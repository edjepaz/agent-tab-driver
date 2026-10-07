# User-side setup

This gets *your* computer ready so your AI agent can drive *your* browser.
Nothing AI-specific runs here — just a browser extension, a tiny Python
relay, and Tailscale.

```
agent's machine --(Tailscale, TCP)--> relay.py on YOUR computer :8765
                                               |
                                  browser extension (polls the relay)
                                               |
                                           your browser tab
```

## One-time setup

1. **Tailscale** — install it, log in, and connect on the computer whose
   browser you want driven. Find its Tailscale IP by running `tailscale ip`
   (it looks like `100.x.x.x`). Note it down.
2. **Python 3** — the relay is stdlib-only, no packages to install.
   (Windows: install from python.org and tick "Add python.exe to PATH".)
3. **Download** this repo (or the release zip) somewhere handy.
4. **Set your Tailscale IP in the extension** — open
   `extension/background.js` and set `TAILSCALE_HOST` to the IP from step 1.
   (Skip this if your browser reaches `localhost` normally; it's only needed
   when something like HP Sure Click sandboxes the browser.)
5. **Load the extension** — Chrome or Brave → `chrome://extensions` (or
   `brave://extensions`) → enable **Developer mode** → **Load unpacked** →
   select the `extension/` folder. Leave it enabled only when you want the
   agent driving.

## Each time you want the agent to drive

1. Make sure Tailscale is connected.
2. Start the relay:
   - Windows: double-click `start-relay.bat`.
   - Mac/Linux: `./start-relay.sh`.
   - Or manually: `python3 relay.py` (reads `relay-config.json`; flags like
     `--host 100.x.x.x` override it).
   On first run the starter scripts create `relay-config.json` for you —
   they ask for your Tailscale IP and an optional shell token. All relay
   settings live there; see [protocol.md](protocol.md#configuration).
   - **Shell access (optional):** if you want the agent to also run shell
     commands and read files on this computer, start the relay with a token:
     `python3 relay.py --host 100.x.x.x --token SOMETHING_ONLY_YOU_KNOW`
     (or set the `AGENT_TAB_DRIVER_TOKEN` env var before double-clicking the
     starter). Tell the agent the token once per session. Without a token,
     the shell endpoint stays disabled and the agent can only drive the browser.
3. Open your browser to the page you want and make it the active tab.
   **Log in yourself** if the site needs it — the agent never sees your passwords this way.
4. Tell the agent your computer's Tailscale IP. It connects over the tailnet
   and starts issuing commands.
5. When done: stop the relay (Ctrl+C, or close the window) and optionally
   disable the extension.

## Pairing your agent with your tailnet

The agent's machine must be on the same Tailscale network as your computer.
How you do that depends on your agent — typically you approve its device
from the Tailscale admin console, the same way you'd add a phone or laptop.

## Safety notes — read these

- The browser-driving endpoints have **no password**. Anyone on your tailnet
  who can reach the port can drive your browser. Bind it to your Tailscale IP
  (never `0.0.0.0`) and run it only while you actively want driving.
- The **shell endpoint** (`POST /run`) is different: it requires the token
  you set at startup, and only programs on your allowlist may run (read-only
  by default; widen it with `--allow` or `AGENT_TAB_DRIVER_ALLOW`). The token
  is the boundary — keep it to yourself and the agent, and never commit it.
- Without the token, the agent can only touch tabs in the browser window the
  extension sees. With the token, it can also read files and run the commands
  you allow — that is the point, so enable it deliberately. Either way it
  can't see your other tabs or anything you don't allow.
- Driving is visible: you watch the tab click and type in real time. Shell
  commands are logged to the relay window and `relay-audit.log`. If anything
  looks wrong, kill the relay.
- This does not defeat all bot detection. Your IP and location now look
  right, but automation signals can still be noticed by hardened sites.

## Troubleshooting

- Relay terminal shows nothing when the extension should be polling: the
  extension isn't reaching the relay. Check it's enabled in
  `chrome://extensions` (Developer mode, Load unpacked), and that the active
  window isn't a `chrome://` page.
- Commands queue but never run: reload the extension after editing
  `background.js`; compare `extension_version` vs `relay_version` in the
  relay's `/status` output — they must match.
- HP Sure Click (or similar sandboxing) isolates the browser: `localhost`
  from the extension is the sandbox's loopback, not your machine's. Set
  `TAILSCALE_HOST` in `background.js` to your Tailscale IP. If even that
  doesn't route, use a browser outside the sandbox (Brave worked in testing).
- MV3 suspends idle service workers: the extension long-polls the relay to
  stay awake. If commands stall after a long idle, reload the extension.
