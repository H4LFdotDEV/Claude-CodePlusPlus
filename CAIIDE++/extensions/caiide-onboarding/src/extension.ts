import * as vscode from 'vscode';
import { OnboardingPanel } from './onboardingPanel';

const ONBOARDING_COMPLETE_KEY = 'caiide.onboardingComplete';

export async function activate(context: vscode.ExtensionContext) {
    console.log('CAIIDE++ Onboarding extension activating...');

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('caiide-onboarding.showWizard', () => {
            OnboardingPanel.createOrShow(context);
        }),

        vscode.commands.registerCommand('caiide-onboarding.resetOnboarding', async () => {
            await context.globalState.update(ONBOARDING_COMPLETE_KEY, false);
            vscode.window.showInformationMessage('Onboarding reset. Restart CAIIDE++ to see the wizard.');
        })
    );

    // Check if we should show onboarding
    const onboardingComplete = context.globalState.get<boolean>(ONBOARDING_COMPLETE_KEY, false);
    const forceOnboarding = process.env.CAIIDE_ONBOARDING === 'true';
    const config = vscode.workspace.getConfiguration('caiide-onboarding');
    const showOnStartup = config.get<boolean>('showOnStartup', true);

    if ((!onboardingComplete && showOnStartup) || forceOnboarding) {
        // Small delay to let VS Code fully initialize
        setTimeout(() => {
            OnboardingPanel.createOrShow(context);
        }, 1000);
    }

    console.log('CAIIDE++ Onboarding extension activated');
}

export function deactivate() {
    OnboardingPanel.dispose();
}
