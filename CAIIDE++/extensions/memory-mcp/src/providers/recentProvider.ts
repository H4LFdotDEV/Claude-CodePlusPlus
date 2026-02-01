import * as vscode from 'vscode';
import { McpClient, MemoryResult } from '../mcpClient';

export class RecentMemoriesProvider implements vscode.TreeDataProvider<MemoryItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<MemoryItem | undefined | null | void> =
        new vscode.EventEmitter<MemoryItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<MemoryItem | undefined | null | void> =
        this._onDidChangeTreeData.event;

    private memories: MemoryResult[] = [];

    constructor(private mcpClient: McpClient) {}

    async refresh(): Promise<void> {
        try {
            this.memories = await this.mcpClient.list(50);
        } catch (error) {
            console.error('Failed to refresh memories:', error);
            this.memories = [];
        }
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: MemoryItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: MemoryItem): Thenable<MemoryItem[]> {
        if (element) {
            return Promise.resolve([]);
        }

        if (this.memories.length === 0) {
            return Promise.resolve([
                new MemoryItem(
                    'No memories yet',
                    '',
                    'info',
                    vscode.TreeItemCollapsibleState.None
                )
            ]);
        }

        return Promise.resolve(
            this.memories.map(memory => new MemoryItem(
                memory.content.substring(0, 60) + (memory.content.length > 60 ? '...' : ''),
                memory.id,
                memory.doc_type,
                vscode.TreeItemCollapsibleState.None,
                {
                    command: 'caiide-memory.openMemory',
                    title: 'Open Memory',
                    arguments: [memory.id]
                }
            ))
        );
    }
}

export class MemoryItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly memoryId: string,
        public readonly memoryType: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly command?: vscode.Command
    ) {
        super(label, collapsibleState);

        this.tooltip = `${this.memoryType}: ${this.label}`;
        this.description = this.memoryType;

        // Set icon based on type
        const iconMap: Record<string, string> = {
            'code': 'symbol-method',
            'note': 'note',
            'reference': 'book',
            'conversation': 'comment-discussion',
            'info': 'info'
        };
        this.iconPath = new vscode.ThemeIcon(iconMap[this.memoryType] || 'file');

        if (this.memoryId) {
            this.contextValue = 'memory';
        }
    }
}
