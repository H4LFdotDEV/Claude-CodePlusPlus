import * as vscode from 'vscode';
import * as os from 'os';
import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const ONBOARDING_COMPLETE_KEY = 'caiide.onboardingComplete';
const USER_PROFILE_KEY = 'caiide.userProfile';

interface SystemInfo {
    os: string;
    arch: string;
    ramGb: number;
    cpuCores: number;
    cpuModel: string;
    diskGb: number;
    profile: string;
    dockerRunning: boolean;
}

interface ServiceStatus {
    name: string;
    status: 'running' | 'stopped' | 'unknown';
    tier: string;
}

interface UserProfile {
    email?: string;
    role?: string;
    languages?: string[];
    style?: string;
    experience?: string;
    notifications?: boolean;
}

export class OnboardingPanel {
    public static currentPanel: OnboardingPanel | undefined;
    private static readonly viewType = 'caiideOnboarding';

    private readonly _panel: vscode.WebviewPanel;
    private readonly _context: vscode.ExtensionContext;
    private _disposables: vscode.Disposable[] = [];

    private constructor(panel: vscode.WebviewPanel, context: vscode.ExtensionContext) {
        this._panel = panel;
        this._context = context;

        // Set initial HTML
        this._panel.webview.html = this._getLoadingHtml();

        // Handle messages from webview
        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.command) {
                    case 'ready':
                        await this._initializeWizard();
                        break;
                    case 'saveApiKey':
                        await this._saveApiKey(message.key, message.value);
                        break;
                    case 'saveUserProfile':
                        await this._saveUserProfile(message.profile);
                        break;
                    case 'completeOnboarding':
                        await this._completeOnboarding();
                        break;
                    case 'skipOnboarding':
                        await this._skipOnboarding();
                        break;
                    case 'refreshServices':
                        await this._sendServiceStatus();
                        break;
                    case 'launchOpenClaw':
                        await this._launchOpenClaw();
                        break;
                }
            },
            null,
            this._disposables
        );

        // Handle panel disposal
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    }

    public static createOrShow(context: vscode.ExtensionContext) {
        const column = vscode.ViewColumn.One;

        if (OnboardingPanel.currentPanel) {
            OnboardingPanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            OnboardingPanel.viewType,
            'Welcome to CAIIDE++',
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(context.extensionUri, 'media')
                ]
            }
        );

        OnboardingPanel.currentPanel = new OnboardingPanel(panel, context);
    }

    public static dispose() {
        if (OnboardingPanel.currentPanel) {
            OnboardingPanel.currentPanel._panel.dispose();
        }
    }

    public dispose() {
        OnboardingPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) {
                disposable.dispose();
            }
        }
    }

    private async _initializeWizard() {
        const systemInfo = await this._detectSystemInfo();
        const services = await this._detectServices();

        this._panel.webview.html = this._getWizardHtml(systemInfo, services);
    }

    private async _detectSystemInfo(): Promise<SystemInfo> {
        const platform = os.platform();
        const arch = os.arch();
        const ramGb = Math.round(os.totalmem() / (1024 * 1024 * 1024));
        const cpuCores = os.cpus().length;
        const cpuModel = os.cpus()[0]?.model || 'Unknown';

        // Detect available disk space
        let diskGb = 0;
        try {
            if (platform === 'darwin' || platform === 'linux') {
                const { stdout } = await execAsync('df -g ~ | tail -1 | awk \'{print $4}\'');
                diskGb = parseInt(stdout.trim()) || 0;
            }
        } catch {
            diskGb = 50; // Default fallback
        }

        // Detect Docker
        let dockerRunning = false;
        try {
            await execAsync('docker info');
            dockerRunning = true;
        } catch {
            dockerRunning = false;
        }

        // Determine profile
        let profile = 'minimal';
        if (ramGb >= 32 && diskGb >= 50) {
            profile = 'enterprise';
        } else if (ramGb >= 16 && diskGb >= 20 && dockerRunning) {
            profile = 'full';
        } else if (ramGb >= 8 && diskGb >= 10) {
            profile = 'standard';
        }

        // Check for CAIIDE_PROFILE environment variable
        if (process.env.CAIIDE_PROFILE) {
            profile = process.env.CAIIDE_PROFILE;
        }

        return {
            os: platform === 'darwin' ? 'macOS' : platform === 'linux' ? 'Linux' : 'Windows',
            arch,
            ramGb,
            cpuCores,
            cpuModel,
            diskGb,
            profile,
            dockerRunning
        };
    }

    private async _detectServices(): Promise<ServiceStatus[]> {
        const services: ServiceStatus[] = [];
        const containerPrefix = 'claude-code-pp';

        // Check SQLite (always available)
        const sqlitePath = path.join(os.homedir(), '.claude-code-pp', 'memory', 'sqlite');
        services.push({
            name: 'SQLite',
            status: fs.existsSync(sqlitePath) ? 'running' : 'stopped',
            tier: 'Cold'
        });

        // Check Vault
        const vaultPath = path.join(os.homedir(), '.claude-code-pp', 'memory', 'vault');
        services.push({
            name: 'Vault',
            status: fs.existsSync(vaultPath) ? 'running' : 'stopped',
            tier: 'Archive'
        });

        // Check Redis (with correct container name)
        try {
            await execAsync('redis-cli ping');
            services.push({ name: 'Redis', status: 'running', tier: 'Hot' });
        } catch {
            try {
                await execAsync(`docker exec ${containerPrefix}-redis redis-cli ping`);
                services.push({ name: 'Redis', status: 'running', tier: 'Hot' });
            } catch {
                services.push({ name: 'Redis', status: 'stopped', tier: 'Hot' });
            }
        }

        // Check Neo4j (with correct container name)
        try {
            await execAsync('curl -s http://localhost:7474');
            services.push({ name: 'Neo4j/Graphiti', status: 'running', tier: 'Warm' });
        } catch {
            try {
                await execAsync(`docker exec ${containerPrefix}-neo4j curl -s http://localhost:7474`);
                services.push({ name: 'Neo4j/Graphiti', status: 'running', tier: 'Warm' });
            } catch {
                services.push({ name: 'Neo4j/Graphiti', status: 'stopped', tier: 'Warm' });
            }
        }

        return services;
    }

    private async _sendServiceStatus() {
        const services = await this._detectServices();
        this._panel.webview.postMessage({
            command: 'updateServices',
            services
        });
    }

    private _detectShellProfile(): string {
        const shell = process.env.SHELL || '';
        if (shell.includes('zsh')) {
            return path.join(os.homedir(), '.zshrc');
        } else if (shell.includes('bash')) {
            // Check for .bash_profile on macOS
            const bashProfile = path.join(os.homedir(), '.bash_profile');
            if (os.platform() === 'darwin' && fs.existsSync(bashProfile)) {
                return bashProfile;
            }
            return path.join(os.homedir(), '.bashrc');
        }
        return path.join(os.homedir(), '.bashrc');
    }

    private async _appendToShellProfile(key: string, value: string) {
        const shellRc = this._detectShellProfile();
        const exportLine = `export ${key}="${value}"`;
        const marker = `# CAIIDE++ API Key: ${key}`;

        try {
            let content = '';
            if (fs.existsSync(shellRc)) {
                content = fs.readFileSync(shellRc, 'utf8');
            }

            // Check if already present
            if (content.includes(marker)) {
                // Update existing
                const regex = new RegExp(`${marker}\\nexport ${key}="[^"]*"`, 'g');
                content = content.replace(regex, `${marker}\n${exportLine}`);
            } else {
                // Append new
                content += `\n\n${marker}\n${exportLine}\n`;
            }

            fs.writeFileSync(shellRc, content);
            return true;
        } catch (error) {
            console.error('Failed to update shell profile:', error);
            return false;
        }
    }

    private async _updateEnvFile(key: string, value: string) {
        const envPath = path.join(os.homedir(), '.claude-code-pp', '.env');

        try {
            let content = '';
            if (fs.existsSync(envPath)) {
                content = fs.readFileSync(envPath, 'utf8');
            }

            // Check if key exists
            const keyRegex = new RegExp(`^${key}=.*$`, 'm');
            if (keyRegex.test(content)) {
                content = content.replace(keyRegex, `${key}=${value}`);
            } else {
                content += `\n${key}=${value}\n`;
            }

            fs.writeFileSync(envPath, content, { mode: 0o600 });
            return true;
        } catch (error) {
            console.error('Failed to update .env file:', error);
            return false;
        }
    }

    private async _saveApiKey(key: string, value: string) {
        try {
            // 1. Store in VS Code secrets (for IDE access)
            await this._context.secrets.store(key, value);

            // 2. Append to shell profile (for CLI access)
            const shellSaved = await this._appendToShellProfile(key, value);

            // 3. Update .env file (for Docker services)
            const envSaved = await this._updateEnvFile(key, value);

            const message = shellSaved && envSaved
                ? `${key} saved to secrets, shell profile, and .env`
                : `${key} saved to secrets`;

            vscode.window.showInformationMessage(message);

            this._panel.webview.postMessage({
                command: 'apiKeySaved',
                key,
                success: true
            });
        } catch (error) {
            this._panel.webview.postMessage({
                command: 'apiKeySaved',
                key,
                success: false,
                error: String(error)
            });
        }
    }

    private async _saveUserProfile(profile: UserProfile) {
        try {
            // Save to VS Code global state
            await this._context.globalState.update(USER_PROFILE_KEY, profile);

            // Save to config file
            const configDir = path.join(os.homedir(), '.claude-code-pp', 'config');
            if (!fs.existsSync(configDir)) {
                fs.mkdirSync(configDir, { recursive: true });
            }

            const userConfigPath = path.join(configDir, 'user.json');
            fs.writeFileSync(userConfigPath, JSON.stringify(profile, null, 2));

            // Try to store in Memory MCP if available
            try {
                await this._storeProfileInMemory(profile);
            } catch {
                // Memory MCP not available, that's ok
            }

            this._panel.webview.postMessage({
                command: 'profileSaved',
                success: true
            });
        } catch (error) {
            this._panel.webview.postMessage({
                command: 'profileSaved',
                success: false,
                error: String(error)
            });
        }
    }

    private async _storeProfileInMemory(profile: UserProfile) {
        // Build profile description for Claude
        const parts: string[] = [];

        if (profile.role) {
            parts.push(`User's primary role: ${profile.role}`);
        }
        if (profile.experience) {
            parts.push(`Programming experience: ${profile.experience} years`);
        }
        if (profile.languages && profile.languages.length > 0) {
            parts.push(`Primary languages: ${profile.languages.join(', ')}`);
        }
        if (profile.style) {
            parts.push(`Preferred explanation style: ${profile.style}`);
        }

        if (parts.length === 0) {
            return;
        }

        const content = `User Profile (from onboarding):\n${parts.join('\n')}`;

        // Write to vault for persistence
        const vaultPath = path.join(os.homedir(), '.claude-code-pp', 'memory', 'vault', 'notes');
        if (!fs.existsSync(vaultPath)) {
            fs.mkdirSync(vaultPath, { recursive: true });
        }

        const profileNote = path.join(vaultPath, 'user-profile.md');
        const noteContent = `---
type: preference
tags: [user-profile, onboarding]
created: ${new Date().toISOString()}
---

# User Profile

${parts.map(p => `- ${p}`).join('\n')}
`;

        fs.writeFileSync(profileNote, noteContent);
    }

    private async _launchOpenClaw() {
        try {
            // Check if OpenClaw is installed
            const { stdout } = await execAsync('which openclaw || which npx');

            if (stdout.includes('openclaw')) {
                // Run openclaw onboard
                const terminal = vscode.window.createTerminal('OpenClaw Setup');
                terminal.sendText('openclaw onboard');
                terminal.show();
            } else {
                // Offer to install via npx
                const choice = await vscode.window.showInformationMessage(
                    'OpenClaw enables Claude via WhatsApp, Telegram, Discord, and more. Install it now?',
                    'Install OpenClaw',
                    'Skip'
                );

                if (choice === 'Install OpenClaw') {
                    const terminal = vscode.window.createTerminal('OpenClaw Install');
                    terminal.sendText('npm install -g openclaw && openclaw onboard');
                    terminal.show();
                }
            }

            this._panel.webview.postMessage({
                command: 'openclawLaunched',
                success: true
            });
        } catch {
            this._panel.webview.postMessage({
                command: 'openclawLaunched',
                success: false
            });
        }
    }

    private async _completeOnboarding() {
        await this._context.globalState.update(ONBOARDING_COMPLETE_KEY, true);
        vscode.window.showInformationMessage('Welcome to CAIIDE++! Your AI-native development environment is ready.');
        this._panel.dispose();
    }

    private async _skipOnboarding() {
        await this._context.globalState.update(ONBOARDING_COMPLETE_KEY, true);
        this._panel.dispose();
    }

    private _getLoadingHtml(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Loading CAIIDE++</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            background-color: var(--vscode-editor-background);
            color: var(--vscode-foreground);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .loader {
            text-align: center;
        }
        .spinner {
            width: 50px;
            height: 50px;
            border: 4px solid var(--vscode-button-background);
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="loader">
        <div class="spinner"></div>
        <p>Detecting system resources...</p>
    </div>
    <script>
        const vscode = acquireVsCodeApi();
        vscode.postMessage({ command: 'ready' });
    </script>
</body>
</html>`;
    }

    private _getWizardHtml(systemInfo: SystemInfo, services: ServiceStatus[]): string {
        const profileDescriptions: Record<string, string> = {
            minimal: 'SQLite + Vault (lightweight)',
            standard: '+ Redis caching',
            full: '+ Neo4j/Graphiti knowledge graph',
            enterprise: '+ livegrep + LiteLLM'
        };

        const tierColors: Record<string, string> = {
            Hot: '#ff6b6b',
            Warm: '#feca57',
            Cold: '#48dbfb',
            Archive: '#a29bfe'
        };

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to CAIIDE++</title>
    <style>
        :root {
            --primary: #d4a574;
            --primary-hover: #c49664;
            --success: #54d17a;
            --warning: #feca57;
            --danger: #ff6b6b;
            --bg: var(--vscode-editor-background);
            --fg: var(--vscode-foreground);
            --border: var(--vscode-panel-border);
            --input-bg: var(--vscode-input-background);
            --input-border: var(--vscode-input-border);
        }

        * {
            box-sizing: border-box;
        }

        body {
            font-family: var(--vscode-font-family);
            background-color: var(--bg);
            color: var(--fg);
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }

        .container {
            max-width: 700px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo {
            font-size: 48px;
            margin-bottom: 10px;
        }

        h1 {
            color: var(--primary);
            margin: 0 0 10px;
            font-size: 28px;
        }

        .subtitle {
            opacity: 0.8;
            font-size: 16px;
        }

        .step {
            display: none;
            animation: fadeIn 0.3s ease;
        }

        .step.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .card {
            background: var(--vscode-sideBar-background);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .card-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .info-item {
            padding: 10px;
            background: var(--bg);
            border-radius: 6px;
        }

        .info-label {
            font-size: 12px;
            opacity: 0.7;
            text-transform: uppercase;
        }

        .info-value {
            font-size: 18px;
            font-weight: 600;
        }

        .profile-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            background: var(--primary);
            color: #000;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
        }

        .tier-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .tier-item {
            display: flex;
            align-items: center;
            padding: 12px;
            background: var(--bg);
            border-radius: 6px;
            gap: 15px;
        }

        .tier-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }

        .tier-name {
            flex: 1;
        }

        .tier-status {
            font-size: 14px;
        }

        .tier-status.running {
            color: var(--success);
        }

        .tier-status.stopped {
            color: var(--danger);
        }

        .input-group {
            margin-bottom: 15px;
        }

        .input-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
        }

        .input-group input,
        .input-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--input-border);
            background: var(--input-bg);
            color: var(--fg);
            border-radius: 4px;
            font-size: 14px;
        }

        .input-group input:focus,
        .input-group select:focus {
            outline: 2px solid var(--primary);
            border-color: var(--primary);
        }

        .input-group .hint {
            font-size: 12px;
            opacity: 0.7;
            margin-top: 5px;
        }

        .input-group .saved {
            color: var(--success);
        }

        .checkbox-group {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .checkbox-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--bg);
            border-radius: 6px;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.2s;
        }

        .checkbox-item:hover {
            border-color: var(--primary);
        }

        .checkbox-item.selected {
            background: var(--primary);
            color: #000;
        }

        .checkbox-item input {
            display: none;
        }

        .radio-group {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .radio-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px;
            background: var(--bg);
            border-radius: 6px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
        }

        .radio-item:hover {
            border-color: var(--border);
        }

        .radio-item.selected {
            border-color: var(--primary);
            background: rgba(212, 165, 116, 0.1);
        }

        .radio-item input {
            display: none;
        }

        .button-group {
            display: flex;
            justify-content: space-between;
            margin-top: 30px;
        }

        button {
            padding: 10px 24px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
        }

        .btn-primary {
            background: var(--primary);
            color: #000;
        }

        .btn-primary:hover {
            background: var(--primary-hover);
        }

        .btn-secondary {
            background: transparent;
            color: var(--fg);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }

        .step-indicators {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
        }

        .step-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--border);
            transition: all 0.3s;
        }

        .step-dot.active {
            background: var(--primary);
            width: 30px;
            border-radius: 5px;
        }

        .step-dot.completed {
            background: var(--success);
        }

        .tips {
            background: var(--vscode-textBlockQuote-background);
            border-left: 3px solid var(--primary);
            padding: 15px;
            border-radius: 0 6px 6px 0;
            margin-top: 20px;
        }

        .tips h4 {
            margin: 0 0 10px;
        }

        .tips ul {
            margin: 0;
            padding-left: 20px;
        }

        .tips li {
            margin-bottom: 5px;
        }

        .optional-card {
            border: 2px dashed var(--border);
            background: transparent;
        }

        .optional-card:hover {
            border-color: var(--primary);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">C++</div>
            <h1>Welcome to CAIIDE++</h1>
            <p class="subtitle">AI-Native Development with Persistent Memory</p>
        </div>

        <div class="step-indicators">
            <div class="step-dot active" data-step="1"></div>
            <div class="step-dot" data-step="2"></div>
            <div class="step-dot" data-step="3"></div>
            <div class="step-dot" data-step="4"></div>
            <div class="step-dot" data-step="5"></div>
            <div class="step-dot" data-step="6"></div>
        </div>

        <!-- Step 1: System Check -->
        <div class="step active" id="step-1">
            <div class="card">
                <div class="card-title">Your System</div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Operating System</div>
                        <div class="info-value">${systemInfo.os} (${systemInfo.arch})</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Memory</div>
                        <div class="info-value">${systemInfo.ramGb} GB</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">CPU</div>
                        <div class="info-value">${systemInfo.cpuCores} cores</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Disk Available</div>
                        <div class="info-value">${systemInfo.diskGb} GB</div>
                    </div>
                </div>
                <div style="margin-top: 20px; text-align: center;">
                    <div class="info-label">Recommended Profile</div>
                    <div style="margin-top: 10px;">
                        <span class="profile-badge">${systemInfo.profile}</span>
                    </div>
                    <div style="margin-top: 8px; font-size: 14px; opacity: 0.8;">
                        ${profileDescriptions[systemInfo.profile] || 'Standard configuration'}
                    </div>
                </div>
            </div>

            <div class="button-group">
                <button class="btn-secondary" onclick="skipOnboarding()">Skip Setup</button>
                <button class="btn-primary" onclick="nextStep()">Get Started</button>
            </div>
        </div>

        <!-- Step 2: API Keys -->
        <div class="step" id="step-2">
            <div class="card">
                <div class="card-title">API Configuration</div>
                <p style="opacity: 0.8; margin-bottom: 20px;">
                    Configure your API keys. They'll be saved to VS Code secrets, your shell profile, and the .env file for full CLI + Docker support.
                </p>

                <div class="input-group">
                    <label for="anthropic-key">Anthropic API Key <span style="color: var(--danger);">*</span></label>
                    <input type="password" id="anthropic-key" placeholder="sk-ant-..." />
                    <div class="hint" id="anthropic-hint">Required for Claude AI features. <a href="https://console.anthropic.com/" target="_blank">Get one here</a></div>
                </div>

                <div class="input-group">
                    <label for="openai-key">OpenAI API Key (optional)</label>
                    <input type="password" id="openai-key" placeholder="sk-..." />
                    <div class="hint" id="openai-hint">Used for embeddings and GPT fallback</div>
                </div>
            </div>

            <div class="button-group">
                <button class="btn-secondary" onclick="prevStep()">Back</button>
                <button class="btn-primary" onclick="saveApiKeys()">Save & Continue</button>
            </div>
        </div>

        <!-- Step 3: About You (Questionnaire) -->
        <div class="step" id="step-3">
            <div class="card">
                <div class="card-title">Help Claude Understand You</div>
                <p style="opacity: 0.8; margin-bottom: 20px;">
                    This helps personalize your AI assistant experience. All fields are optional.
                </p>

                <div class="input-group">
                    <label>What's your primary role?</label>
                    <div class="radio-group" id="role-group">
                        <label class="radio-item" data-value="Backend Developer">
                            <input type="radio" name="role" value="Backend Developer">
                            Backend Developer
                        </label>
                        <label class="radio-item" data-value="Frontend Developer">
                            <input type="radio" name="role" value="Frontend Developer">
                            Frontend Developer
                        </label>
                        <label class="radio-item" data-value="Full Stack">
                            <input type="radio" name="role" value="Full Stack">
                            Full Stack Developer
                        </label>
                        <label class="radio-item" data-value="DevOps/SRE">
                            <input type="radio" name="role" value="DevOps/SRE">
                            DevOps / SRE
                        </label>
                        <label class="radio-item" data-value="Data Scientist">
                            <input type="radio" name="role" value="Data Scientist">
                            Data Scientist / ML Engineer
                        </label>
                        <label class="radio-item" data-value="Student">
                            <input type="radio" name="role" value="Student">
                            Student / Learning
                        </label>
                    </div>
                </div>

                <div class="input-group">
                    <label>Primary programming languages? (select all that apply)</label>
                    <div class="checkbox-group" id="languages-group">
                        <label class="checkbox-item" data-value="Python">
                            <input type="checkbox" value="Python">
                            Python
                        </label>
                        <label class="checkbox-item" data-value="TypeScript">
                            <input type="checkbox" value="TypeScript">
                            TypeScript
                        </label>
                        <label class="checkbox-item" data-value="JavaScript">
                            <input type="checkbox" value="JavaScript">
                            JavaScript
                        </label>
                        <label class="checkbox-item" data-value="Go">
                            <input type="checkbox" value="Go">
                            Go
                        </label>
                        <label class="checkbox-item" data-value="Rust">
                            <input type="checkbox" value="Rust">
                            Rust
                        </label>
                        <label class="checkbox-item" data-value="Java">
                            <input type="checkbox" value="Java">
                            Java
                        </label>
                        <label class="checkbox-item" data-value="C/C++">
                            <input type="checkbox" value="C/C++">
                            C/C++
                        </label>
                        <label class="checkbox-item" data-value="Swift">
                            <input type="checkbox" value="Swift">
                            Swift
                        </label>
                    </div>
                </div>
            </div>

            <div class="button-group">
                <button class="btn-secondary" onclick="prevStep()">Back</button>
                <button class="btn-primary" onclick="nextStep()">Continue</button>
            </div>
        </div>

        <!-- Step 4: Preferences -->
        <div class="step" id="step-4">
            <div class="card">
                <div class="card-title">Your Preferences</div>

                <div class="input-group">
                    <label>How do you prefer explanations?</label>
                    <div class="radio-group" id="style-group">
                        <label class="radio-item" data-value="concise">
                            <input type="radio" name="style" value="concise">
                            Concise and direct - just the essentials
                        </label>
                        <label class="radio-item" data-value="detailed">
                            <input type="radio" name="style" value="detailed">
                            Detailed with examples - show me how
                        </label>
                        <label class="radio-item" data-value="visual">
                            <input type="radio" name="style" value="visual">
                            Visual / diagrams when possible
                        </label>
                    </div>
                </div>

                <div class="input-group">
                    <label>Years of programming experience?</label>
                    <div class="radio-group" id="experience-group">
                        <label class="radio-item" data-value="0-2">
                            <input type="radio" name="experience" value="0-2">
                            0-2 years
                        </label>
                        <label class="radio-item" data-value="3-5">
                            <input type="radio" name="experience" value="3-5">
                            3-5 years
                        </label>
                        <label class="radio-item" data-value="5-10">
                            <input type="radio" name="experience" value="5-10">
                            5-10 years
                        </label>
                        <label class="radio-item" data-value="10+">
                            <input type="radio" name="experience" value="10+">
                            10+ years
                        </label>
                    </div>
                </div>

                <div class="input-group">
                    <label for="user-email">Email (optional)</label>
                    <input type="email" id="user-email" placeholder="you@example.com" />
                    <div class="hint">For updates and tips. We won't spam you.</div>
                </div>
            </div>

            <div class="button-group">
                <button class="btn-secondary" onclick="prevStep()">Back</button>
                <button class="btn-primary" onclick="saveProfile()">Save & Continue</button>
            </div>
        </div>

        <!-- Step 5: Services -->
        <div class="step" id="step-5">
            <div class="card">
                <div class="card-title">Memory Tiers</div>
                <p style="opacity: 0.8; margin-bottom: 20px;">
                    Your tiered memory system status. Each tier provides different capabilities.
                </p>

                <div class="tier-list" id="tier-list">
                    ${services.map(service => `
                        <div class="tier-item">
                            <div class="tier-indicator" style="background: ${tierColors[service.tier] || '#888'}"></div>
                            <div class="tier-name">
                                <strong>${service.name}</strong>
                                <div style="font-size: 12px; opacity: 0.7;">${service.tier} tier</div>
                            </div>
                            <div class="tier-status ${service.status}">${service.status === 'running' ? 'Connected' : 'Not running'}</div>
                        </div>
                    `).join('')}
                </div>

                <button class="btn-secondary" style="margin-top: 15px; width: 100%;" onclick="refreshServices()">
                    Refresh Status
                </button>
            </div>

            <!-- Optional: OpenClaw -->
            <div class="card optional-card">
                <div class="card-title">Connect Messaging (Optional)</div>
                <p style="opacity: 0.8; margin-bottom: 15px;">
                    Access Claude via WhatsApp, Telegram, Discord, Slack, and more with OpenClaw.
                </p>
                <button class="btn-secondary" style="width: 100%;" onclick="launchOpenClaw()">
                    Set Up Messaging Channels
                </button>
            </div>

            <div class="button-group">
                <button class="btn-secondary" onclick="prevStep()">Back</button>
                <button class="btn-primary" onclick="nextStep()">Continue</button>
            </div>
        </div>

        <!-- Step 6: Complete -->
        <div class="step" id="step-6">
            <div class="card">
                <div class="card-title">You're All Set!</div>
                <p style="opacity: 0.8;">
                    CAIIDE++ is configured and ready to use. Here are some quick tips to get started:
                </p>

                <div class="tips">
                    <h4>Quick Tips</h4>
                    <ul>
                        <li>Use <code>Cmd/Ctrl+Shift+M</code> to search memory</li>
                        <li>Select code and use <code>Cmd/Ctrl+Shift+S</code> to store</li>
                        <li>Open the Memory panel in the Activity Bar</li>
                        <li>Run <code>memory_stats</code> in Claude CLI to verify</li>
                    </ul>
                </div>
            </div>

            <div class="button-group">
                <button class="btn-secondary" onclick="prevStep()">Back</button>
                <button class="btn-primary" onclick="completeOnboarding()">Start Coding</button>
            </div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentStep = 1;
        const totalSteps = 6;

        // Profile data
        let userProfile = {
            role: null,
            languages: [],
            style: null,
            experience: null,
            email: null
        };

        // Initialize radio/checkbox handlers
        document.querySelectorAll('.radio-item').forEach(item => {
            item.addEventListener('click', () => {
                const group = item.parentElement;
                group.querySelectorAll('.radio-item').forEach(i => i.classList.remove('selected'));
                item.classList.add('selected');
                item.querySelector('input').checked = true;

                // Update profile
                const groupId = group.id;
                if (groupId === 'role-group') userProfile.role = item.dataset.value;
                if (groupId === 'style-group') userProfile.style = item.dataset.value;
                if (groupId === 'experience-group') userProfile.experience = item.dataset.value;
            });
        });

        document.querySelectorAll('.checkbox-item').forEach(item => {
            item.addEventListener('click', () => {
                item.classList.toggle('selected');
                const checkbox = item.querySelector('input');
                checkbox.checked = !checkbox.checked;

                // Update languages
                const selected = [];
                document.querySelectorAll('#languages-group .checkbox-item.selected').forEach(i => {
                    selected.push(i.dataset.value);
                });
                userProfile.languages = selected;
            });
        });

        function updateStepIndicators() {
            document.querySelectorAll('.step-dot').forEach((dot, index) => {
                const stepNum = index + 1;
                dot.classList.remove('active', 'completed');
                if (stepNum === currentStep) {
                    dot.classList.add('active');
                } else if (stepNum < currentStep) {
                    dot.classList.add('completed');
                }
            });
        }

        function showStep(step) {
            document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
            document.getElementById('step-' + step).classList.add('active');
            currentStep = step;
            updateStepIndicators();
        }

        function nextStep() {
            if (currentStep < totalSteps) {
                showStep(currentStep + 1);
            }
        }

        function prevStep() {
            if (currentStep > 1) {
                showStep(currentStep - 1);
            }
        }

        function saveApiKeys() {
            const anthropicKey = document.getElementById('anthropic-key').value;
            const openaiKey = document.getElementById('openai-key').value;

            if (anthropicKey) {
                vscode.postMessage({
                    command: 'saveApiKey',
                    key: 'ANTHROPIC_API_KEY',
                    value: anthropicKey
                });
            }

            if (openaiKey) {
                vscode.postMessage({
                    command: 'saveApiKey',
                    key: 'OPENAI_API_KEY',
                    value: openaiKey
                });
            }

            nextStep();
        }

        function saveProfile() {
            // Get email
            userProfile.email = document.getElementById('user-email').value || null;

            vscode.postMessage({
                command: 'saveUserProfile',
                profile: userProfile
            });

            nextStep();
        }

        function refreshServices() {
            vscode.postMessage({ command: 'refreshServices' });
        }

        function launchOpenClaw() {
            vscode.postMessage({ command: 'launchOpenClaw' });
        }

        function completeOnboarding() {
            vscode.postMessage({ command: 'completeOnboarding' });
        }

        function skipOnboarding() {
            vscode.postMessage({ command: 'skipOnboarding' });
        }

        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
                case 'apiKeySaved':
                    const hintId = message.key === 'ANTHROPIC_API_KEY' ? 'anthropic-hint' : 'openai-hint';
                    const hint = document.getElementById(hintId);
                    if (message.success) {
                        hint.textContent = 'Saved to secrets, shell profile, and .env!';
                        hint.classList.add('saved');
                    } else {
                        hint.textContent = 'Failed to save: ' + message.error;
                    }
                    break;

                case 'updateServices':
                    const tierList = document.getElementById('tier-list');
                    tierList.innerHTML = message.services.map(service => \`
                        <div class="tier-item">
                            <div class="tier-indicator" style="background: \${getTierColor(service.tier)}"></div>
                            <div class="tier-name">
                                <strong>\${service.name}</strong>
                                <div style="font-size: 12px; opacity: 0.7;">\${service.tier} tier</div>
                            </div>
                            <div class="tier-status \${service.status}">\${service.status === 'running' ? 'Connected' : 'Not running'}</div>
                        </div>
                    \`).join('');
                    break;

                case 'profileSaved':
                    // Profile saved, continue
                    break;
            }
        });

        function getTierColor(tier) {
            const colors = {
                'Hot': '#ff6b6b',
                'Warm': '#feca57',
                'Cold': '#48dbfb',
                'Archive': '#a29bfe'
            };
            return colors[tier] || '#888';
        }
    </script>
</body>
</html>`;
    }
}
