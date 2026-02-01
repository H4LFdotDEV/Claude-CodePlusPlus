import * as vscode from 'vscode';
import { McpClient } from './mcpClient';
import { MemorySearchPanel } from './panels/searchPanel';
import { RecentMemoriesProvider } from './providers/recentProvider';
import { StatsProvider } from './providers/statsProvider';

let mcpClient: McpClient;
let searchPanel: MemorySearchPanel;
let recentProvider: RecentMemoriesProvider;
let statsProvider: StatsProvider;

export async function activate(context: vscode.ExtensionContext) {
    console.log('CAIIDE++ Memory extension activating...');

    // Get configuration
    const config = vscode.workspace.getConfiguration('caiide-memory');
    const serverCommand = config.get<string>('serverCommand', 'python -m memory_mcp.server');
    const autoConnect = config.get<boolean>('autoConnect', true);

    // Initialize MCP client
    mcpClient = new McpClient(serverCommand);

    // Initialize providers
    recentProvider = new RecentMemoriesProvider(mcpClient);
    statsProvider = new StatsProvider(mcpClient);

    // Register tree data providers
    vscode.window.registerTreeDataProvider('memoryRecent', recentProvider);
    vscode.window.registerTreeDataProvider('memoryStats', statsProvider);

    // Register webview provider for search
    searchPanel = new MemorySearchPanel(context.extensionUri, mcpClient);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('memorySearch', searchPanel)
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('caiide-memory.search', async () => {
            const query = await vscode.window.showInputBox({
                prompt: 'Search memory',
                placeHolder: 'Enter search query...'
            });
            if (query) {
                await searchMemory(query);
            }
        }),

        vscode.commands.registerCommand('caiide-memory.store', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('No active editor');
                return;
            }

            const selection = editor.document.getText(editor.selection);
            if (!selection) {
                vscode.window.showWarningMessage('No text selected');
                return;
            }

            await storeMemory(selection, editor.document.fileName);
        }),

        vscode.commands.registerCommand('caiide-memory.storeFile', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('No active editor');
                return;
            }

            const content = editor.document.getText();
            await storeMemory(content, editor.document.fileName, 'file');
        }),

        vscode.commands.registerCommand('caiide-memory.refresh', async () => {
            await recentProvider.refresh();
            await statsProvider.refresh();
            vscode.window.showInformationMessage('Memory refreshed');
        }),

        vscode.commands.registerCommand('caiide-memory.stats', async () => {
            try {
                const stats = await mcpClient.getStats();
                vscode.window.showInformationMessage(
                    `Memory: ${stats.total_documents} documents stored`
                );
            } catch (error) {
                vscode.window.showErrorMessage(`Failed to get stats: ${error}`);
            }
        }),

        vscode.commands.registerCommand('caiide-memory.connect', async () => {
            try {
                await mcpClient.connect();
                vscode.window.showInformationMessage('Connected to Memory server');
                await recentProvider.refresh();
                await statsProvider.refresh();
            } catch (error) {
                vscode.window.showErrorMessage(`Connection failed: ${error}`);
            }
        }),

        vscode.commands.registerCommand('caiide-memory.openMemory', async (id: string) => {
            try {
                const memory = await mcpClient.recall(id);
                if (memory) {
                    const doc = await vscode.workspace.openTextDocument({
                        content: memory.content,
                        language: detectLanguage(memory.source)
                    });
                    await vscode.window.showTextDocument(doc);
                }
            } catch (error) {
                vscode.window.showErrorMessage(`Failed to open memory: ${error}`);
            }
        })
    );

    // Auto-connect if configured
    if (autoConnect) {
        try {
            await mcpClient.connect();
            console.log('Connected to Memory MCP server');

            // Initial refresh
            await recentProvider.refresh();
            await statsProvider.refresh();
        } catch (error) {
            console.warn('Auto-connect failed:', error);
            vscode.window.showWarningMessage(
                'Memory server not available. Use "Memory: Connect" command to retry.'
            );
        }
    }

    // Status bar item
    const statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.command = 'caiide-memory.stats';
    statusBarItem.text = '$(database) Memory';
    statusBarItem.tooltip = 'CAIIDE++ Memory';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    console.log('CAIIDE++ Memory extension activated');
}

async function searchMemory(query: string): Promise<void> {
    try {
        const results = await mcpClient.search(query, 20);

        if (results.length === 0) {
            vscode.window.showInformationMessage('No memories found');
            return;
        }

        // Show quick pick with results
        const items = results.map(r => ({
            label: r.content.substring(0, 80) + (r.content.length > 80 ? '...' : ''),
            description: r.doc_type,
            detail: r.source,
            id: r.id
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: `Found ${results.length} memories`,
            matchOnDescription: true,
            matchOnDetail: true
        });

        if (selected) {
            await vscode.commands.executeCommand('caiide-memory.openMemory', selected.id);
        }
    } catch (error) {
        vscode.window.showErrorMessage(`Search failed: ${error}`);
    }
}

async function storeMemory(
    content: string,
    source: string,
    type: string = 'code'
): Promise<void> {
    try {
        // Ask for additional metadata
        const docType = await vscode.window.showQuickPick(
            ['code', 'note', 'reference', 'conversation'],
            { placeHolder: 'Select memory type' }
        );

        if (!docType) {
            return;
        }

        const tagsInput = await vscode.window.showInputBox({
            prompt: 'Tags (comma-separated, optional)',
            placeHolder: 'tag1, tag2, tag3'
        });

        const tags = tagsInput
            ? tagsInput.split(',').map(t => t.trim()).filter(t => t)
            : [];

        // Get default tags from config
        const config = vscode.workspace.getConfiguration('caiide-memory');
        const defaultTags = config.get<string[]>('defaultTags', []);
        const allTags = [...new Set([...defaultTags, ...tags])];

        await mcpClient.store(content, docType, source, allTags);
        vscode.window.showInformationMessage('Memory stored successfully');

        // Refresh the recent list
        await recentProvider.refresh();
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to store memory: ${error}`);
    }
}

function detectLanguage(source: string): string {
    const ext = source.split('.').pop()?.toLowerCase();
    const langMap: Record<string, string> = {
        'ts': 'typescript',
        'tsx': 'typescriptreact',
        'js': 'javascript',
        'jsx': 'javascriptreact',
        'py': 'python',
        'rs': 'rust',
        'go': 'go',
        'swift': 'swift',
        'md': 'markdown',
        'json': 'json',
        'yaml': 'yaml',
        'yml': 'yaml',
        'toml': 'toml',
        'sh': 'shellscript',
        'bash': 'shellscript'
    };
    return langMap[ext || ''] || 'plaintext';
}

export function deactivate() {
    if (mcpClient) {
        mcpClient.disconnect();
    }
}
