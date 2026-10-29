from __future__ import annotations

import argparse
import getpass
import os

from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Call VM MCP: local VMware Workstation tools")
    parser.add_argument("action", choices=("serve", "credentials"), nargs="?", default="serve")
    parser.add_argument("vm_id", nargs="?")
    parser.add_argument("--config", help="Absolute path to the local VM inventory")
    args = parser.parse_args()
    if args.config:
        os.environ["CALL_VM_MCP_CONFIG"] = args.config
    if args.action == "credentials":
        config = load_config()
        if args.vm_id not in config["vms"]:
            parser.error("Choose a registered VM id: " + ", ".join(config["vms"]))
        from .windows_credentials import write_generic_credential
        username = input(f"{args.vm_id} guest username: ").strip()
        password = getpass.getpass(f"{args.vm_id} guest password: ")
        write_generic_credential(f"VMwareLab/{args.vm_id}", username, password)
        print(f"Saved VMwareLab/{args.vm_id} in Windows Credential Manager.")
    else:
        if args.vm_id:
            parser.error("vm_id is only used by the credentials action")
        from .server import serve
        serve()


if __name__ == "__main__":
    main()
