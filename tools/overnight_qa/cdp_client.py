r"""
cdp_client.py - Pure-Python Chrome DevTools Protocol (CDP) client over WebSocket (RFC 6455).

Zero external dependencies (uses Python stdlib only). Connects to Edge WebView2
inside a running FramePilot.exe launched with:
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=<port>

Capabilities:
- Passively captures JS exceptions, unhandled promise rejections, console.error,
  Log.entryAdded, and failed HTTP requests (e.g., 127.0.0.1 media server 4xx/5xx).
- Injects a non-invasive API Spy around window.pywebview.api & window.onEvent
  with an optional hard READONLY guard blocking DaVinci write APIs.
- Evaluates JS expressions (including async Promises), dispatches real keyboard
  events (with event.code), and captures WebView2 screenshots via CDP.
"""
import base64
import json
import os
import socket
import struct
import threading
import time
import urllib.parse
import urllib.request

# APIs that mutate DaVinci Resolve or persistent user config — blocked in READONLY mode.
WRITE_APIS = (
    "apply",
    "inout_write",
    "append_starred",
    "dur_create_timeline",
    "cache_clear",
    "settings_save",
    "save_template",
)


class CDPError(RuntimeError):
    """Raised when a CDP command fails or times out."""


def discover_targets(port: int, timeout: float = 1.0):
    """Return list of CDP targets from http://127.0.0.1:<port>/json/list."""
    url = f"http://127.0.0.1:{port}/json/list"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_for_page_target(port: int, timeout: float = 25.0, proc=None):
    """Wait until FramePilot's WebView2 page target appears on CDP port."""
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            raise CDPError(f"FramePilot.exe thoát sớm trước khi mở CDP (exit code={proc.returncode})")
        try:
            targets = discover_targets(port, timeout=0.5)
            for t in targets:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return t
        except Exception as e:
            last_err = e
        time.sleep(0.35)
    raise CDPError(f"Hết giờ ({timeout:.0f}s) chờ cổng CDP 127.0.0.1:{port} (lỗi cuối: {last_err})")


