"""
smoke_test.py — Discovery spike for harper-ls LSP protocol.

Spawns harper-ls.exe via stdio, exercises the LSP lifecycle:
  initialize -> initialized -> didOpen -> publishDiagnostics -> codeAction -> shutdown -> exit

Prints all JSON-RPC messages sent and received for analysis.

Windows-compatible: uses background reader thread with os.read().
"""

import json
import subprocess
import sys
import time
import os
import threading
import queue

HARPER_LS_PATH = os.path.join(os.path.dirname(__file__), "harper-ls.exe")


def lsp_encode(obj: dict) -> bytes:
    """Encode a JSON-RPC message with Content-Length framing."""
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


class BackgroundLspReader:
    """Reads LSP messages from a pipe in a background thread.

    Uses os.read() which returns as soon as any data is available.
    """

    def __init__(self, pipe_fd: int):
        self._fd = pipe_fd
        self._buffer = b""
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                chunk = os.read(self._fd, 65536)
                if not chunk:
                    break
                self._buffer += chunk
                self._decode_all()
            except OSError:
                break

    def _decode_all(self):
        while True:
            idx = self._buffer.find(b"\r\n\r\n")
            if idx == -1:
                return

            header_part = self._buffer[:idx]
            content_length = 0
            for line in header_part.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    content_length = int(line.split(b":")[1].strip())

            body_start = idx + 4
            body_end = body_start + content_length

            if len(self._buffer) < body_end:
                return

            body = self._buffer[body_start:body_end]
            self._buffer = self._buffer[body_end:]

            try:
                msg = json.loads(body)
                self._queue.put(msg)
            except json.JSONDecodeError as e:
                print(f"[WARN] JSON decode: {e}", file=sys.stderr)

    def get_messages(self, timeout: float = 3.0, count: int = 0) -> list[dict]:
        """Collect available messages; wait up to `timeout` for the first one.

        Args:
            timeout: Max seconds to wait for the first message.
            count: If > 0, try to collect exactly this many messages.
        """
        results = []
        deadline = time.monotonic() + timeout

        # Wait for first message
        while time.monotonic() < deadline:
            try:
                msg = self._queue.get(timeout=max(0.1, deadline - time.monotonic()))
                results.append(msg)
                break
            except queue.Empty:
                return results

        # Collect more messages
        if count > 0:
            while len(results) < count:
                try:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    msg = self._queue.get(timeout=min(0.5, remaining))
                    results.append(msg)
                except queue.Empty:
                    break
        else:
            while True:
                try:
                    results.append(self._queue.get_nowait())
                except queue.Empty:
                    break

        return results

    def stop(self):
        self._stop.set()


