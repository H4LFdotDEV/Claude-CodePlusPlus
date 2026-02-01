import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';

export interface MemoryResult {
    id: string;
    content: string;
    doc_type: string;
    source: string;
    relevance?: number;
    tags?: string[];
    created_at?: string;
}

export interface MemoryStats {
    total_documents: number;
    components: Record<string, unknown>;
}

interface JsonRpcRequest {
    jsonrpc: '2.0';
    method: string;
    params: unknown;
    id: number;
}

interface JsonRpcResponse<T = unknown> {
    jsonrpc: '2.0';
    result?: T;
    error?: {
        code: number;
        message: string;
    };
    id: number;
}

export class McpClient extends EventEmitter {
    private process: ChildProcess | null = null;
    private command: string;
    private requestId: number = 0;
    private pendingRequests: Map<number, {
        resolve: (value: unknown) => void;
        reject: (error: Error) => void;
    }> = new Map();
    private buffer: string = '';
    private connected: boolean = false;

    constructor(command: string) {
        super();
        this.command = command;
    }

    async connect(): Promise<void> {
        if (this.connected && this.process) {
            return;
        }

        return new Promise((resolve, reject) => {
            const [cmd, ...args] = this.command.split(' ');

            this.process = spawn(cmd, args, {
                stdio: ['pipe', 'pipe', 'pipe'],
                shell: true
            });

            this.process.stdout?.on('data', (data: Buffer) => {
                this.handleData(data.toString());
            });

            this.process.stderr?.on('data', (data: Buffer) => {
                console.error('MCP stderr:', data.toString());
            });

            this.process.on('error', (error) => {
                this.connected = false;
                reject(error);
            });

            this.process.on('close', (code) => {
                this.connected = false;
                console.log(`MCP process exited with code ${code}`);
            });

            // Initialize the connection
            this.initialize()
                .then(() => {
                    this.connected = true;
                    resolve();
                })
                .catch(reject);
        });
    }

    private async initialize(): Promise<void> {
        await this.call('initialize', {
            protocolVersion: '0.1.0',
            capabilities: {},
            clientInfo: {
                name: 'caiide-memory',
                version: '0.1.0'
            }
        });
    }

    private handleData(data: string): void {
        this.buffer += data;

        // Process complete lines
        const lines = this.buffer.split('\n');
        this.buffer = lines.pop() || '';

        for (const line of lines) {
            if (!line.trim()) {
                continue;
            }

            try {
                const response = JSON.parse(line) as JsonRpcResponse;
                const pending = this.pendingRequests.get(response.id);

                if (pending) {
                    this.pendingRequests.delete(response.id);

                    if (response.error) {
                        pending.reject(new Error(response.error.message));
                    } else {
                        pending.resolve(response.result);
                    }
                }
            } catch (error) {
                console.error('Failed to parse MCP response:', line, error);
            }
        }
    }

    private async call<T>(method: string, params: unknown): Promise<T> {
        if (!this.process?.stdin) {
            throw new Error('Not connected to MCP server');
        }

        const id = ++this.requestId;
        const request: JsonRpcRequest = {
            jsonrpc: '2.0',
            method,
            params,
            id
        };

        return new Promise((resolve, reject) => {
            this.pendingRequests.set(id, {
                resolve: resolve as (value: unknown) => void,
                reject
            });

            const requestStr = JSON.stringify(request) + '\n';
            this.process!.stdin!.write(requestStr);

            // Timeout after 30 seconds
            setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    reject(new Error('Request timeout'));
                }
            }, 30000);
        });
    }

    async search(query: string, limit: number = 20): Promise<MemoryResult[]> {
        const result = await this.call<{
            content: Array<{ text: string }>;
        }>('tools/call', {
            name: 'memory_search',
            arguments: { query, limit }
        });

        if (result?.content?.[0]?.text) {
            try {
                return JSON.parse(result.content[0].text);
            } catch {
                return [];
            }
        }
        return [];
    }

    async store(
        content: string,
        type: string,
        source: string,
        tags: string[] = []
    ): Promise<string> {
        const result = await this.call<{
            content: Array<{ text: string }>;
        }>('tools/call', {
            name: 'memory_store',
            arguments: { content, type, source, tags }
        });

        return result?.content?.[0]?.text || '';
    }

    async recall(id: string): Promise<MemoryResult | null> {
        const result = await this.call<{
            content: Array<{ text: string }>;
        }>('tools/call', {
            name: 'memory_recall',
            arguments: { id }
        });

        if (result?.content?.[0]?.text) {
            try {
                return JSON.parse(result.content[0].text);
            } catch {
                return null;
            }
        }
        return null;
    }

    async list(limit: number = 20): Promise<MemoryResult[]> {
        const result = await this.call<{
            content: Array<{ text: string }>;
        }>('tools/call', {
            name: 'memory_list',
            arguments: { limit }
        });

        if (result?.content?.[0]?.text) {
            try {
                return JSON.parse(result.content[0].text);
            } catch {
                return [];
            }
        }
        return [];
    }

    async getStats(): Promise<MemoryStats> {
        const result = await this.call<{
            content: Array<{ text: string }>;
        }>('tools/call', {
            name: 'memory_stats',
            arguments: {}
        });

        if (result?.content?.[0]?.text) {
            return JSON.parse(result.content[0].text);
        }
        return { total_documents: 0, components: {} };
    }

    async delete(id: string): Promise<void> {
        await this.call('tools/call', {
            name: 'memory_delete',
            arguments: { id }
        });
    }

    disconnect(): void {
        if (this.process) {
            this.process.kill();
            this.process = null;
            this.connected = false;
        }
    }

    isConnected(): boolean {
        return this.connected;
    }
}
