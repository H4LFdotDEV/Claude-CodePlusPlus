import * as vscode from 'vscode';
import { McpClient, MemoryStats } from '../mcpClient';

export class StatsProvider implements vscode.TreeDataProvider<StatItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<StatItem | undefined | null | void> =
        new vscode.EventEmitter<StatItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<StatItem | undefined | null | void> =
        this._onDidChangeTreeData.event;

    private stats: MemoryStats | null = null;

    constructor(private mcpClient: McpClient) {}

    async refresh(): Promise<void> {
        try {
            this.stats = await this.mcpClient.getStats();
        } catch (error) {
            console.error('Failed to refresh stats:', error);
            this.stats = null;
        }
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: StatItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: StatItem): Thenable<StatItem[]> {
        if (element) {
            // Return children for expandable items
            if (element.children) {
                return Promise.resolve(element.children);
            }
            return Promise.resolve([]);
        }

        if (!this.stats) {
            return Promise.resolve([
                new StatItem(
                    'Not connected',
                    'Connect to Memory server to see statistics',
                    'warning'
                )
            ]);
        }

        const items: StatItem[] = [
            new StatItem(
                'Total Documents',
                this.stats.total_documents.toString(),
                'database'
            )
        ];

        // Add component stats if available
        if (this.stats.components && typeof this.stats.components === 'object') {
            const componentItems = Object.entries(this.stats.components).map(
                ([name, value]) => new StatItem(
                    name,
                    typeof value === 'object' ? JSON.stringify(value) : String(value),
                    'package'
                )
            );

            if (componentItems.length > 0) {
                items.push(new StatItem(
                    'Components',
                    `${componentItems.length} active`,
                    'extensions',
                    vscode.TreeItemCollapsibleState.Collapsed,
                    componentItems
                ));
            }
        }

        return Promise.resolve(items);
    }
}

export class StatItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly value: string,
        public readonly icon: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None,
        public readonly children?: StatItem[]
    ) {
        super(label, collapsibleState);

        this.description = value;
        this.tooltip = `${label}: ${value}`;
        this.iconPath = new vscode.ThemeIcon(icon);
    }
}