def main():
    print("=" * 60, flush=True)
    print("HARPER-LS LSP SMOKE TEST", flush=True)
    print(f"Binary: {HARPER_LS_PATH}", flush=True)
    print(f"Binary size: {os.path.getsize(HARPER_LS_PATH)} bytes", flush=True)
    print("=" * 60, flush=True)

    # --- Spawn harper-ls ---
    proc = subprocess.Popen(
        [HARPER_LS_PATH, "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"\n[LIFECYCLE] Spawned harper-ls (PID={proc.pid})", flush=True)

    reader = BackgroundLspReader(proc.stdout.fileno())

    stderr_chunks = []
    stderr_stop = threading.Event()

    def read_stderr():
        while not stderr_stop.is_set():
            try:
                chunk = os.read(proc.stderr.fileno(), 65536)
                if not chunk:
                    break
                stderr_chunks.append(chunk)
            except OSError:
                break

    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()

    def handle_server_requests(timeout: float = 0.5):
        """Read and respond to any pending server requests.

        Handles:
          - workspace/configuration: return empty config array
          - client/registerCapability: acknowledge with null result
        """
        msgs = reader.get_messages(timeout=timeout)
        for msg in msgs:
            print(f"\n<<< [MESSAGE]", flush=True)
            print(json.dumps(msg, indent=2, default=str), flush=True)
            respond_to_server(msg)

    def respond_to_server(msg: dict):
        """If `msg` is a server request (has 'id' and is not a notification), respond."""
        if "id" not in msg:
            return
        method = msg.get("method", "")
        msg_id = msg["id"]

        if method == "workspace/configuration":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": [],
            }
            print(f"\n>>> [RESPONSE] workspace/configuration (id={msg_id})", flush=True)
            print(json.dumps(response, indent=2), flush=True)
            proc.stdin.write(lsp_encode(response))
            proc.stdin.flush()

        elif method == "client/registerCapability":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": None,
            }
            print(f"\n>>> [RESPONSE] client/registerCapability (id={msg_id})", flush=True)
            print(json.dumps(response, indent=2), flush=True)
            proc.stdin.write(lsp_encode(response))
            proc.stdin.flush()

    try:
        # === 1. INITIALIZE ===
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": None,
                "rootUri": None,
                "capabilities": {},
                "trace": "off",
            },
        }

        print(f"\n>>> [REQUEST] initialize (id=1)", flush=True)
        print(json.dumps(init_request, indent=2), flush=True)
        proc.stdin.write(lsp_encode(init_request))
        proc.stdin.flush()

        msgs = reader.get_messages(timeout=5.0)
        for msg in msgs:
            print(f"\n<<< [RESPONSE] (id={msg.get('id')})", flush=True)
            print(json.dumps(msg, indent=2, default=str), flush=True)

        time.sleep(0.2)

        # === 1b. initialized notification + handle config requests ===
        initialized_notif = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {},
        }
        print(f"\n>>> [NOTIFICATION] initialized", flush=True)
        print(json.dumps(initialized_notif, indent=2), flush=True)
        proc.stdin.write(lsp_encode(initialized_notif))
        proc.stdin.flush()

        # Handle workspace/configuration and window/logMessage
        handle_server_requests(timeout=2.0)

        # === 2. textDocument/didOpen ===
        sample_text = "helo wrld is a tset"
        did_open_notif = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": "file:///test.txt",
                    "languageId": "plaintext",
                    "version": 1,
                    "text": sample_text,
                }
            },
        }

        print(f"\n>>> [NOTIFICATION] textDocument/didOpen", flush=True)
        print(f"    Text: \"{sample_text}\"", flush=True)
        print(json.dumps(did_open_notif, indent=2), flush=True)
        proc.stdin.write(lsp_encode(did_open_notif))
        proc.stdin.flush()

        # === 3. Collect publishDiagnostics ===
        print(f"\n--- Waiting for publishDiagnostics... ---", flush=True)

        diagnostics_msg = None
        poll_start = time.monotonic()

        while time.monotonic() - poll_start < 8.0:
            msgs = reader.get_messages(timeout=1.0)
            for msg in msgs:
                print(f"\n<<< [MESSAGE]", flush=True)
                print(json.dumps(msg, indent=2, default=str), flush=True)
                respond_to_server(msg)
                if msg.get("method") == "textDocument/publishDiagnostics":
                    diagnostics_msg = msg
            if diagnostics_msg:
                break

        # === 4. textDocument/codeAction for each diagnostic ===
        if diagnostics_msg:
            params = diagnostics_msg.get("params", {})
            uri = params.get("uri", "file:///test.txt")
            diagnostics = params.get("diagnostics", [])
            print(f"\n--- Received {len(diagnostics)} diagnostic(s) ---", flush=True)

            for i, diag in enumerate(diagnostics):
                ca_id = 100 + i
                ca_request = {
                    "jsonrpc": "2.0",
                    "id": ca_id,
                    "method": "textDocument/codeAction",
                    "params": {
                        "textDocument": {"uri": uri},
                        "range": diag["range"],
                        "context": {"diagnostics": [diag]},
                    },
                }
                print(f"\n>>> [REQUEST] textDocument/codeAction (id={ca_id})", flush=True)
                print(json.dumps(ca_request, indent=2), flush=True)
                proc.stdin.write(lsp_encode(ca_request))
                proc.stdin.flush()

            # Read codeAction results (one response per request)
            time.sleep(0.5)
            msgs = reader.get_messages(timeout=4.0)
            for msg in msgs:
                print(f"\n<<< [RESPONSE] (id={msg.get('id')})", flush=True)
                print(json.dumps(msg, indent=2, default=str), flush=True)
        else:
            print("\n--- No publishDiagnostics received ---", flush=True)

        # === 5. SHUTDOWN ===
        # Omit params entirely — harper-ls rejects "params": {}
        shutdown_request = {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "shutdown",
        }
        print(f"\n>>> [REQUEST] shutdown (id=999)", flush=True)
        print(json.dumps(shutdown_request, indent=2), flush=True)
        proc.stdin.write(lsp_encode(shutdown_request))
        proc.stdin.flush()

        # Read all messages after shutdown (harper sends clearing diagnostics first)
        time.sleep(0.5)
        msgs = reader.get_messages(timeout=3.0)
        for msg in msgs:
            print(f"\n<<< [MESSAGE]", flush=True)
            print(json.dumps(msg, indent=2, default=str), flush=True)

        # === 6. EXIT ===
        exit_notif = {
            "jsonrpc": "2.0",
            "method": "exit",
        }
        print(f"\n>>> [NOTIFICATION] exit", flush=True)
        print(json.dumps(exit_notif, indent=2), flush=True)
        proc.stdin.write(lsp_encode(exit_notif))
        proc.stdin.flush()

        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            print("[WARN] harper-ls did not exit in 5s, terminating", flush=True)
            proc.kill()
            proc.wait()

        # Measure time from didOpen to diagnostics
        print("\n" + "=" * 60, flush=True)
        print("SMOKE TEST COMPLETE", flush=True)
        print(f"harper-ls exit code: {proc.returncode}", flush=True)

    finally:
        reader.stop()
        stderr_stop.set()
        stderr_thread.join(timeout=2.0)

    if stderr_chunks:
        stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        print(f"\n--- STDERR ---\n{stderr_text}", flush=True)

    print("=" * 60, flush=True)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
