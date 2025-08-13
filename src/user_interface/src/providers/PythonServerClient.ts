import * as net from 'net';
import * as child_process from 'child_process';

export class PythonServerClient {
    private static instance: PythonServerClient;
    private client: net.Socket | null = null;
    private isConnected = false;
    private messageQueue: string[] = [];
    private reconnectTimeout: NodeJS.Timeout | null = null;
    private onMessageCallback: ((msg: any) => void) | null = null;

    private constructor() {
        this.connect();
    }

    public static getInstance(): PythonServerClient {
        if (!PythonServerClient.instance) {
            PythonServerClient.instance = new PythonServerClient();
        }
        return PythonServerClient.instance;
    }

    private connect() {
        this.client = new net.Socket();
        this.client.connect(5959, '127.0.0.1', () => {
            this.isConnected = true;
            // Send handshake
            this.sendRaw(JSON.stringify({
                type: "hello",
                role: "ui",
                script: "vscode-extension"
            }) + "\n");
            // Flush any queued messages
            while (this.messageQueue.length > 0) {
                this.sendRaw(this.messageQueue.shift()!);
            }
        });

        let buffer = '';
        this.client.on('data', (data) => {
            buffer += data.toString();
            let idx;
            while ((idx = buffer.indexOf('\n')) !== -1) {
                const line = buffer.slice(0, idx);
                buffer = buffer.slice(idx + 1);
                try {
                    const msg = JSON.parse(line);
                    if (this.onMessageCallback) {
                        this.onMessageCallback(msg);
                    }
                } catch (e) {
                    // Ignore parse errors
                }
            }
        });

        this.client.on('close', () => {
            this.isConnected = false;
            this.scheduleReconnect();
        });

        this.client.on('error', (err) => {
            this.isConnected = false;
            this.scheduleReconnect();
        });
    }

    private scheduleReconnect() {
        if (this.reconnectTimeout) return;
        this.reconnectTimeout = setTimeout(() => {
            this.reconnectTimeout = null;
            this.connect();
        }, 2000);
    }

    private sendRaw(message: string) {
        if (this.isConnected && this.client) {
            this.client.write(message);
        } else {
            this.messageQueue.push(message);
        }
    }

    public sendMessage(message: any) {
        const msgStr = JSON.stringify(message) + "\n";        
        this.sendRaw(msgStr);
    }

    public startServerIfNeeded() {
        // Try to connect, and if connection fails, spawn the server
        // (You can implement a more robust check here)
        const proc = child_process.spawn('python', ['src/agent_copilot/develop_server.py', 'start'], {
            detached: true,
            stdio: 'ignore'
        });
        proc.unref();
    }

    public stopServer() {
        this.sendMessage({ type: "shutdown" });
    }

    public onMessage(cb: (msg: any) => void) {
        this.onMessageCallback = cb;
    }
} 
