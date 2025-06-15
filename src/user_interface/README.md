# VS Code Graph Extension

A VS Code extension that displays an interactive graph view in the sidebar with nodes and edges.

## Installation

1. Install Node.js
2. Im this dir (`user_interface`), run `npm install` to install dependencies
2. Run `npm run compile` to build the extension. When developing run `npm run watch` so the extension is continuously re-compiled as you do changes.
3. From the debugger options (from `launch.json`) select "Run extension" and run.
4. A new window will open with the extension active. The graph view will appear in the Explorer sidebar.


## Usage

### Adding Nodes
The extension listens for messages from the backend. To add a node programmatically:

```javascript
// In GraphViewProvider
provider.addNode({
    id: 'unique-id',
    input: 'Input text',
    output: 'Output text',
    codeLocation: 'file.ts:line',
    label: 'Node Label'
});
```

### Node Interactions
- **Hover** over a node to see the action menu
- **Edit Input**: Modify the node's input string
- **Edit Output**: Modify the node's output string  
- **Change Label**: Update the node's display label
- **See in Code**: Navigate to code location

### Backend Communication
The extension sends messages to the backend when:
- A node's input, output, or label is edited
- The webview is ready to receive data

Message format:
```typescript
{
    type: 'nodeUpdated',
    payload: {
        nodeId: string,
        field: 'input' | 'output' | 'label',
        value: string
    }
}
```
