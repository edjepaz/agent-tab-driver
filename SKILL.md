---
name: "agent-tab-driver"
description: "Drive the user's own browser (Chrome/Brave) on their computer via a small local relay over Tailscale, so websites see the user's IP, location, cookies, and sessions instead of a datacenter. Use when a site blocks or flags the cloud browser, or when the user asks you to operate their browser."
---

# Agent Tab Driver

## Purpose

Operate the user's real browser on their own computer through a relay they run (`relay.py`) plus a browser extension they installed (`extension/`). Websites see the user's residential IP, geolocation, cookies, and logged-in sessions — the fix for datacenter-IP fraud blocks.

## Tooling

- The relay listens on the user's computer at `http://<tailscale-ip>:8765`. Get the Tailscale IP from the user (looks like `100.x.x.x`).
- Reach it over the user's tailnet. Your runtime needs a route to their Tailscale network — check your Tailscale setup docs/skill for the current pattern.
- `driver.py` sends one command and waits for the result:
  `python3 driver.py <tailscale-ip> '{"action":"snapshot","tab":"example.com"}'`
- Full HTTP API in `references/protocol.md`.
- Health check first: `GET /status` — confirm `relay_version` and `extension_version` match and `extension_last_seen_s_ago` is small (a few seconds). If the heartbeat is stale, the extension isn't polling: ask the user to check the relay is running and the extension is enabled.

## Auth

The browser-driving endpoints have **no password** — they trust the tailnet. Prerequisites, all on the user's side:

1. Tailscale installed and connected on their computer; your runtime must share their tailnet.
2. `relay.py` running, bound to their Tailscale IP (`python3 relay.py --host 100.x.x.x`, or the `start-relay` script).
3. The extension loaded unpacked in Chrome/Brave (`chrome://extensions` → Developer mode → Load unpacked → `extension/`) and enabled.

Relay settings (bind IP, port, shell token, allowlist) live in
`relay-config.json` next to `relay.py` on the user's computer — see
`references/protocol.md#configuration`. If the user reports the relay
misbehaving, ask them to run `python3 relay.py --print-config` and tell you
the `from` fields (the token prints masked).

The user starts/stops the relay when they want driving. Never ask them to expose the port beyond the tailnet.

## Shell access (optional, token-gated)

If the user started the relay with a token, `POST /run` runs a shell command on their computer:

```
curl -s -H "X-Auth-Token: $AGENT_TAB_DRIVER_TOKEN" -H "Content-Type: application/json" \
  -d '{"cmd":"ls ~/Documents","timeout":30}' http://<tailscale-ip>:8765/run
```

or `AGENT_TAB_DRIVER_TOKEN=... python3 driver.py <tailscale-ip> --run '{"cmd":"dir"}'`.

- Check `/status` first: `shell_enabled` tells you whether the token is configured; `shell_allow` lists permitted programs (read-only by default).
- Ask the user for the token once per session. Keep it in the session only — never write it to a file, a repo, or memory.
- Operating rules for shell: narrate before running anything; prefer reading over changing; never run destructive commands (delete, format, shutdown, registry/system changes) without explicit confirmation for that exact command.

## Operating Rules

1. Confirm the relay is up (`/status`, fresh heartbeat) before issuing commands.
2. Tell the user what you're about to do in their browser before doing it; narrate as you go. Never drive silently.
3. Read-only first: `snapshot`/`text` before any `click`/`type`/`navigate`.
4. Never enter credentials — ask the user to log in themselves, then drive the logged-in session.
5. Never change account settings, submit purchases, or send messages without explicit confirmation for that exact action.
6. Prefer `sel` (CSS selector from the snapshot) over `ref` across multiple steps; re-snapshot after navigation or re-renders.
7. When done, remind the user they can stop the relay (Ctrl+C) and disable the extension.
