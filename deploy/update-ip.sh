#!/usr/bin/env bash
# Update GCP firewall rule for Streamlit access
#
# Usage:
#   bash deploy/update-ip.sh              # Lock to current public IP
#   bash deploy/update-ip.sh public       # Open to all IPs
#   bash deploy/update-ip.sh 79.121.202.94  # Lock to specific IP (NordVPN dedicated)
set -euo pipefail

if [ "${1:-}" = "public" ]; then
    RANGE="0.0.0.0/0"
elif [ -n "${1:-}" ]; then
    RANGE="${1}/32"
else
    RANGE="$(curl -s ifconfig.me)/32"
fi

gcloud compute firewall-rules update allow-streamlit --source-ranges="$RANGE"
echo "Firewall updated: source-ranges=$RANGE"
