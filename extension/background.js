// Agent Tab Driver — background service worker (prototype).
// Polls the local relay for commands, runs them in a chosen tab via
// chrome.scripting, and posts results back. Nothing leaves your machine
// except through your own Tailscale network to your own agent.

const VERSION = "0.4.0";
// Bases to try in order. localhost works in a normal browser; if HP Sure Click
// (or similar) sandboxes the browser, localhost is the sandbox's own loopback,
// so fall back to this machine's Tailscale IP — SET YOURS HERE before loading.
// Find it with: tailscale ip   (looks like 100.x.x.x)
const TAILSCALE_HOST = "100.x.x.x";
const RELAY_BASES = [`http://127.0.0.1:8765`, `http://${TAILSCALE_HOST}:8765`];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Try each relay base in order, return the first fetch that succeeds.
async function relayFetch(path, options) {
  let lastErr = null;
  for (const base of RELAY_BASES) {
    try {
      return await fetch(`${base}${path}`, options);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr;
}

// Heartbeat so the driver can see the extension is alive, which version it
// runs, and what tabs are open — invaluable for remote debugging.
async function heartbeat() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const tabs = await chrome.tabs.query({});
    await relayFetch(`/heartbeat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        version: VERSION,
        tabUrl: tab ? tab.url : null,
        openTabs: tabs
          .filter((t) => t.url && !t.url.startsWith("chrome://") && !t.url.startsWith("brave://"))
          .map((t) => ({ url: t.url, title: (t.title || "").slice(0, 60) })),
      }),
    });
  } catch (e) {
    // relay not running — skip quietly
  }
}

// Pick which tab a command runs in. Pass {"tab": "mintmobile.com"} (or any
// URL substring) to drive a background tab; omit it (or use "active") for
// the currently active tab.
async function resolveTab(cmd) {
  if (cmd.tab && cmd.tab !== "active") {
    const tabs = await chrome.tabs.query({});
    const match = tabs.find((t) => t.url && t.url.includes(cmd.tab));
    if (match) return match;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function runCommand(cmd) {
  const tab = await resolveTab(cmd);
  let result;
  if (!tab) {
    result = { id: cmd.id, ok: false, error: "no matching tab" };
  } else if (cmd.action === "wait") {
    const ms = Math.min(cmd.ms || 1000, 15000);
    await sleep(ms);
    result = { id: cmd.id, ok: true, output: { waited_ms: ms } };
  } else if (cmd.action === "screenshot") {
    // Captures the window's VISIBLE tab — for a background tab, activate it
    // first (pass {"tab": ...} plus "activate": true).
    try {
      if (cmd.activate && !tab.active) await chrome.tabs.update(tab.id, { active: true });
      await sleep(400);
      const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, {
        format: "jpeg",
        quality: 60,
      });
      result = { id: cmd.id, ok: true, output: { tabUrl: tab.url, screenshot: dataUrl } };
    } catch (err) {
      result = { id: cmd.id, ok: false, error: String((err && err.message) || err) };
    }
  } else {
    try {
      const injected = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: executeInPage,
        args: [cmd],
      });
      result = { id: cmd.id, ok: true, output: injected[0].result };
    } catch (err) {
      result = { id: cmd.id, ok: false, error: String((err && err.message) || err) };
    }
  }
  await relayFetch(`/result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(result),
  });
}

// This function is serialized and executed INSIDE the web page.
function executeInPage(cmd) {
  function cssPath(el) {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.body && parts.length < 8) {
      let name = node.tagName.toLowerCase();
      if (node.id) {
        parts.unshift("#" + CSS.escape(node.id));
        break;
      }
      const parent = node.parentNode;
      if (parent) {
        const sibs = [...parent.children].filter((c) => c.tagName === node.tagName);
        if (sibs.length > 1) name += `:nth-of-type(${sibs.indexOf(node) + 1})`;
      }
      parts.unshift(name);
      node = node.parentNode;
    }
    return parts.join(" > ");
  }

  function tagRef(el, i) {
    el.dataset.agentRef = i;
    return i;
  }

  // Elements can be addressed by snapshot ref, or directly by a CSS selector
  // (the snapshot also returns one per element, which survives re-renders).
  function findEl(cmd) {
    if (cmd.sel) {
      try {
        return document.querySelector(cmd.sel);
      } catch (e) {
        return null;
      }
    }
    if (cmd.ref !== undefined && cmd.ref !== null) {
      return document.querySelector(`[data-agent-ref="${cmd.ref}"]`);
    }
    return null;
  }

  function elLabel(cmd) {
    return cmd.ref !== undefined && cmd.ref !== null ? cmd.ref : cmd.sel;
  }

  if (cmd.action === "snapshot") {
    const els = [...document.querySelectorAll(
      "a, button, input, select, textarea, [role=button]"
    )].slice(0, 80);
    return {
      url: location.href,
      title: document.title,
      elements: els.map((el, i) => ({
        ref: tagRef(el, i),
        sel: cssPath(el),
        tag: el.tagName.toLowerCase(),
        type: el.type || null,
        text: (el.innerText || el.value || el.getAttribute("aria-label") || "").trim().slice(0, 80),
        name: el.name || el.id || null,
      })),
    };
  }

  if (cmd.action === "navigate") {
    location.href = cmd.url;
    return { navigating: cmd.url };
  }

  if (cmd.action === "text") {
    const text = (document.body.innerText || "").replace(/\n{3,}/g, "\n\n").trim();
    return { url: location.href, title: document.title, text: text.slice(0, 5000) };
  }

  const needsEl = ["click", "type", "select", "scroll"].includes(cmd.action);
  const el = findEl(cmd);
  if (needsEl && !el) {
    return { error: `element not found — run snapshot first, or pass a "sel" CSS selector` };
  }

  if (cmd.action === "click") {
    el.click();
    return { clicked: elLabel(cmd) };
  }
  if (cmd.action === "type") {
    el.focus();
    el.value = cmd.text;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return { typed: elLabel(cmd), chars: String(cmd.text).length };
  }
  if (cmd.action === "select") {
    const wanted = String(cmd.text).toLowerCase();
    const opt = [...el.options].find((o) => o.text.trim().toLowerCase().includes(wanted));
    if (!opt) return { error: `no option matching "${cmd.text}"` };
    el.value = opt.value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return { selected: opt.text.trim() };
  }
  if (cmd.action === "scroll") {
    el.scrollIntoView({ block: "center", behavior: "instant" });
    return { scrolled: elLabel(cmd) };
  }
  if (cmd.action === "press") {
    const target = el || document.activeElement || document.body;
    const key = cmd.key || "Enter";
    for (const type of ["keydown", "keypress", "keyup"]) {
      target.dispatchEvent(new KeyboardEvent(type, { key, code: key, bubbles: true }));
    }
    return { pressed: key };
  }
  return { error: `unknown action: ${cmd.action}` };
}

// Long-poll loop instead of setInterval: MV3 suspends service workers that
// look idle, which kills timers. An in-flight fetch keeps the worker alive,
// and commands queue safely in the relay if the worker ever restarts.
(async function loop() {
  for (;;) {
    try {
      await heartbeat();
      const res = await relayFetch(`/command?wait=25`);
      const { command } = await res.json();
      if (command) await runCommand(command);
    } catch (e) {
      await sleep(2000); // relay not running — back off quietly
    }
  }
})();
