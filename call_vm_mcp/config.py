"""A local, explicitly registered inventory; loading it performs no VM operations."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


def load_config(path: str | Path | None = None) -> dict:
    selected = path or os.environ.get("CALL_VM_MCP_CONFIG")
    location = Path(selected) if selected else Path(__file__).resolve().parent.parent / "config.local.json"
    try:
        config = json.loads(location.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing inventory: {location}. Copy configs/machines.example.json and edit its paths.") from exc
    if not isinstance(config, dict):
        raise ValueError("Inventory must be a JSON object")
    vmrun = config.get("vmrun")
    if not isinstance(vmrun, str) or not Path(vmrun).is_absolute():
        raise ValueError("vmrun must be an absolute executable path")
    machines = config.get("vms")
    if not isinstance(machines, dict) or not machines:
        raise ValueError("vms must contain at least one registered VM")
    for vm_id, machine in machines.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", vm_id):
            raise ValueError(f"Invalid VM id: {vm_id}")
        if not isinstance(machine, dict):
            raise ValueError(f"Invalid definition for {vm_id}")
        if machine.get("os") not in {"linux", "windows"}:
            raise ValueError(f"Unsupported OS for {vm_id}")
        if not isinstance(machine.get("label"), str) or not machine["label"].strip():
            raise ValueError(f"Missing label for {vm_id}")
        vmx = machine.get("path")
        if not isinstance(vmx, str) or not Path(vmx).is_absolute() or Path(vmx).suffix.lower() != ".vmx":
            raise ValueError(f"Expected an absolute .vmx path for {vm_id}")
    return config
