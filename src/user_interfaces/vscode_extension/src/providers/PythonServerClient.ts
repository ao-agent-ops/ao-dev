import * as net from 'net';
import * as child_process from 'child_process';

export class PythonServerClient {
    private static instance: PythonServerClient;
    private client: net.Socket;
    private messageQueue: string[] = [];
    private messageCallbacks: ((msg: any) => void)[] = [];
    private reconnectTimeout?: NodeJS.Timeout;
    private isConnecting: boolean = false;

    private constructor() {
        this.client = new net.Socket();
        this.connect();
    }

    public static getInstance(): PythonServerClient {
        return PythonServerClient.instance ??= new PythonServerClient();
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
            this.isConnecting = false;
            this.client.write(JSON.stringify({
                type: "hello",
                role: "ui",
                script: "vscode-extension"
            }) + "\n");
            this.messageQueue.forEach(msg => this.client.write(msg));
            this.messageQueue = [];
        });

        let buffer = '';
        this.client.on('data', (data) => {
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
            this.isConnecting = false;
            // Clear any pending reconnect
            if (this.reconnectTimeout) {
                clearTimeout(this.reconnectTimeout);
            }
            this.reconnectTimeout = setTimeout(() => this.connect(), 2000);
        });

        this.client.on('error', () => {
            // Don't call connect() again here since 'close' will also fire
            // This prevents double reconnection attempts
        });
    }

    public sendMessage(message: any) {
        const msgStr = JSON.stringify(message) + "\n";
        if (this.client.readyState === 'open') {
            this.client.write(msgStr);
        } else {
            this.messageQueue.push(msgStr);
        }
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

    public removeMessageListener(cb: (msg: any) => void) {
        const index = this.messageCallbacks.indexOf(cb);
        if (index > -1) {
            this.messageCallbacks.splice(index, 1);
        }
    }

    public dispose() {
        // Clear reconnect timeout
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = undefined;
        }

        // Clean up socket
        if (this.client) {
            this.client.removeAllListeners();
            this.client.destroy();
        }

        // Clear callbacks
        this.messageCallbacks = [];
        this.messageQueue = [];
    }
} 