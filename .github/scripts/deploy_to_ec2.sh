#!/usr/bin/env bash
set -euo pipefail

# Save SSH key to a temporary file (absolute path)
if [ -z "${EC2_SSH_KEY:-}" ]; then
  echo "Error: EC2_SSH_KEY is empty"
  exit 1
fi

TMPKEYDIR=$(mktemp -d)
KEYFILE="$TMPKEYDIR/ec2_key.pem"
echo "$EC2_SSH_KEY" > "$KEYFILE"
chmod 600 "$KEYFILE"

# Fail early if critical secrets are missing
if [ -z "${GOOGLE_CLIENT_ID:-}" ] || [ -z "${GOOGLE_CLIENT_SECRET:-}" ] || [ -z "${ECR_REGISTRY:-}" ]; then
  echo "Error: Missing required secrets (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, or ECR_REGISTRY). Aborting deploy."
  rm -f "$KEYFILE" || true
  exit 1
fi

WORKDIR=~/workflow-extension
mkdir -p "$WORKDIR"
cd "$WORKDIR" || exit 1

# Create docker-compose.prod.yml (variables are expanded by the runner)
cat > docker-compose.prod.yml <<'YML'
version: '3.8'

services:
  frontend:
    image: ${ECR_REGISTRY}/workflow-extension-frontend:latest
    container_name: workflow-frontend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - letsencrypt:/etc/letsencrypt
    restart: unless-stopped
    networks:
      - app-network

  backend:
    image: ${ECR_REGISTRY}/workflow-extension-backend:latest
    container_name: workflow-backend
    ports:
      - "5958:5958"
      - "5959:5959"
    environment:
      - HOST=0.0.0.0
      - PORT=5959
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - CALLBACK_URL=${CALLBACK_URL}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
      - JWT_SECRET=${JWT_SECRET}
      - USE_SECURE_COOKIES=${USE_SECURE_COOKIES}
      - VITE_API_BASE=${VITE_API_BASE}
      - FRONTEND_ORIGIN=${FRONTEND_ORIGIN}
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
    restart: unless-stopped
    networks:
      - app-network

  proxy:
    image: ${ECR_REGISTRY}/workflow-extension-proxy:latest
    container_name: workflow-proxy
    ports:
      - "4000:4000"
    environment:
      - WS_PORT=4000
      - PYTHON_PORT=5959
      - PYTHON_HOST=backend
    depends_on:
      - backend
    restart: unless-stopped
    networks:
      - app-network

networks:
  app-network:
    driver: bridge

volumes:
  letsencrypt:
YML

# Create .env with expanded values
cat > .env <<ENV
AWS_REGION=${AWS_REGION}
ECR_REGISTRY=${ECR_REGISTRY}
OPENAI_API_KEY=${OPENAI_API_KEY}
DATABASE_URL=${DATABASE_URL}
CALLBACK_URL=${CALLBACK_URL}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
JWT_SECRET=${JWT_SECRET}
USE_SECURE_COOKIES=${USE_SECURE_COOKIES}
VITE_API_BASE=${VITE_API_BASE}
FRONTEND_ORIGIN=${FRONTEND_ORIGIN}
ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
ENV

# Move files to a temp location so scp gets them
TMPDIR=$(mktemp -d)
cp docker-compose.prod.yml .env "$TMPDIR/"

# Copy nginx config from repository
cp docker/host-nginx-agops-project.conf "$TMPDIR/"

# Copy files to EC2
scp -o StrictHostKeyChecking=no -i "$KEYFILE" "$TMPDIR/docker-compose.prod.yml" "$TMPDIR/.env" "$TMPDIR/host-nginx-agops-project.conf" ${EC2_USER}@${EC2_HOST}:~/workflow-extension/

# Execute remote deploy commands (source .env on remote to export variables)
ssh -o StrictHostKeyChecking=no -i "$KEYFILE" ${EC2_USER}@${EC2_HOST} <<'REMOTE'
set -e
cd ~/workflow-extension || mkdir -p ~/workflow-extension && cd ~/workflow-extension

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# Login to ECR using configured region
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

docker-compose -f docker-compose.prod.yml pull

docker-compose -f docker-compose.prod.yml down || true

docker stop $(docker ps -q) 2>/dev/null || true

docker container prune -f || true

sudo fuser -k 80/tcp 2>/dev/null || true
sudo fuser -k 443/tcp 2>/dev/null || true
sudo fuser -k 5959/tcp 2>/dev/null || true
sudo fuser -k 4000/tcp 2>/dev/null || true
sleep 2

# Update host nginx configuration
sudo cp host-nginx-agops-project.conf /etc/nginx/conf.d/agops-project.conf
sudo nginx -t

docker-compose -f docker-compose.prod.yml up -d --force-recreate --remove-orphans

docker image prune -f

# Restart host nginx to pick up config changes and ensure it's running
sudo systemctl restart nginx
sudo systemctl status nginx --no-pager

echo "✅ Frontend, Backend, Proxy deployed and host nginx restarted on EC2."
REMOTE

# Cleanup
rm -f "$KEYFILE"
rm -rf "$TMPDIR"
rm -rf "$TMPKEYDIR"

exit 0
