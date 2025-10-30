# User interfaces

We support two user interfaces:

1. VS Code extension
2. Web app

They currently display the same things. Many of the web view UI components are shared between them. Those are placed inside the `shared_components/` folder. Messaging for the extension has a caveat where the VS Code extension web views can't communicate with the server directly but must take a hop through the VS Code extension itself.


## Installation

1. Install Node.js if you haven't already.
2. In this dir (`user_interfaces/`) run `npm install` to install dependencies.

## Building and launching

### Build Everything
In `src/user_interfaces/` run `npm run build:all`

### Build VS Code Extension
In `src/user_interfaces/` run `npm run build:extension`

### Build Webapp Client
In `src/user_interfaces/` run `npm run build:webapp-client`

### Run Webapp Client

1. In `src/user_interfaces/web_app/` run `node server.js`. Keep terminal open.
2. In a another terminal, in `src/user_interfaces/` run `npm run dev:webapp-client`. Open the localhost link displayed.

### Run VS Code Extension

1. From the debugger options (from launch.json) select "Run extension" and run.
2. A new window will open with the extension active (look for the bar chart icon all the way on the left in the VS Code side panel).


## Troubleshooting

If you encounter issues:

 - **Clean install**: `npm run clean && npm install`
 - **Check workspace links**: `npm ls --workspaces`
 - **Rebuild extension**: `cd vscode_extension && npm run compile`
 - If you want to see the logs in the extension: `Cmd+P` and then type `> Developer: Toggle Developer Tools`.
 - If you want to see logs in the web app (in Google Chrome): `Right click` -> `Inspect` -> `Console`

## Graph layout
We use our custom algorithm to determine where nodes are placed in the web view pannel and where edge flow between them. [The algo can be found here.](https://drive.google.com/file/d/1eKiijfvaGs_-5sajpeqk923Xbvro7x3X/view?usp=drive_link)

