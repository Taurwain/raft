"""Configuration loading from YAML and CLI (infrastructure)."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from app.domain.config import ClusterConfig


def load_config(path: str | Path, *, cli_args: argparse.Namespace | None = None) -> ClusterConfig:
    """Load a ClusterConfig from a YAML file, applying CLI overrides."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if cli_args is not None:
        if getattr(cli_args, "self_id", None):
            data["self_id"] = cli_args.self_id
        if getattr(cli_args, "host", None):
            data.setdefault("nodes", [])
            for node in data["nodes"]:
                if node.get("id") == data.get("self_id"):
                    node["host"] = cli_args.host
        if getattr(cli_args, "port", None):
            data.setdefault("nodes", [])
            for node in data["nodes"]:
                if node.get("id") == data.get("self_id"):
                    node["port"] = cli_args.port
    return ClusterConfig(**data)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser used by a single node."""
    parser = argparse.ArgumentParser(description="Raft consensus node")
    parser.add_argument("--config", default="configs/cluster.yaml", help="path to cluster config")
    parser.add_argument("--self-id", default=None, help="override the node id to run as")
    parser.add_argument("--host", default=None, help="override bind host for this node")
    parser.add_argument("--port", type=int, default=None, help="override bind port for this node")
    return parser