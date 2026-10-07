#!/bin/sh
# Start the agent-tab-driver relay on Mac/Linux.
# First run: creates relay-config.json (asks for your Tailscale IP and an
# optional shell token), then starts the relay with it.
if [ ! -f relay-config.json ]; then
  echo "First run — creating relay-config.json"
  printf "This computer's Tailscale IP (run 'tailscale ip' to find it): "
  read CFG_HOST
  printf "Shell token for POST /run (Enter to disable shell access): "
  read CFG_TOKEN
  cat > relay-config.json <<EOF
{
  "host": "$CFG_HOST",
  "port": 8765,
  "token": "$CFG_TOKEN",
  "audit_log": "relay-audit.log"
}
EOF
  chmod 600 relay-config.json
  echo "Wrote relay-config.json — keep it private, it may hold your token."
fi
exec python3 relay.py
