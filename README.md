# Agent Tab Driver

Let your AI agent drive **your** browser, on **your** computer, from **your**
IP address.

Cloud AI browsers get flagged as datacenter traffic — sites like carriers
and banks lock the account or throw CAPTCHAs. This project flips it around:
a tiny browser extension carries out the agent's commands in your real
browser, over your own Tailscale private network. Sites see your IP, your
location, your cookies, your logged-in sessions.

> ⚠️ **Security — read first.** The browser-driving endpoints have no password;
> anyone on your Tailscale network who can reach the relay can drive your
> browser. The **shell endpoint** (`POST /run`) is token-gated: start the
> relay with `--token` (or `AGENT_TAB_DRIVER_TOKEN`) to enable it, and it
> stays disabled otherwise. Bind the relay to your Tailscale IP (never
> `0.0.0.0`), run it only while you want the agent working, and stop it
> (Ctrl+C) when you're done. See
> [user-setup.md](references/user-setup.md#safety-notes--read-these).

## How it works

```
agent --(Tailscale)--> relay.py on YOUR computer :8765
                                |
                   browser extension (polls the relay)
                                |
                            your browser tab
```

The agent queues JSON commands (`snapshot`, `click`, `type`, …); the
extension executes them in the chosen tab via `chrome.scripting` and posts
results back. Full protocol: [references/protocol.md](references/protocol.md).

## Install

Two halves — one on your computer, one on your agent.

### Part A — your computer (Windows, Mac, or Linux)

1. Install **Tailscale**, log in, connect. Run `tailscale ip` to get this
   computer's IP (looks like `100.x.x.x`).
2. Install **Python 3** (stdlib only, no packages).
3. Download this repo.
4. In `extension/background.js`, set `TAILSCALE_HOST` to your Tailscale IP
   (needed when the browser is sandboxed, e.g. HP Sure Click; harmless otherwise).
5. Load the extension: Chrome/Brave → `chrome://extensions` → **Developer
   mode** → **Load unpacked** → select `extension/`.
6. Start the relay: double-click `start-relay.bat` (Windows) or run
   `./start-relay.sh` (Mac/Linux).

Detailed walkthrough: [references/user-setup.md](references/user-setup.md).

### Part B — your agent

This repo **is** the skill. Clone it into your agent's skills folder:

```bash
git clone https://github.com/edjepaz/agent-tab-driver ~/workspace/skills/agent-tab-driver
```

Then pair the agent with your tailnet (approve its device in the Tailscale
admin console, the same as adding any device) and tell it your computer's
Tailscale IP. `SKILL.md` teaches the agent the rest: health checks,
operating rules, and the command protocol.

## Try it locally (5 minutes, no agent needed)

1. `python3 relay.py` — server on port 8765.
2. Load `extension/` unpacked in Chrome, open any web page.
3. `python3 demo.py` — queues a `snapshot`; the extension reads the tab and
   prints the elements it found.

## Project layout

| path | what | where it runs |
|---|---|---|
| `extension/` | MV3 browser extension | your computer |
| `relay.py` | command relay (stdlib-only HTTP server) | your computer |
| `relay-config.json` | your settings (host, port, token, allowlist) — gitignored, never committed | your computer |
| `relay-config.example.json` | documented template for the config | — |
| `start-relay.bat` / `start-relay.sh` | one-click relay starters | your computer |
| `driver.py` | send-a-command helper for the agent | agent's machine |
| `SKILL.md` | agent instructions (purpose, tooling, auth, rules) | agent's machine |
| `references/protocol.md` | relay HTTP API + action reference | both |
| `references/user-setup.md` | detailed setup + troubleshooting | your computer |

## Status

Working prototype (v0.6.0), proven end-to-end: an agent drove a real,
logged-in carrier account through the user's own browser and IP after the
cloud browser got fraud-blocked. v0.5.0 added an optional token-gated shell
endpoint (`POST /run`) so the agent can also run allowlisted shell commands
on the user's computer; v0.6.0 adds `relay-config.json` so all relay settings
live in one gitignored file. Not a product: no Web Store listing, no hosted
pairing service — by design, it's a personal tool you run yourself.

## Contributing & donations

Issues and PRs welcome. If this saved you from a fraud-detection headache,
consider [sponsoring](https://github.com/sponsors/edjepaz) —
it keeps the lights on for maintenance.

## License

MIT — see [LICENSE](LICENSE).
