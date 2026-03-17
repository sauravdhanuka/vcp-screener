#!/usr/bin/env bash
# Bootstrap VCP Screener on a fresh GCP VM
# Run on VM after SSH: bash ~/vcp-screener/deploy/vm-bootstrap.sh
set -euo pipefail

echo "=== VCP Screener VM Bootstrap ==="

# 1. Wait for Docker (installed by startup script)
echo "Waiting for Docker installation..."
while ! command -v docker &>/dev/null; do
    echo "  Docker not ready, waiting 10s..."
    sleep 10
done
echo "Docker is installed."

# Ensure current user can use docker without sudo
if ! groups | grep -q docker; then
    echo "Adding user to docker group (will take effect on next login)..."
    sudo usermod -aG docker "$USER"
    echo "Please log out and back in, then re-run this script."
    exit 1
fi

# 2. Create 2GB swap file
if [ ! -f /swapfile ]; then
    echo "Creating 2GB swap file..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap enabled."
else
    echo "Swap file already exists."
fi

# 3. Set timezone
echo "Setting timezone to Asia/Kolkata..."
sudo timedatectl set-timezone Asia/Kolkata

# 4. Clone repo
REPO_DIR="$HOME/vcp-screener"
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning repository..."
    git clone https://github.com/sauravdhanuka/vcp-screener.git "$REPO_DIR"
else
    echo "Repository already exists, pulling latest..."
    cd "$REPO_DIR" && git pull
fi

cd "$REPO_DIR"

# 5. Create .env if not exists
if [ ! -f .env ]; then
    cat > .env << 'ENVEOF'
# VCP Screener settings (override defaults via VCP_ prefix)
# VCP_ACCOUNT_SIZE=500000
# VCP_MAX_POSITIONS=6
ENVEOF
    echo ""
    echo "=========================================="
    echo "  .env file created. Edit if needed:"
    echo "  nano $REPO_DIR/.env"
    echo "=========================================="
    echo ""
fi

# 6. Build Docker images
echo "Building Docker images (this may take a few minutes)..."
docker compose build

# 7. Start services
echo "Starting all services..."
docker compose up -d

# 8. Initial data download
echo ""
echo "=========================================="
echo "  Starting initial data download."
echo "  This will take 30-60 minutes."
echo "  You can detach (Ctrl+C) and check later:"
echo "    docker compose logs -f dashboard"
echo "=========================================="
echo ""
docker compose exec dashboard vcp data download

# 9. Run initial screening
echo "Running initial screening..."
docker compose exec dashboard vcp screen run

# Get external IP
EXTERNAL_IP=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip 2>/dev/null || echo "EXTERNAL_IP")

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "  Dashboard: http://${EXTERNAL_IP}:8501"
echo "  Logs:      docker compose logs -f"
echo "  Update:    bash deploy/update.sh"
echo "=========================================="
