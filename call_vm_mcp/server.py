"""Local stdio MCP server for a small VMware Workstation lab.

This server controls only the VMX files listed in ``VM_DEFINITIONS``. Guest
passwords are read from the process environment and are never kept in code or
written to server output.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from .windows_credentials import read_generic_credential


from .config import load_config

_config = load_config()
DEFAULT_VMRUN = _config["vmrun"]
VM_DEFINITIONS = _config["vms"]

mcp = FastMCP("Call VM MCP")


def setting(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def vmrun_path() -> str:
    return setting("VMWARE_VMRUN_PATH", DEFAULT_VMRUN)


def vm_definition(vm_id: str, require_file: bool = True) -> dict[str, str]:
    key = vm_id.strip().lower()
    if key not in VM_DEFINITIONS:
        options = ", ".join(VM_DEFINITIONS)
        raise ValueError(f"Unknown VM '{vm_id}'. Choose one of: {options}")
    definition = VM_DEFINITIONS[key].copy()
    definition["id"] = key
    override = os.environ.get(f"VMWARE_{key.upper()}_VMX_PATH")
    if override:
        definition["path"] = override
    if require_file and not Path(definition["path"]).is_file():
        raise RuntimeError(f"VMX file was not found: {definition['path']}")
    return definition


def run_process(args: list[str], timeout: int = 60) -> dict[str, Any]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            # vmrun writes UTF-8 paths on this host, including Chinese VMX names.
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError(f"VMware CLI was not found: {args[0]}") from None
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": None,
            "stdout": (exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or "").strip(),
            "stderr": (exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or "").strip(),
            "error": f"Timed out after {timeout} seconds",
        }

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def running_vms() -> set[str]:
    result = run_process([vmrun_path(), "list"])
    if not result["ok"]:
        raise RuntimeError(result["stderr"] or result["stdout"] or "Could not query VMware")
    return {
        os.path.normcase(os.path.normpath(line.strip()))
        for line in result["stdout"].splitlines()
        if line.strip().lower().endswith(".vmx")
    }


def is_running(definition: dict[str, str]) -> bool:
    return os.path.normcase(os.path.normpath(definition["path"])) in running_vms()


def guest_credentials(vm_id: str) -> tuple[str, str]:
    prefix = f"VMWARE_{vm_id.upper()}"
    username = os.environ.get(f"{prefix}_USERNAME") or os.environ.get("VMWARE_GUEST_USERNAME")
    password = os.environ.get(f"{prefix}_PASSWORD") or os.environ.get("VMWARE_GUEST_PASSWORD")
    if username and password:
        return username, password
    if username or password:
        raise RuntimeError(f"Set both {prefix}_USERNAME and {prefix}_PASSWORD, or neither.")

    credential = read_generic_credential(f"VMwareLab/{vm_id}")
    if credential:
        return credential
    raise RuntimeError(
        f"No credential for {vm_id}. Run serve.py credentials {vm_id}, "
        f"or set {prefix}_USERNAME and {prefix}_PASSWORD in the MCP server environment."
    )


@mcp.tool()
def vmware_list() -> list[dict[str, Any]]:
    """List registered VM IDs, VMX availability and running state."""
    running = running_vms()
    machines: list[dict[str, Any]] = []
    for vm_id in VM_DEFINITIONS:
        definition = vm_definition(vm_id, require_file=False)
        machines.append(
            {
                "id": vm_id,
                "label": definition["label"],
                "os": definition["os"],
                "vmx_path": definition["path"],
                "exists": Path(definition["path"]).is_file(),
                "running": os.path.normcase(os.path.normpath(definition["path"])) in running,
            }
        )
    return machines


@mcp.tool()
def vmware_start(vm_id: str, wait_seconds: int = 90, gui: bool = False) -> dict[str, Any]:
    """Start one VM; gui=true opens its VMware window. Idempotent if running."""
    if not 1 <= wait_seconds <= 300:
        raise ValueError("wait_seconds must be between 1 and 300")
    definition = vm_definition(vm_id)
    if is_running(definition):
        if gui:
            executable = Path(vmrun_path()).with_name("vmware.exe")
            if not executable.is_file():
                raise RuntimeError(f"VMware GUI executable was not found: {executable}")
            subprocess.Popen([str(executable), "-x", definition["path"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "vm_id": definition["id"], "already_running": True}

    result = run_process([vmrun_path(), "start", definition["path"], "gui" if gui else "nogui"], timeout=60)
    if not result["ok"]:
        return result | {"vm_id": definition["id"]}

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if is_running(definition):
            return {"ok": True, "vm_id": definition["id"], "already_running": False, "running": True}
        time.sleep(2)
    return {"ok": False, "vm_id": definition["id"], "error": "VM did not start in time"}


@mcp.tool()
def vmware_shutdown(vm_id: str) -> dict[str, Any]:
    """Request a soft shutdown of one registered VM. Requires VMware Tools."""
    definition = vm_definition(vm_id)
    if not is_running(definition):
        return {"ok": True, "vm_id": definition["id"], "already_stopped": True}
    return run_process([vmrun_path(), "stop", definition["path"], "soft"]) | {"vm_id": definition["id"]}


def run_linux_command(
    vm_id: str,
    command: str,
    working_directory: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    definition = vm_definition(vm_id)
    if definition["os"] != "linux":
        raise ValueError(f"{vm_id} is not a Linux guest; command execution is not enabled for it yet.")
    if not command.strip():
        raise ValueError("command must not be empty")
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("timeout_seconds must be between 1 and 600")
    if not is_running(definition):
        return {"ok": False, "vm_id": definition["id"], "error": "VM is not running; call vmware_start first."}

    username, password = guest_credentials(definition["id"])
    guest_output = f"/tmp/vmware-mcp-{uuid.uuid4().hex}.log"
    local_output = Path(tempfile.gettempdir()) / f"vmware-mcp-{uuid.uuid4().hex}.log"
    directory = working_directory or f"/home/{username}"
    quoted_output = shlex.quote(guest_output)
    # The wrapper itself always exits successfully so VMware lets us copy output.
    # vmrun strips shell-style ``$variables`` from arguments, therefore an
    # if/else marker is used instead of trying to append ``$?``.
    script = (
        f"if (cd -- {shlex.quote(directory)} && {{ {command}; }}) > {quoted_output} 2>&1; then "
        f"printf '\\n__VMWARE_MCP_OK__=1\\n' >> {quoted_output}; "
        f"else printf '\\n__VMWARE_MCP_OK__=0\\n' >> {quoted_output}; fi; exit 0"
    )

    try:
        started = run_process(
            [
                vmrun_path(),
                "-gu",
                username,
                "-gp",
                password,
                "runProgramInGuest",
                definition["path"],
                "/bin/bash",
                "-lc",
                script,
            ],
            timeout=timeout_seconds + 30,
        )
        if not started["ok"]:
            return started | {"vm_id": definition["id"]}

        copied = run_process(
            [
                vmrun_path(),
                "-gu",
                username,
                "-gp",
                password,
                "CopyFileFromGuestToHost",
                definition["path"],
                guest_output,
                str(local_output),
            ],
            timeout=30,
        )
        if not copied["ok"]:
            return copied | {"vm_id": definition["id"], "error": "Command ran but its output could not be copied."}

        output = local_output.read_text(encoding="utf-8", errors="replace")
        marker = re.search(r"\n__VMWARE_MCP_OK__=([01])\s*$", output)
        succeeded = marker is not None and marker.group(1) == "1"
        if marker:
            output = output[: marker.start()].rstrip()
        return {
            "ok": succeeded,
            "vm_id": definition["id"],
            "command_succeeded": succeeded,
            "stdout_stderr": output,
        }
    finally:
        local_output.unlink(missing_ok=True)


@mcp.tool()
def linux_run(
    vm_id: str,
    command: str,
    working_directory: str | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Run Bash in a registered Linux VM; requires Tools and saved guest credentials."""
    return run_linux_command(vm_id, command, working_directory, timeout_seconds)


def ubuntu_run(command: str, working_directory: str | None = None, timeout_seconds: int = 60) -> dict[str, Any]:
    """Convenience alias for running one Bash command in the Ubuntu guest."""
    return run_linux_command("ubuntu", command, working_directory, timeout_seconds)


if os.environ.get("CALL_VM_MCP_LEGACY_ALIASES") == "1":
    mcp.tool()(ubuntu_run)

def serve() -> None:
    mcp.run(transport="stdio")
