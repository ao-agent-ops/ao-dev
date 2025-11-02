import * as net from 'net';
import * as child_process from 'child_process';

export class PythonServerClient {
    private static instance: PythonServerClient;
    private client = new net.Socket();
    private messageQueue: string[] = [];
    private onMessageCallback?: (msg: any) => void;

    private constructor() {
        this.connect();
    }

    public static getInstance(): PythonServerClient {
        return PythonServerClient.instance ??= new PythonServerClient();
    }

    private connect() {
        this.client.connect(5959, '127.0.0.1', () => {
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
                this.onMessageCallback?.(msg);
            }
        });

        this.client.on('close', () => {
            setTimeout(() => this.connect(), 2000);
        });

        this.client.on('error', () => {
            setTimeout(() => this.connect(), 2000);
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
        this.onMessageCallback = cb;
    }
} 