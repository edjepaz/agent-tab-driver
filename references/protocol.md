# Relay HTTP API

Base URL: `http://<tailscale-ip>:8765` (reached over the user's tailnet).

## Configuration

`relay.py` reads `relay-config.json` from its own folder on startup
(override with `--config <path>`). Copy `relay-config.example.json` to
`relay-config.json` and edit it — or let `start-relay.bat` / `start-relay.sh`
create it on first run. Precedence: **CLI flags > environment variables >
config file > built-in defaults**. `relay-config.json` is gitignored because
it may hold your shell token.

| key | env var | default | what |
|---|---|---|---|
| `host` | `AGENT_TAB_DRIVER_HOST` | `127.0.0.1` | interface to bind (your Tailscale IP for agent access) |
| `port` | `AGENT_TAB_DRIVER_PORT` | `8765` | port to listen on |
| `token` | `AGENT_TAB_DRIVER_TOKEN` | _(empty)_ | enables `POST /run`; empty disables it |
| `allow` | `AGENT_TAB_DRIVER_ALLOW` | read-only set | programs the agent may run via `/run` (list or `"a,b,c"`) |
| `audit_log` | `AGENT_TAB_DRIVER_AUDIT_LOG` | `relay-audit.log` | where shell invocations are logged |

`python3 relay.py --print-config` prints the resolved configuration with the
token masked — useful for debugging ("which value won?").

## Endpoints

| method | path | body | returns |
|---|---|---|---|
| `GET` | `/command?wait=25` | — | `{"command": {...} \| null}` — long-polls up to `wait` seconds (max 30). Used by the extension. |
| `POST` | `/command` | command JSON | `{"queued": n}` |
| `GET` | `/results` | — | `{"results": [...]}` — all completed results (match by `id`) |
| `POST` | `/result` | result JSON | `{"stored": n}` — used by the extension |
| `POST` | `/heartbeat` | `{"version","tabUrl","openTabs"}` | `{"ok": true}` — used by the extension |
| `GET` | `/status` | — | health: versions, queue depth, heartbeat age, open tabs, shell status |
| `POST` | `/clear` | — | `{"ok": true}` — clears queued commands and results |
| `POST` | `/run` | `{"cmd","cwd","timeout"}` | runs a shell command on the user's computer — **requires token** (see below) |

## Command envelope

```json
{
  "id": "cmd-abc123",
  "action": "click",
  "tab": "mintmobile.com",
  "ref": 5
}
```

- `id` (string, required): unique per command; the result echoes it back.
- `tab` (optional): URL substring to select a background tab, e.g. `"mintmobile.com"`. Omit (or `"active"`) for the active tab.

## Actions

| action | fields | does |
|---|---|---|
| `snapshot` | — | list interactive elements: `ref`, `sel` (CSS selector), tag, text (max 80 shown) |
| `text` | — | page's visible text (up to ~5000 chars) |
| `click` | `ref` or `sel` | click an element |
| `type` | `ref` or `sel`, `text` | focus + set value + fire input/change events |
| `select` | `ref` or `sel`, `text` | pick a dropdown option by visible text |
| `press` | `key` (default `Enter`), optional `ref`/`sel` | dispatch keydown/keypress/keyup |
| `scroll` | `ref` or `sel` | scroll element into view |
| `navigate` | `url` | go to a URL |
| `wait` | `ms` (max 15000) | pause, e.g. after a click that loads content |
| `screenshot` | optional `activate: true` | JPEG of the window's visible tab (base64 data URL) |

Elements can be addressed by snapshot `ref` (fast, but dies if the page re-renders) or by `sel` CSS selector (the snapshot returns one per element — prefer it across multiple steps).

## Result envelope

```json
{ "id": "cmd-abc123", "ok": true, "output": { ... } }
{ "id": "cmd-abc123", "ok": false, "error": "element not found — run snapshot first, or pass a \"sel\" CSS selector" }
```

Poll `GET /results` and match on `id`. `driver.py` does this for you.

## POST /run — shell command (token required)

```json
{ "cmd": "ls ~/Documents", "cwd": "/tmp", "timeout": 30 }
```

Runs the command in the user's shell and returns:

```json
{ "ok": true, "exit_code": 0, "stdout": "...", "stderr": "...",
  "truncated": false, "elapsed_s": 0.42, "timeout_error": null }
```

- **Auth:** the relay must have been started with `--token` (or
  `AGENT_TAB_DRIVER_TOKEN`); the caller sends it as the `X-Auth-Token`
  header. Without a token configured, or with a wrong one, `/run` answers
  403. The browser-driving endpoints stay tokenless by design.
- **Allowlist:** only programs on the allowlist may run, matched against the
  first word of the command (case-insensitive). Default is read-only:
  `echo, pwd, whoami, hostname, ls, dir, cat, type, more, find, findstr,
  where, which, tree, head, tail, wc, stat`. Override with `--allow` or
  `AGENT_TAB_DRIVER_ALLOW="ls,cat,python"`. The allowlist is operator
  scoping, not a sandbox — the token is the boundary.
- `timeout` defaults to 30s, max 120s. Output is capped at 64KB per stream
  (`truncated: true` when cut).
- Every invocation is logged to the relay console and `relay-audit.log`
  (timestamp, caller, exit code, command).
- `driver.py` helper:
  `AGENT_TAB_DRIVER_TOKEN=secret python3 driver.py 100.x.x.x --run '{"cmd":"dir"}'`

## Notes

- The extension long-polls `/command?wait=25` in a loop; this keeps the MV3 service worker alive (timers get suspended).
- Heartbeats arrive with every poll cycle; `/status` exposes `extension_last_seen_s_ago`, `extension_version`, `relay_version`, and the open-tabs list — the fastest way to debug "nothing happens."
- Commands queue in the relay if the extension is momentarily disconnected; check `queued` / `oldest_queued_age_s` in `/status` if results stop arriving.
