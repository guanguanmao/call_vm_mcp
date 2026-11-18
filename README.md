# Call VM MCP

**English** | [简体中文](README.zh-CN.md)

A local MCP server for VMware Workstation on Windows. Connect OpenCode, Codex, or another MCP client over stdio to operate virtual machines you have explicitly registered.

## Installation

Requires Windows, VMware Workstation, Python 3.11 or later, and existing `.vmx` files. All installation paths below are examples; replace them with your own.

```powershell
Set-Location 'C:\Tools\Call-VM-MCP'
.\scripts\install.ps1 -Python python
```

The installer creates an isolated `.venv`, installs pinned dependencies, and copies the example inventory if a local inventory does not already exist. It does not overwrite an existing inventory. For offline installation, add `-WheelDirectory 'D:\Wheels'`.

## Register virtual machines

Edit `config.local.json` in the installation directory. Enter absolute paths to vmrun and your VMX files. Escape backslashes as `\\` in JSON.

```json
{
  "vmrun": "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe",
  "vms": {
    "kali": {
      "label": "Kali Linux",
      "os": "linux",
      "path": "D:\\VMs\\Kali\\Kali.vmx"
    }
  }
}
```

Add more machines under `vms` as needed. IDs must start with a lowercase letter, contain only lowercase letters, digits, or underscores, and be at most 32 characters long. Set `os` to `linux` or `windows`. The inventory does not store passwords. Reload the MCP server after adding or editing machines; automatic discovery and live configuration reloads are not supported.

## Connect a client

For OpenCode, merge the following `mcp` configuration into your project's `opencode.json`. Enabling the server at project level keeps the tools scoped to the projects that need them.

```json
{
  "mcp": {
    "vmware_lab": {
      "type": "local",
      "command": [
        "C:\\Tools\\Call-VM-MCP\\.venv\\Scripts\\python.exe",
        "C:\\Tools\\Call-VM-MCP\\serve.py"
      ],
      "enabled": true,
      "timeout": 120000
    }
  }
}
```

Replace both installation paths, reload the client, and run `opencode mcp list` to check the connection. Do not register the same server more than once.

For other clients, see [configs/mcp-servers.json](configs/mcp-servers.json). For Codex, see [configs/codex.example.toml](configs/codex.example.toml). These templates do not modify client settings automatically. Launch the server with its dedicated Python interpreter. To use a different inventory, append `--config` and the JSON file's absolute path to the launcher arguments.

## Usage

| Tool | Function |
| --- | --- |
| `vmware_list()` | Return registered VM IDs, labels, OS types, VMX paths, file availability, and running state. |
| `vmware_start(vm_id, wait_seconds=90, gui=false)` | Start a VM; `gui=true` shows its VMware window. An already running VM is not started again. |
| `vmware_shutdown(vm_id)` | Request a normal shutdown using VMware Tools. Failure does not trigger a forced power-off. |
| `linux_run(vm_id, command, working_directory=null, timeout_seconds=60)` | Execute a Bash command in a running Linux guest and return its output. |

For example, ask your client: “List my virtual machines, then start kali and show its window.” The server does not start machines automatically during initialization. A `running=true` result only means VMware has started the VM; it does not guarantee that the guest is ready.

Windows guests currently support listing and power operations, but not guest command execution. Four tools are registered by default.

## Guest credentials

Listing and starting VMs do not require a password. Linux guest commands require VMware Tools / open-vm-tools and a login account inside that VM.

Run the following in an interactive terminal on the host:

```powershell
& .\.venv\Scripts\python.exe .\serve.py credentials kali
```

Enter the guest username and password. The password is not echoed. Credentials are saved in the current Windows user's Credential Manager under `VMwareLab/kali`. Replace `kali` with another registered VM ID as needed. Set credentials again after changing computers or Windows users. Do not put passwords in chat, inventories, or client configuration.

Once the guest is running and Tools is ready, try `linux_run` with the command `uname -s; id -un; pwd` and the working directory `/tmp` to check the returned result. Guest command execution still requires end-to-end acceptance testing.

## Operational notes

- Each client starts its own stdio subprocess. The server does not listen on an HTTP port or poll in the background; normal operation uses the local vmrun executable.
- Avoid issuing conflicting start and shutdown requests for the same VM from multiple clients. There is currently no operation lock.
- Guest commands run with the guest account's permissions. A timeout only limits how long the host waits; it does not guarantee termination of guest processes.
- Command output is first written to a log in the guest's `/tmp` directory. The host's temporary copy is deleted after reading; guest logs can be cleaned up separately. vmrun receives the password as a host process argument.
- VM paths and command output are returned to the client. If the client uses a cloud model, these results may be included in model requests.
- If `exists=false`, check the VMX path. If credentials are missing, run the credentials command above. If normal shutdown fails, check Tools.
- Local inventories, virtual environments, and passwords are not part of the files to share. Review package contents before sharing. `.gitignore` does not apply to arbitrary ZIP exports and does not remove files already tracked by Git.
