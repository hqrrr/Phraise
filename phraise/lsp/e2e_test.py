# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: LSP end-to-end test script for Harper integration.
"""End-to-end smoke test using the REAL harper-ls.exe binary.

Spawns harper-ls via subprocess, exercises the full LSP lifecycle
(initialize → didOpen → publishDiagnostics → shutdown → exit),
and verifies that grammar issues are detected for intentional mistakes.

Skips gracefully if the binary is not present.
"""

import json
import os
import subprocess
import sys
import threading
import time
import queue
from pathlib import Path


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

HARPER_BINARY = Path(__file__).parent / "harper-ls.exe"


def is_binary_available() -> bool:
    """Check whether the harper-ls.exe binary exists and is readable."""
    return HARPER_BINARY.exists() and os.access(str(HARPER_BINARY), os.R_OK)


# ---------------------------------------------------------------------------
# LSP protocol helpers
# ---------------------------------------------------------------------------

def lsp_encode(obj: dict) -> bytes:
    """Encode a JSON-RPC message with Content-Length framing."""
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


class BackgroundLspReader:
    """Reads LSP messages from a pipe in a background thread."""

    def __init__(self, pipe_fd: int):
        self._fd = pipe_fd
        self._buffer = b""
        self._queue: queue.Queue = queue.Queue()
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
            except json.JSONDecodeError:
                pass

    def get_messages(self, timeout: float = 3.0) -> list[dict]:
        """Collect available messages; wait up to *timeout* for the first."""
        results = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                msg = self._queue.get(timeout=max(0.1, deadline - time.monotonic()))
                results.append(msg)
                break
            except queue.Empty:
                return results
        # Drain any remaining messages
        while True:
            try:
                results.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return results

    def stop(self):
        self._stop.set()


def handle_server_requests(reader: BackgroundLspReader, stdin, timeout: float = 1.0):
    """Read and respond to pending server→client requests.

    Handles workspace/configuration and client/registerCapability.
    """
    msgs = reader.get_messages(timeout=timeout)
    for msg in msgs:
        if "id" not in msg:
            continue
        method = msg.get("method", "")
        msg_id = msg["id"]
        if method == "workspace/configuration":
            response = {"jsonrpc": "2.0", "id": msg_id, "result": []}
            stdin.write(lsp_encode(response))
            stdin.flush()
        elif method == "client/registerCapability":
            response = {"jsonrpc": "2.0", "id": msg_id, "result": None}
            stdin.write(lsp_encode(response))
            stdin.flush()


# ---------------------------------------------------------------------------
# E2E test
# ---------------------------------------------------------------------------

