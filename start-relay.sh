#!/bin/sh
# Start the agent-tab-driver relay on Mac/Linux.
# Asks for this computer's Tailscale IP once, saves it to relay-host.txt.
if [ -f relay-host.txt ]; then
  RELAY_HOST=$(cat relay-host.txt)
else
  printf "Enter this computer's Tailscale IP (run 'tailscale ip' to find it): "
  read RELAY_HOST
  echo "$RELAY_HOST" > relay-host.txt
fi
echo "Starting relay on $RELAY_HOST:8765 ..."
exec python3 relay.py --host "$RELAY_HOST"
