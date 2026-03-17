#!/usr/bin/env bash
# Create GCP e2-micro VM for VCP Screener (free tier)
# Run from local machine: bash deploy/gcp-setup.sh
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
echo "Using GCP project: $PROJECT_ID"

ZONE="us-central1-a"
VM_NAME="vcp-screener"

# 1. Enable IAP API for SSH tunneling
echo "Enabling IAP API..."
gcloud services enable iap.googleapis.com

# 2. Create firewall rule for IAP SSH (if not exists)
if ! gcloud compute firewall-rules describe allow-iap-ssh &>/dev/null; then
    echo "Creating IAP SSH firewall rule..."
    gcloud compute firewall-rules create allow-iap-ssh \
        --direction=INGRESS \
        --priority=1000 \
        --network=default \
        --action=ALLOW \
        --rules=tcp:22 \
        --source-ranges=35.235.240.0/20 \
        --description="Allow SSH via IAP tunnel"
else
    echo "IAP SSH firewall rule already exists."
fi

# 3. Create firewall rule for Streamlit access (if not exists)
if ! gcloud compute firewall-rules describe allow-streamlit &>/dev/null; then
    echo "Creating Streamlit firewall rule..."
    echo "NOTE: To restrict access later, run: bash deploy/update-ip.sh"
    gcloud compute firewall-rules create allow-streamlit \
        --direction=INGRESS \
        --priority=1000 \
        --network=default \
        --action=ALLOW \
        --rules=tcp:8501 \
        --source-ranges="0.0.0.0/0" \
        --target-tags=streamlit-access \
        --description="Allow Streamlit dashboard access (public)"
else
    echo "Streamlit firewall rule already exists."
fi

# 4. Create VM
echo "Creating VM: $VM_NAME in $ZONE..."
gcloud compute instances create "$VM_NAME" \
    --zone="$ZONE" \
    --machine-type=e2-micro \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --tags=iap-ssh,streamlit-access \
    --metadata=startup-script='#!/bin/bash
# Auto-install Docker on first boot
if ! command -v docker &>/dev/null; then
    apt-get update
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin git
    usermod -aG docker $(ls /home/ | head -1)
    systemctl enable docker
    touch /tmp/docker-installed
fi
'

echo ""
echo "VM created! SSH into it with:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --tunnel-through-iap"
echo ""
echo "Then run: bash ~/vcp-screener/deploy/vm-bootstrap.sh"
echo ""
echo "Update your allowed IP with: bash deploy/update-ip.sh"
