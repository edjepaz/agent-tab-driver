#!/usr/bin/env python3
"""Local command relay for the agent-tab-driver prototype.

The Chrome extension polls GET /command for work, executes it in the active
tab, and POSTs the outcome to /result. A driver (you, or a demo script) queues
commands with POST /command and reads outcomes with GET /results.

POST /run executes a shell command on this computer and returns its output.
Unlike the browser endpoints, /run requires a token (see --token), because a
shell is a much bigger deal than clicking a tab.

Stdlib only. Binds to 127.0.0.1 so nothing leaves your machine.
"""
import hmac
import json
import os
import shlex
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


def read_version():
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        return open(os.path.join(here, "VERSION")).read().strip()
    except OSError:
        return "unknown"


RELAY_VERSION = read_version()

COMMANDS = []  # queued (command, enqueued_at) tuples, oldest first
RESULTS = []   # completed results
HEARTBEAT = {"at": 0.0, "version": None, "tab_url": None, "open_tabs": []}  # last extension check-in

# NOTE: the browser-driving endpoints (/command, /result, /heartbeat, /clear)
# have no authentication — they trust the tailnet, and driving is visible in
# your browser as it happens. Only ever bind the relay to 127.0.0.1 or to your
# Tailscale IP, and only run it while you actively want the agent driving.
# Anyone who can reach the port can queue browser commands.
#
# POST /run is different: it executes shell commands on your computer, so it
# requires a token. Start the relay with --token (or set AGENT_TAB_DRIVER_TOKEN)
# to enable it; without a token, /run answers 403. The caller sends the token
# in the X-Auth-Token header. The allowlist below scopes which programs may be
# invoked — it is operator scoping, not a sandbox: the token is the boundary.

SHELL_TOKEN = os.environ.get("AGENT_TAB_DRIVER_TOKEN", "")

# Programs the agent may invoke via /run, matched against the first word of the
# command (case-insensitive, extension stripped on Windows). Override with
# --allow or AGENT_TAB_DRIVER_ALLOW="ls,cat,python". Default is read-only.
DEFAULT_ALLOW = {
    "echo", "pwd", "whoami", "hostname", "ls", "dir", "cat", "type", "more",
    "find", "findstr", "where", "which", "tree", "head", "tail", "wc", "stat",
}
RUN_ALLOW = set(
    a.strip().lower() for a in
    os.environ.get("AGENT_TAB_DRIVER_ALLOW", "").split(",") if a.strip()
) or set(DEFAULT_ALLOW)

MAX_RUN_OUTPUT = 65536  # bytes kept per stream; the rest is truncated
MAX_RUN_TIMEOUT = 120   # seconds; the caller may ask for less


def audit(line):
    """Log a shell invocation to the console and relay-audit.log."""
    msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}"
    print(msg, flush=True)
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "relay-audit.log"), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def run_first_word(cmd):
    """First program word of a command string, lowercased, extension stripped."""
    try:
        first = shlex.split(cmd, posix=(os.name != "nt"))[0]
    except (ValueError, IndexError):
        return ""
    return os.path.splitext(os.path.basename(first))[0].lower()


