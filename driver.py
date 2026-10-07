#!/usr/bin/env python3
"""Driver helper: send one command to the relay and wait for its result.

Usage:
    python3 driver.py <relay-host> '<json-command>' [timeout_s]
    python3 driver.py <relay-host> --run '{"cmd":"ls ~/Documents","timeout":30}'

Examples:
    python3 driver.py 100.x.x.x '{"action":"snapshot","tab":"mintmobile.com"}'
    python3 driver.py 100.x.x.x '{"action":"text","tab":"mintmobile.com"}'
    python3 driver.py 100.x.x.x '{"action":"click","ref":5,"tab":"mintmobile.com"}'
    python3 driver.py 100.x.x.x '{"action":"screenshot","tab":"mintmobile.com"}' > shot.json

--run executes a shell command on the user's computer via POST /run and prints
the result. The relay must have been started with a token (--token or
AGENT_TAB_DRIVER_TOKEN); pass it via the AGENT_TAB_DRIVER_TOKEN env var:

    AGENT_TAB_DRIVER_TOKEN=secret python3 driver.py 100.x.x.x --run '{"cmd":"dir"}'

Stdlib only. Prints the result as JSON.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid


def call(host, path, obj=None, timeout=15, headers=None):
    url = f"http://{host}:8765{path}"
    data = json.dumps(obj).encode() if obj is not None else None
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(
        url, data=data, headers=hdrs,
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def run_shell(host, run_json):
    token = os.environ.get("AGENT_TAB_DRIVER_TOKEN", "")
    if not token:
        print(json.dumps({"error": "set AGENT_TAB_DRIVER_TOKEN first"}))
        sys.exit(2)
    spec = json.loads(run_json)
    timeout = float(spec.get("timeout", 30) or 30) + 15
    try:
        result = call(host, "/run", spec, timeout=timeout,
                      headers={"X-Auth-Token": token})
    except urllib.error.HTTPError as e:
        result = {"http_error": e.code, **json.loads(e.read() or b"{}")}
    print(json.dumps(result, indent=1)[:12000])


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    host = sys.argv[1]
    if sys.argv[2] == "--run":
        if len(sys.argv) < 4:
            print(__doc__)
            sys.exit(2)
        run_shell(host, sys.argv[3])
        return
    cmd_json = sys.argv[2]
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 60
    cmd = json.loads(cmd_json)
    cmd.setdefault("id", f"cmd-{uuid.uuid4().hex[:8]}")
    call(host, "/command", cmd)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        results = call(host, "/results")["results"]
        for r in results:
            if r.get("id") == cmd["id"]:
                print(json.dumps(r, indent=1)[:6000])
                return
    print(json.dumps({"error": "timed out waiting for result", "id": cmd["id"]}))
    sys.exit(1)


if __name__ == "__main__":
    main()
