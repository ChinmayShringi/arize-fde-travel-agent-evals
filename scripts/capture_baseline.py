"""Capture an immutable baseline: boot the API with tracing, replay the shipped
traffic, export every span to disk, write a run manifest.

Usage:
    uv run python scripts/capture_baseline.py /path/to/output_dir

The output dir must not already contain a capture (baselines are immutable).
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

PORT = 8317  # deliberately not 8000: avoids colliding with dev servers
BASE_URL = f"http://127.0.0.1:{PORT}"


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: capture_baseline.py <output_dir>")
    out = Path(sys.argv[1])
    spans_path = out / "spans.jsonl"
    if spans_path.exists():
        sys.exit(f"refusing to overwrite existing capture in {out}")
    out.mkdir(parents=True, exist_ok=True)

    # Preflight: the port must be free, otherwise traffic could silently hit a
    # stale server running different code.
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            sys.exit(f"port {PORT} already in use; kill the stale server first")

    env = {**os.environ, "TRACE_EXPORT_PATH": str(spans_path)}
    run_log = (out / "run_log.txt").open("w")
    server = subprocess.Popen(
        ["uv", "run", "uvicorn", "agent.api:app", "--port", str(PORT)],
        env=env,
        stdout=(out / "server_log.txt").open("w"),
        stderr=subprocess.STDOUT,
    )
    try:
        with httpx.Client(base_url=BASE_URL, timeout=2) as client:
            for _ in range(30):
                if server.poll() is not None:
                    sys.exit(f"server died during startup (exit {server.returncode}); see server_log.txt")
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                sys.exit("server never became healthy")

        started = time.time()
        traffic = subprocess.run(
            ["uv", "run", "python", "scripts/generate_traffic.py", BASE_URL],
            stdout=run_log,
            stderr=subprocess.STDOUT,
        )
        wall_seconds = round(time.time() - started, 1)
        if traffic.returncode != 0:
            sys.exit(f"traffic run failed with code {traffic.returncode}; see run_log.txt")
    finally:
        # SIGTERM lets uvicorn shut down cleanly, which flushes the OTLP batch
        # processor so Arize receives the tail spans; the local file already
        # has every span via the simple processor.
        server.send_signal(signal.SIGTERM)
        server.wait(timeout=30)
        run_log.close()

    spans = [json.loads(line) for line in spans_path.open()]
    roots = [s for s in spans if s["parent_id"] is None]
    sent = None
    for line in (out / "run_log.txt").read_text().splitlines():
        if line.startswith("Done") and "sent" in line:
            sent = int(line.split("sent")[1].split()[0])
    if not spans or not roots:
        sys.exit("CAPTURE INVALID: no spans were exported; do not use this directory")
    if sent is not None and len(roots) != sent:
        sys.exit(
            f"CAPTURE INVALID: {sent} messages sent but {len(roots)} root spans captured"
        )
    git_sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    manifest = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "git_dirty": bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True
            ).stdout.strip()
        ),
        "prompt_version": os.getenv("PROMPT_VERSION", "v0-shipped"),
        "agent_version": os.getenv("AGENT_VERSION", "baseline-0080b11"),
        "model": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
        "span_count": len(spans),
        "turn_count": len(roots),
        "wall_seconds": wall_seconds,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
