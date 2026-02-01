import * as vscode from 'vscode';
import { McpClient, MemoryResult } from '../mcpClient';

export class MemorySearchPanel implements vscode.WebviewViewProvider {
    public static readonly viewType = 'memorySearch';

    private _view?: vscode.WebviewView;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly mcpClient: McpClient
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'search':
                    await this.handleSearch(data.query);
                    break;
                case 'openMemory':
                    await vscode.commands.executeCommand(
                        'caiide-memory.openMemory',
                        data.id
                    );
                    break;
            }
        });
    }

    private async handleSearch(query: string): Promise<void> {
        if (!this._view) {
            return;
        }

        try {
            const results = await this.mcpClient.search(query, 20);
            this._view.webview.postMessage({
                type: 'results',
                results
            });
        } catch (error) {
            this._view.webview.postMessage({
                type: 'error',
                message: String(error)
            });
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Memory Search</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-sideBar-background);
            padding: 12px;
        }

        .search-container {
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
        }

        input[type="text"] {
            flex: 1;
            padding: 6px 10px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 4px;
            outline: none;
        }

        input[type="text"]:focus {
            border-color: var(--vscode-focusBorder);
        }

        button {
            padding: 6px 12px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }

        button:hover {
            background: var(--vscode-button-hoverBackground);
        }

        .results {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .result-item {
            padding: 10px;
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.15s;
        }

        .result-item:hover {
            background: var(--vscode-list-hoverBackground);
        }

        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }

        .result-type {
            font-size: 10px;
            text-transform: uppercase;
            padding: 2px 6px;
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            border-radius: 3px;
        }

        .result-source {
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .result-content {
            font-size: 12px;
            line-height: 1.4;
            color: var(--vscode-foreground);
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
        }

        .empty {
            text-align: center;
            color: var(--vscode-descriptionForeground);
            padding: 20px;
        }

        .error {
            color: var(--vscode-errorForeground);
            padding: 10px;
            background: var(--vscode-inputValidation-errorBackground);
            border-radius: 4px;
        }

        .loading {
            text-align: center;
            padding: 20px;
            color: var(--vscode-descriptionForeground);
        }
    </style>
</head>
<body>
    <div class="search-container">
        <input type="text" id="searchInput" placeholder="Search memory..." />
        <button id="searchBtn">Search</button>
    </div>
    <div id="results" class="results">
        <div class="empty">Enter a query to search memory</div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        const searchInput = document.getElementById('searchInput');
        const searchBtn = document.getElementById('searchBtn');
        const resultsDiv = document.getElementById('results');

        function search() {
            const query = searchInput.value.trim();
            if (!query) return;

            resultsDiv.innerHTML = '<div class="loading">Searching...</div>';
            vscode.postMessage({ type: 'search', query });
        }

        searchBtn.addEventListener('click', search);
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') search();
        });

        window.addEventListener('message', (event) => {
            const message = event.data;

            switch (message.type) {
                case 'results':
                    if (message.results.length === 0) {
                        resultsDiv.innerHTML = '<div class="empty">No memories found</div>';
                    } else {
                        resultsDiv.innerHTML = message.results.map(r => \`
                            <div class="result-item" data-id="\${r.id}">
                                <div class="result-header">
                                    <span class="result-type">\${r.doc_type}</span>
                                    <span class="result-source">\${r.source}</span>
                                </div>
                                <div class="result-content">\${escapeHtml(r.content)}</div>
                            </div>
                        \`).join('');

                        document.querySelectorAll('.result-item').forEach(item => {
                            item.addEventListener('click', () => {
                                vscode.postMessage({
                                    type: 'openMemory',
                                    id: item.dataset.id
                                });
                            });
                        });
                    }
                    break;

                case 'error':
                    resultsDiv.innerHTML = \`<div class="error">\${message.message}</div>\`;
                    break;
            }
        });

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>`;
    }
}
