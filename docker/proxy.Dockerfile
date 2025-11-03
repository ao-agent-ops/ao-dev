# WebSocket Proxy Dockerfile
FROM node:18-slim
WORKDIR /app
COPY src/user_interfaces/web_app/ /app/
RUN npm install
EXPOSE 4000
CMD ["node", "server.js"]
