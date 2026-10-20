"""Launch a whole Raft cluster locally as one process per node.

Usage:
    uv run python launcher.py --config configs/cluster.yaml
"""

from __future__ import annotations

import argparse
import contextlib
import subprocess
import sys
import time
from pathlib import Path

import yaml

from app.domain.config import ClusterConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch a local Raft cluster")
    parser.add_argument("--config", default="configs/cluster.yaml")
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="stream each node's logs to your terminal (default: write to logs/ files)",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = ClusterConfig(**data)

    print(f"Starting cluster '{config.cluster_name}' with {len(config.nodes)} node(s)...")
    print(f"Quorum = {config.quorum}")

    procs: list[subprocess.Popen] = []
    for node in config.nodes:
        cmd = [
            sys.executable,
            "-m",
            "app.main",
            "--config",
            str(config_path),
            "--self-id",
            node.id,
        ]
        log_dir = Path(config.limits.log_dir) / f"{node.id}.log"
        if args.stdout:
            print(f">>> node {node.id} -> {node.address}")
            procs.append(
                subprocess.Popen(cmd, cwd=Path(__file__).resolve().parent)
            )
        else:
            log_dir.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(log_dir, "w")  # noqa: SIM115
            print(f">>> node {node.id} -> {log_dir}")
            procs.append(
                subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=Path(__file__).resolve().parent,
                )
            )

    print("\nCluster is up. Press Ctrl+C to stop all nodes.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        for p in procs:
            p.terminate()
        with contextlib.suppress(Exception):
            for p in procs:
                p.wait(timeout=3)


if __name__ == "__main__":
    main()