class CDPClient:
    """Minimal, thread-safe RFC 6455 WebSocket client for Chrome DevTools Protocol."""

    def __init__(self, ws_url: str, timeout: float = 10.0):
        self.ws_url = ws_url
        self._sock = None
        self._send_lock = threading.Lock()
        self._id_lock = threading.Lock()
        self._next_id = 1
        self._pending = {}  # id -> (threading.Event, dict_holder)
        self._closed = threading.Event()
        self._reader_thread = None

        # Collected passive diagnostics (thread-safe via _evt_lock)
        self._evt_lock = threading.Lock()
        self.js_exceptions = []
        self.console_errors = []
        self.network_errors = []
        self.log_errors = []

        self._connect(timeout=timeout)

    def _connect(self, timeout: float):
        parsed = urllib.parse.urlparse(self.ws_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 9222
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(None)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(req.encode("ascii"))

        resp = b""
        sock.settimeout(timeout)
        while b"\r\n\r\n" not in resp:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise CDPError("WebSocket handshake bị đóng sớm")
            resp += chunk
        sock.settimeout(None)

        status_line = resp.split(b"\r\n", 1)[0]
        if b"101" not in status_line:
            sock.close()
            raise CDPError(f"WebSocket handshake thất bại: {status_line!r}")

        self._sock = sock
        leftover = resp.split(b"\r\n\r\n", 1)[1]
        self._reader_thread = threading.Thread(
            target=self._read_loop, args=(leftover,), daemon=True, name="cdp-reader"
        )
        self._reader_thread.start()

    def _send_frame(self, opcode: int, payload: bytes):
        mask = os.urandom(4)
        header = bytearray([0x80 | (opcode & 0x0F)])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", n))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", n))
        header.extend(mask)
        masked = bytes(b ^ mask[i & 3] for i, b in enumerate(payload))
        with self._send_lock:
            if self._closed.is_set() or self._sock is None:
                raise CDPError("CDP WebSocket đã đóng")
            self._sock.sendall(bytes(header) + masked)

    def _read_loop(self, initial_buf: bytes):
        buf = bytearray(initial_buf)

        def read_exact(k: int) -> bytes:
            while len(buf) < k:
                chunk = self._sock.recv(65536)
                if not chunk:
                    raise EOFError("WebSocket closed")
                buf.extend(chunk)
            out = bytes(buf[:k])
            del buf[:k]
            return out

        frag_chunks = []
        frag_opcode = None
        try:
            while not self._closed.is_set():
                b1, b2 = read_exact(2)
                fin = bool(b1 & 0x80)
                opcode = b1 & 0x0F
                masked = bool(b2 & 0x80)
                length = b2 & 0x7F
                if length == 126:
                    length = struct.unpack("!H", read_exact(2))[0]
                elif length == 127:
                    length = struct.unpack("!Q", read_exact(8))[0]
                mask_key = read_exact(4) if masked else None
                payload = read_exact(length)
                if mask_key:
                    payload = bytes(b ^ mask_key[i & 3] for i, b in enumerate(payload))

                if opcode == 0x8:  # close
                    break
                if opcode == 0x9:  # ping -> pong
                    try:
                        self._send_frame(0xA, payload)
                    except Exception:
                        pass
                    continue
                if opcode == 0xA:  # pong
                    continue

                if opcode == 0x0:
                    frag_chunks.append(payload)
                    if fin:
                        full = b"".join(frag_chunks)
                        frag_chunks.clear()
                        if frag_opcode == 0x1:
                            self._handle_message(full.decode("utf-8", errors="replace"))
                        frag_opcode = None
                elif opcode == 0x1:
                    if fin:
                        self._handle_message(payload.decode("utf-8", errors="replace"))
                    else:
                        frag_opcode = 0x1
                        frag_chunks = [payload]
        except Exception:
            pass
        finally:
            self._closed.set()
            # Wake up any pending callers
            with self._id_lock:
                for ev, holder in self._pending.values():
                    holder["error"] = "CDP connection closed"
                    ev.set()
                self._pending.clear()

    def _handle_message(self, text: str):
        try:
            msg = json.loads(text)
        except ValueError:
            return
        if "id" in msg:
            cid = msg["id"]
            with self._id_lock:
                pair = self._pending.pop(cid, None)
            if pair is not None:
                ev, holder = pair
                holder["msg"] = msg
                ev.set()
            return

        method = msg.get("method", "")
        params = msg.get("params") or {}
        ts = time.time()
        with self._evt_lock:
            if method == "Runtime.exceptionThrown":
                det = params.get("exceptionDetails") or {}
                exc = det.get("exception") or {}
                desc = exc.get("description") or det.get("text") or "Unhandled JS exception"
                self.js_exceptions.append({
                    "ts": ts,
                    "text": str(desc)[:1500],
                    "url": det.get("url", ""),
                    "line": det.get("lineNumber"),
                    "col": det.get("columnNumber"),
                })
            elif method == "Runtime.consoleAPICalled":
                ctype = params.get("type", "")
                if ctype in ("error", "assert"):
                    args = params.get("args") or []
                    rendered = " ".join(
                        str(a.get("value") if "value" in a else a.get("description", ""))
                        for a in args
                    )
                    self.console_errors.append({"ts": ts, "type": ctype, "text": rendered[:1200]})
            elif method == "Log.entryAdded":
                entry = params.get("entry") or {}
                if entry.get("level") == "error":
                    self.log_errors.append({
                        "ts": ts,
                        "source": entry.get("source", ""),
                        "text": str(entry.get("text", ""))[:1200],
                        "url": entry.get("url", ""),
                    })
            elif method == "Network.loadingFailed":
                err_text = params.get("errorText", "")
                # Ignore benign aborts from rapid clip switching / canceled range requests
                if not params.get("canceled") and "ERR_ABORTED" not in err_text:
                    self.network_errors.append({
                        "ts": ts,
                        "kind": "loadingFailed",
                        "error": err_text,
                        "type": params.get("type", ""),
                    })
            elif method == "Network.responseReceived":
                resp = params.get("response") or {}
                status = int(resp.get("status") or 0)
                if status >= 400:
                    self.network_errors.append({
                        "ts": ts,
                        "kind": "http_error",
                        "status": status,
                        "url": str(resp.get("url", ""))[:300],
                    })

    def send(self, method: str, params=None, timeout: float = 15.0):
        """Send a CDP command and wait for its result."""
        if self._closed.is_set():
            raise CDPError("CDP đã đóng kết nối")
        ev = threading.Event()
        holder = {}
        with self._id_lock:
            cid = self._next_id
            self._next_id += 1
            self._pending[cid] = (ev, holder)
        payload = json.dumps({"id": cid, "method": method, "params": params or {}}).encode("utf-8")
        self._send_frame(0x1, payload)
        if not ev.wait(timeout=timeout):
            with self._id_lock:
                self._pending.pop(cid, None)
            raise CDPError(f"CDP timeout ({timeout:.1f}s) khi gọi {method}")
        if "error" in holder:
            raise CDPError(holder["error"])
        msg = holder.get("msg") or {}
        if "error" in msg:
            raise CDPError(f"CDP {method} lỗi: {msg['error']}")
        return msg.get("result") or {}

    def enable_domains(self):
        """Enable Runtime, Log, Network, and Page domains for passive error collection."""
        for m in ("Runtime.enable", "Log.enable", "Network.enable", "Page.enable"):
            try:
                self.send(m, timeout=5.0)
            except Exception:
                pass

    def eval_js(self, expression: str, await_promise: bool = True, timeout: float = 20.0):
        """Evaluate JS expression and return its JSON-serializable value."""
        res = self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
            },
            timeout=timeout,
        )
        if "exceptionDetails" in res:
            det = res["exceptionDetails"]
            exc = det.get("exception") or {}
            raise CDPError(f"JS exception: {exc.get('description') or det.get('text')}")
        return (res.get("result") or {}).get("value")

    def screenshot(self, path: str, timeout: float = 10.0) -> bool:
        """Capture PNG screenshot of WebView2 directly via CDP (works even if occluded)."""
        try:
            res = self.send("Page.captureScreenshot", {"format": "png"}, timeout=timeout)
            b64 = res.get("data")
            if not b64:
                return False
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
            return True
        except Exception:
            return False

    def dispatch_key(self, code: str, key: str, vk: int, shift: bool = False, ctrl: bool = False):
        """Dispatch rawKeyDown + keyUp via CDP Input domain (preserves event.code cleanly)."""
        mods = (8 if shift else 0) | (2 if ctrl else 0)
        base = {
            "code": code,
            "key": key,
            "windowsVirtualKeyCode": vk,
            "nativeVirtualKeyCode": vk,
            "modifiers": mods,
        }
        self.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", **base}, timeout=5.0)
        time.sleep(0.04)
        self.send("Input.dispatchKeyEvent", {"type": "keyUp", **base}, timeout=5.0)

    def install_api_spy(self, readonly: bool = True):
        """Wrap window.pywebview.api & window.onEvent to record calls, timings, errors,
        and enforce a hard READONLY guard blocking DaVinci write APIs."""
        blocked_json = json.dumps(list(WRITE_APIS) if readonly else [])
        js = f"""
        (() => {{
            if (window.__QA_SPY_INSTALLED__) return {{ already: true, apiCount: Object.keys(window.pywebview?.api || {{}}).length }};
            const BLOCKED = new Set({blocked_json});
            const RING_MAX = 60;
            window.__QA_RING__ = [];
            window.__QA_API_ERRORS__ = [];
            window.__QA_SLOW_CALLS__ = [];
            window.__QA_BLOCKED_ATTEMPTS__ = [];

            function pushRing(entry) {{
                window.__QA_RING__.push(entry);
                if (window.__QA_RING__.length > RING_MAX) window.__QA_RING__.shift();
            }}
            function preview(v) {{
                try {{
                    const s = JSON.stringify(v);
                    return s && s.length > 180 ? s.slice(0, 180) + "..." : s;
                }} catch (_) {{ return String(v).slice(0, 120); }}
            }}

            const apiObj = window.pywebview && window.pywebview.api;
            if (!apiObj) return {{ error: "window.pywebview.api not ready" }};

            const wrappedCount = {{ n: 0 }};
            for (const name of Object.keys(apiObj)) {{
                if (typeof apiObj[name] !== "function") continue;
                const orig = apiObj[name].bind(apiObj);
                apiObj[name] = async function(...args) {{
                    const t0 = performance.now();
                    if (BLOCKED.has(name)) {{
                        const rec = {{ ts: Date.now(), fn: name, args: preview(args), blocked: true }};
                        window.__QA_BLOCKED_ATTEMPTS__.push(rec);
                        pushRing({{ kind: "api_blocked", ...rec }});
                        return {{ error: "[QA_READONLY_GUARD] Đã chặn lệnh ghi: " + name, _qa_blocked: true }};
                    }}
                    try {{
                        const res = await orig(...args);
                        const ms = Math.round(performance.now() - t0);
                        const hasErr = !!(res && typeof res === "object" && res.error);
                        pushRing({{ kind: "api", ts: Date.now(), fn: name, ms, ok: !hasErr, args: preview(args), res: hasErr ? preview(res) : undefined }});
                        if (hasErr) {{
                            window.__QA_API_ERRORS__.push({{ ts: Date.now(), fn: name, ms, args: preview(args), error: String(res.error).slice(0, 400) }});
                        }}
                        if (ms > 15000) {{
                            window.__QA_SLOW_CALLS__.push({{ ts: Date.now(), fn: name, ms, args: preview(args) }});
                        }}
                        return res;
                    }} catch (e) {{
                        const ms = Math.round(performance.now() - t0);
                        const err = String(e && e.stack || e).slice(0, 500);
                        pushRing({{ kind: "api_throw", ts: Date.now(), fn: name, ms, args: preview(args), err }});
                        window.__QA_API_ERRORS__.push({{ ts: Date.now(), fn: name, ms, args: preview(args), error: "THROW: " + err }});
                        throw e;
                    }}
                }};
                wrappedCount.n++;
            }}

            if (typeof window.onEvent === "function") {{
                const origOnEvent = window.onEvent;
                window.onEvent = function(kind, data) {{
                    pushRing({{ kind: "event", ts: Date.now(), event: kind, data: preview(data) }});
                    try {{
                        return origOnEvent.apply(this, arguments);
                    }} catch (e) {{
                        window.__QA_API_ERRORS__.push({{ ts: Date.now(), fn: "onEvent:" + kind, ms: 0, error: "THROW: " + String(e && e.stack || e).slice(0, 500) }});
                        throw e;
                    }}
                }};
            }}

            window.__QA_SPY_INSTALLED__ = true;
            return {{ ok: true, wrapped: wrappedCount.n, readonly: BLOCKED.size > 0 }};
        }})()
        """
        return self.eval_js(js, await_promise=False, timeout=10.0)

    def drain_diagnostics(self):
        """Drain both CDP-level passive errors and JS-level spy logs."""
        with self._evt_lock:
            cdp_data = {
                "js_exceptions": list(self.js_exceptions),
                "console_errors": list(self.console_errors),
                "network_errors": list(self.network_errors),
                "log_errors": list(self.log_errors),
            }
            self.js_exceptions.clear()
            self.console_errors.clear()
            self.network_errors.clear()
            self.log_errors.clear()

        spy_data = {"ring": [], "api_errors": [], "slow_calls": [], "blocked": []}
        try:
            val = self.eval_js(
                """(() => {
                    const out = {
                        ring: (window.__QA_RING__ || []).slice(-25),
                        api_errors: (window.__QA_API_ERRORS__ || []).splice(0),
                        slow_calls: (window.__QA_SLOW_CALLS__ || []).splice(0),
                        blocked: (window.__QA_BLOCKED_ATTEMPTS__ || []).splice(0)
                    };
                    return out;
                })()""",
                await_promise=False,
                timeout=5.0,
            )
            if isinstance(val, dict):
                spy_data = val
        except Exception:
            pass

        return {**cdp_data, **spy_data}

    def close(self):
        self._closed.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
