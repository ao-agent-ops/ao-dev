import * as net from 'net';
import * as child_process from 'child_process';
import * as vscode from 'vscode';

export class PythonServerClient {
    private static instance: PythonServerClient;
    private client: any = undefined;
    private messageQueue: string[] = [];
    private onMessageCallback?: (msg: any) => void;
    private messageCallbacks: ((msg: any) => void)[] = [];
    private connectionCallbacks: (() => void)[] = [];
    private userId?: string;
    private serverHost: string;
    private serverPort: number;
    private serverUrl?: string;
    private useWebSocket = false;
    private reconnecting = false;
    private reconnectTimer: NodeJS.Timeout | undefined;

    private constructor() {
        // Read server configuration from VSCode settings
        const config = vscode.workspace.getConfiguration('ao');
        this.serverHost = config.get('pythonServerHost') || '127.0.0.1';
        this.serverPort = config.get('pythonServerPort') || 5959;
        this.serverUrl = config.get('pythonServerUrl');
        this.useWebSocket = !!(this.serverUrl && typeof this.serverUrl === 'string' && this.serverUrl.startsWith('ws'));

        // Don't auto-connect - let the extension control when to connect
        // after setting user_id
    }

    public static getInstance(): PythonServerClient {
        return PythonServerClient.instance ??= new PythonServerClient();
    }

    public setUserId(userId: string | undefined) {
        this.userId = userId;
    }

    public async ensureConnected() {
        if (!this.client) {
            // Check for authentication before connecting
            try {
                const vscode = await import('vscode');
                const session = await vscode.authentication.getSession('google', [], { createIfNone: false });
                if (session) {
                    this.userId = session.account.id;
                }
            } catch (error) {
                // Authentication check failed, continue without user_id
                console.error('Failed to check authentication before connection:', error);
            }
            this.connect();
        }
    }

    private connect() {
        // Clean up existing client before reconnecting
        if (this.client) {
            this.client.removeAllListeners();
            this.client.destroy();
        }
        
        // Create a new socket for each connection attempt
        this.client = new net.Socket();
        
        this.client.connect(5959, '127.0.0.1', () => {
            this.reconnecting = false;
            
            const handshake: any = {
                type: "hello",
                role: "ui",
                script: "vscode-extension"
            };

            // Add user_id to handshake if authenticated
            if (this.userId) {
                handshake.user_id = this.userId;
            }

            this.client.write(JSON.stringify(handshake) + "\n");
            this.messageQueue.forEach(msg => this.client.write(msg));
            this.messageQueue = [];

            // Notify connection listeners (e.g., to request experiment list)
            this.connectionCallbacks.forEach(callback => callback());
        });

        let buffer = '';
        this.client.on('data', (data: Buffer) => {
            buffer += data.toString();
            let idx;
            while ((idx = buffer.indexOf('\n')) !== -1) {
                const line = buffer.slice(0, idx);
                buffer = buffer.slice(idx + 1);
                const msg = JSON.parse(line);
                // Call all registered callbacks
                this.messageCallbacks.forEach(callback => callback(msg));
            }
        });

        this.client.on('close', () => {
            this.reconnecting = false;
            // Clear any pending reconnect
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
            }
            // Use ensureConnected for reconnections to check auth first
            this.reconnectTimer = setTimeout(() => this.ensureConnected(), 2000);
        });

        this.client.on('error', () => {
            // Don't call connect() again here since 'close' will also fire
            // This prevents double reconnection attempts
        });
    }

    public sendMessage(message: any) {
        const msgStr = JSON.stringify(message) + "\n";
        // WebSocket client (ws) has send() and numeric readyState
        if (this.client) {
            // WebSocket
            if (typeof this.client.send === 'function') {
                const isOpen = (typeof this.client.readyState === 'number' && this.client.readyState === 1); // 1 === OPEN
                if (isOpen) {
                    try { this.client.send(msgStr); } catch (e) { this.messageQueue.push(msgStr); }
                } else {
                    this.messageQueue.push(msgStr);
                }
                return;
            }

            // TCP socket (net.Socket)
            if (typeof this.client.write === 'function') {
                if (this.client.writable) {
                    try { this.client.write(msgStr); } catch (e) { this.messageQueue.push(msgStr); }
                } else {
                    this.messageQueue.push(msgStr);
                }
                return;
            }
        }

        // fallback: queue message
        this.messageQueue.push(msgStr);
    }

    public startServerIfNeeded() {
        child_process.spawn('python', ['src/server/develop_server.py', 'start'], {
            detached: true,
            stdio: 'ignore'
        }).unref();
    }

    public stopServer() {
        this.sendMessage({ type: "shutdown" });
    }

    public onMessage(cb: (msg: any) => void) {
        this.messageCallbacks.push(cb);
    }

    public onConnection(cb: () => void) {
        this.connectionCallbacks.push(cb);
    }

    public removeMessageListener(cb: (msg: any) => void) {
        const index = this.messageCallbacks.indexOf(cb);
        if (index > -1) {
            this.messageCallbacks.splice(index, 1);
        }
    }

    public dispose() {
        // Clear reconnect timeout
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = undefined;
        }

        // Clean up socket
        if (this.client) {
            this.client.removeAllListeners();
            this.client.destroy();
        }

        // Clear callbacks
        this.messageCallbacks = [];
        this.connectionCallbacks = [];
        this.messageQueue = [];
    }

    private scheduleReconnect() {
        if (this.reconnecting) {
            return; // Already scheduled
        }
        
        this.reconnecting = true;
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnecting = false;
            this.reconnectTimer = undefined;
            this.connect();
        }, 2000);
    }
} 