def check_run_auth(headers):
    if not SHELL_TOKEN:
        return "shell endpoint disabled: restart the relay with --token or set AGENT_TAB_DRIVER_TOKEN"
    presented = headers.get("X-Auth-Token", "")
    if not hmac.compare_digest(presented, SHELL_TOKEN):
        return "bad or missing X-Auth-Token"
    return ""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/command":
            # Long-poll: hold the request until a command arrives (or timeout)
            # so the extension's service worker stays awake on its fetch.
            qs = parse_qs(parsed.query)
            try:
                wait = min(float(qs.get("wait", [0])[0] or 0), 30)
            except ValueError:
                wait = 0
            deadline = time.time() + wait
            while not COMMANDS and time.time() < deadline:
                time.sleep(0.5)
            item = COMMANDS.pop(0) if COMMANDS else None
            self._send(200, {"command": item[0] if item else None})
        elif path == "/results":
            self._send(200, {"results": RESULTS})
        elif path == "/status":
            ago = time.time() - HEARTBEAT["at"] if HEARTBEAT["at"] else None
            oldest_age = round(time.time() - COMMANDS[0][1], 1) if COMMANDS else None
            self._send(200, {
                "relay_version": RELAY_VERSION,
                "queued": len(COMMANDS),
                "oldest_queued_age_s": oldest_age,
                "results": len(RESULTS),
                "extension_last_seen_s_ago": round(ago, 1) if ago is not None else None,
                "extension_version": HEARTBEAT["version"],
                "extension_tab_url": HEARTBEAT["tab_url"],
                "open_tabs": HEARTBEAT["open_tabs"],
                "shell_enabled": bool(SHELL_TOKEN),
                "shell_allow": sorted(RUN_ALLOW),
            })
        else:
            self._send(404, {"error": "unknown endpoint"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        path = urlparse(self.path).path
        if path == "/command":
            COMMANDS.append((data, time.time()))
            self._send(200, {"queued": len(COMMANDS)})
        elif path == "/result":
            RESULTS.append(data)
            self._send(200, {"stored": len(RESULTS)})
        elif path == "/heartbeat":
            HEARTBEAT.update({
                "at": time.time(),
                "version": data.get("version"),
                "tab_url": data.get("tabUrl"),
                "open_tabs": data.get("openTabs") or [],
            })
            self._send(200, {"ok": True})
        elif path == "/clear":
            COMMANDS.clear()
            RESULTS.clear()
            self._send(200, {"ok": True})
        elif path == "/run":
            err = check_run_auth(self.headers)
            if err:
                self._send(403, {"ok": False, "error": err})
                return
            cmd = data.get("cmd", "")
            if not isinstance(cmd, str) or not cmd.strip():
                self._send(400, {"ok": False, "error": "missing 'cmd' string"})
                return
            first = run_first_word(cmd)
            if first not in RUN_ALLOW:
                self._send(403, {"ok": False, "error": f"command not in allowlist: '{first}'"})
                return
            try:
                timeout = min(float(data.get("timeout", 30) or 30), MAX_RUN_TIMEOUT)
            except (TypeError, ValueError):
                self._send(400, {"ok": False, "error": "'timeout' must be a number of seconds"})
                return
            cwd = data.get("cwd")
            t0 = time.time()
            timeout_error = None
            try:
                p = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=timeout, cwd=cwd)
                out, err_out, code = p.stdout, p.stderr, p.returncode
            except subprocess.TimeoutExpired as e:
                out, err_out, code = (e.stdout or ""), (e.stderr or ""), None
                timeout_error = f"timed out after {timeout:g}s"
            except (OSError, ValueError) as e:
                self._send(400, {"ok": False, "error": str(e)})
                return
            elapsed = round(time.time() - t0, 2)
            truncated = False
            if len(out) > MAX_RUN_OUTPUT:
                out = out[:MAX_RUN_OUTPUT]
                truncated = True
            if len(err_out) > MAX_RUN_OUTPUT:
                err_out = err_out[:MAX_RUN_OUTPUT]
                truncated = True
            audit(f"RUN from {self.client_address[0]} exit={code} cmd={cmd!r}")
            self._send(200, {
                "ok": True,
                "exit_code": code,
                "stdout": out,
                "stderr": err_out,
                "truncated": truncated,
                "elapsed_s": elapsed,
                "timeout_error": timeout_error,
            })
        else:
            self._send(404, {"error": "unknown endpoint"})

    def log_message(self, fmt, *args):
        print(f"{self.command} {self.path}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1",
                    help="interface to bind (127.0.0.1, or your Tailscale IP to let the agent reach it)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--token", default="",
                    help="enable POST /run (shell commands) with this token; "
                         "or set AGENT_TAB_DRIVER_TOKEN. Without a token, /run is disabled.")
    ap.add_argument("--allow", default="",
                    help="comma-separated programs the agent may run via /run; "
                         "or set AGENT_TAB_DRIVER_ALLOW. Default is a read-only set.")
    args = ap.parse_args()
    if args.token:
        SHELL_TOKEN = args.token
    if args.allow:
        RUN_ALLOW.clear()
        RUN_ALLOW.update(a.strip().lower() for a in args.allow.split(",") if a.strip())
    print(f"relay listening on http://{args.host}:{args.port}")
    if SHELL_TOKEN:
        print(f"POST /run enabled, allowlist: {', '.join(sorted(RUN_ALLOW))}")
        print("Shell invocations are logged to the console and relay-audit.log")
    else:
        print("POST /run disabled (no --token / AGENT_TAB_DRIVER_TOKEN)")
    HTTPServer((args.host, args.port), Handler).serve_forever()
