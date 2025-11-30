const express = require("express");
const { WebSocketServer } = require("ws");
const net = require("net");
const cors = require("cors");
const path = require("path");


const HOST = process.env.PYTHON_HOST || "127.0.0.1";
const PORT = process.env.PYTHON_PORT ? parseInt(process.env.PYTHON_PORT) : 5959;
const WS_PORT = process.env.WS_PORT ? parseInt(process.env.WS_PORT) : 4000;

const app = express();
app.use(cors());

const server = app.listen(WS_PORT, "0.0.0.0", () =>
  console.log(`Web proxy running on ws://0.0.0.0:${WS_PORT}`)
);

const wss = new WebSocketServer({ server, path: "/ws" });

wss.on("connection", (ws, req) => {
  console.log("Frontend connected via WebSocket");

  // Extract user_id from cookies sent by the browser (httponly cookie set by auth)
  let userId = null;
  try {
    const cookieHeader = req.headers.cookie || "";
    console.log("🍪 Raw cookie header:", cookieHeader);
    cookieHeader.split(";").forEach((c) => {
      const parts = c.split("=");
      if (parts.length >= 2) {
        const key = parts[0].trim();
        const val = parts.slice(1).join("=").trim();
        console.log(`🍪 Parsed cookie: ${key} = ${val}`);
        if (key === "user_id") {
          userId = val;
          console.log(`✅ Found user_id cookie: ${userId}`);
        }
      }
    });
  } catch (e) {
    console.warn("Failed to parse cookies for user_id", e);
  }
  
  console.log(`👤 Final userId: ${userId}`);

  // connect to Python socket server
  const client = net.createConnection({ host: HOST, port: PORT }, () => {
    console.log(`Connected to Python backend at ${HOST}:${PORT}`);
    const handshake = { role: "ui" };
    if (userId) {
      // try to convert to integer, otherwise pass as string
      const n = parseInt(userId, 10);
      handshake.user_id = Number.isNaN(n) ? userId : n;
      console.log(`📤 Sending handshake with user_id: ${handshake.user_id}`);
    } else {
      console.log(`📤 Sending handshake WITHOUT user_id`);
    }
    console.log(`📤 Full handshake: ${JSON.stringify(handshake)}`);
    client.write(JSON.stringify(handshake) + "\n"); // handshake
  });

  client.on("error", (err) => {
    console.error("Error connecting to Python backend:", err);
    ws.close();
  });

  client.on("error", (err) => {
    console.error("Error connecting to Python backend:", err);
    ws.close();
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
    console.log("Frontend WebSocket closed");
    client.end();
  });

  ws.on("error", (err) => {
    console.error("WebSocket error:", err);
    client.end();
  });
});
