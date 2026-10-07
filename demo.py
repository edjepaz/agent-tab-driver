#!/usr/bin/env python3
"""Demo driver: queues a snapshot command and prints the tab's response.

Usage:
  1. python3 relay.py            # in one terminal
  2. Load extension/ unpacked in Chrome (chrome://extensions, developer mode)
  3. Open any web page and make it the active tab
  4. python3 demo.py             # in another terminal
"""
import json
import time
import urllib.request

RELAY = "http://127.0.0.1:8765"


def post(path, obj):
    req = urllib.request.Request(
        RELAY + path,
        data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.load(urllib.request.urlopen(req))


def get(path):
    return json.load(urllib.request.urlopen(RELAY + path))


post("/clear", {})
post("/command", {"id": "demo-1", "action": "snapshot"})
print("snapshot queued — extension should pick it up within ~2 seconds…")
for _ in range(12):
    time.sleep(1.5)
    results = get("/results")["results"]
    if results:
        print(json.dumps(results[-1], indent=2)[:2500])
        break
else:
    print("no result yet — is relay.py running and the extension loaded?")
