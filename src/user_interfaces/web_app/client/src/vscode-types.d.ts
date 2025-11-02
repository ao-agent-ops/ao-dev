interface VscodeApi {
  postMessage(message: any): void;
  getState(): any;
  setState(state: any): void;
}

declare global {
  interface Window {
    vscode?: VscodeApi;
  }
}

export {};