def run_e2e_test() -> int:
    """Run the end-to-end LSP smoke test against the real harper-ls binary.

    Returns 0 on success, 1 on failure, 2 on skip.
    """

    print("=" * 60)
    print("HARPER E2E SMOKE TEST")
    print(f"Binary: {HARPER_BINARY}")
    if HARPER_BINARY.exists():
        print(f"Binary size: {HARPER_BINARY.stat().st_size:,} bytes")
    print("=" * 60)

    # --- 1. Availability check ---
    if not is_binary_available():
        print("\nSKIP: harper-ls.exe not found at", HARPER_BINARY)
        print("This is expected in CI / non-Windows environments.")
        return 2  # skip

    print("[OK] Binary found")

    # --- 2. Spawn harper-ls ---
    proc = subprocess.Popen(
        [str(HARPER_BINARY), "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"\n[LIFECYCLE] Spawned harper-ls (PID={proc.pid})")

    reader = BackgroundLspReader(proc.stdout.fileno())

    # Background stderr collector
    stderr_chunks: list[bytes] = []
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

    errors: list[str] = []
    diagnostics_received = False
    exit_code = -1

    try:
        # --- 3. Initialize ---
        print("\n>>> [REQUEST] initialize (id=1)")
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
        proc.stdin.write(lsp_encode(init_request))
        proc.stdin.flush()

        msgs = reader.get_messages(timeout=5.0)
        response_msgs = [m for m in msgs if "id" in m]
        if not response_msgs:
            errors.append("No initialize response received within 5s")
        else:
            print("[OK] Initialize response received")

        time.sleep(0.2)

        # --- 4. Send initialized notification ---
        print("\n>>> [NOTIFICATION] initialized")
        initialized_notif = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
        proc.stdin.write(lsp_encode(initialized_notif))
        proc.stdin.flush()

        handle_server_requests(reader, proc.stdin, timeout=2.0)

        # --- 5. Send didOpen with intentional mistakes ---
        # "tset" → "test", "emergancy" → "emergency", "systme" → "system"
        sample_text = "This is a tset of the emergancy broadcast systme."
        print(f'\n>>> [NOTIFICATION] textDocument/didOpen\n    Text: "{sample_text}"')
        did_open_notif = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": "file:///e2e_test.txt",
                    "languageId": "plaintext",
                    "version": 1,
                    "text": sample_text,
                },
            },
        }
        proc.stdin.write(lsp_encode(did_open_notif))
        proc.stdin.flush()

        # --- 6. Wait for publishDiagnostics ---
        print("\n--- Waiting for publishDiagnostics... ---")
        poll_start = time.monotonic()
        diagnostics_msg = None

        while time.monotonic() - poll_start < 8.0:
            msgs = reader.get_messages(timeout=1.0)
            for msg in msgs:
                handle_server_requests(reader, proc.stdin, timeout=0.1)
                if msg.get("method") == "textDocument/publishDiagnostics":
                    diagnostics_msg = msg
            if diagnostics_msg:
                break

        if diagnostics_msg:
            params = diagnostics_msg.get("params", {})
            diags = params.get("diagnostics", [])
            print(f"[OK] Received {len(diags)} diagnostic(s) from harper-ls")

            for diag in diags:
                msg_text = diag.get("message", "")
                print(f"   - {msg_text}")

            if len(diags) > 0:
                diagnostics_received = True
                print("[OK] Grammar issues DETECTED in intentional mistakes")
            else:
                errors.append("No diagnostics found for text with intentional mistakes")
        else:
            errors.append(
                "No publishDiagnostics received within 8s for intentional mistakes"
            )

        # --- 7. Shutdown ---
        print("\n>>> [REQUEST] shutdown (id=999)")
        shutdown_request = {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "shutdown",
        }
        proc.stdin.write(lsp_encode(shutdown_request))
        proc.stdin.flush()

        # Wait for shutdown response (id=999)
        shutdown_response_seen = False
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            msgs = reader.get_messages(timeout=1.0)
            for msg in msgs:
                if msg.get("id") == 999:
                    shutdown_response_seen = True
                    break
            if shutdown_response_seen:
                break
        if not shutdown_response_seen:
            errors.append("No shutdown response received (id=999)")

        # --- 8. Exit ---
        print("\n>>> [NOTIFICATION] exit")
        exit_notif = {"jsonrpc": "2.0", "method": "exit"}
        proc.stdin.write(lsp_encode(exit_notif))
        proc.stdin.flush()

        # Close stdin to signal EOF, helping the process terminate
        try:
            proc.stdin.close()
        except OSError:
            pass

        try:
            proc.wait(timeout=10.0)
            print(f"[OK] harper-ls exited cleanly (exit code={proc.returncode})")
        except subprocess.TimeoutExpired:
            print("[WARN] harper-ls did not exit within 10s, terminating")
            proc.terminate()
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        exit_code = proc.returncode

    finally:
        reader.stop()
        stderr_stop.set()
        stderr_thread.join(timeout=2.0)

    # --- 9. Report stderr ---
    if stderr_chunks:
        stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        if stderr_text.strip():
            print(f"\n--- STDERR ---\n{stderr_text[:2000]}")
            if len(stderr_text) > 2000:
                print(f"[... truncated, total {len(stderr_text)} bytes]")

    # --- 10. Verdict ---
    print("\n" + "=" * 60)
    if errors:
        print("E2E TEST FAILED")
        for e in errors:
            print(f"  FAIL: {e}")
        return 1
    elif diagnostics_received:
        print("E2E TEST PASSED")
        print("  - Binary spawned successfully")
        print("  - Initialize completed")
        print("  - Diagnostics received for intentional mistakes")
        print("  - Shutdown/exit clean")
        return 0
    else:
        print("E2E TEST FAILED")
        print("  No diagnostics received (but no explicit errors recorded)")
        return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    exit_code = run_e2e_test()
    if exit_code == 2:
        print("\n[SKIP] Skipped (binary not available) -- not a failure.")
        return 0  # skip is not failure
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
