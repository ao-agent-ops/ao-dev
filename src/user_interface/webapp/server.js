const express = require("express");
const { WebSocketServer } = require("ws");
const net = require("net");
const cors = require("cors");

const HOST = "127.0.0.1";   
const PORT = 5959;          
const WS_PORT = 4000;      

const app = express();
app.use(cors());
const server = app.listen(WS_PORT, () =>
  console.log(`Web proxy running on ws://localhost:${WS_PORT}`)
);

const wss = new WebSocketServer({ server });

wss.on("connection", (ws) => {
  console.log("Frontend connected");

  // connect to Python socket server
  const client = net.createConnection({ host: HOST, port: PORT }, () => {
    console.log("Connected to Python server");
    client.write(JSON.stringify({ role: "ui" }) + "\n"); // handshake
  });

  // forward Python server → browser
  client.on("data", (data) => {
    data
      .toString()
      .split("\n")
      .filter(Boolean)
      .forEach((msg) => ws.send(msg));
  });

  // forward browser → Python server
  ws.on("message", (msg) => {
    client.write(msg.toString() + "\n");
  });

  ws.on("close", () => {
    client.end();
  });
});
