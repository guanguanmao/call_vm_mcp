# Call VM MCP

用于 Windows VMware Workstation 的本地 MCP 服务。通过 stdio 接入 OpenCode、Codex 或其他 MCP 客户端，操作自己登记的虚拟机。

## 安装

需要 Windows、VMware Workstation、Python 3.11 或以上，以及已有的 `.vmx` 文件。以下安装位置均为示例，请替换为自己的路径。

```powershell
Set-Location 'C:\Tools\Call-VM-MCP'
.\scripts\install.ps1 -Python python
```

安装器建立独立 `.venv`、安装锁定依赖，并在缺少本机登记表时复制示例；不会覆盖已有登记表。离线安装可追加 `-WheelDirectory 'D:\Wheels'`。

## 登记虚拟机

编辑安装目录下的 `config.local.json`，填写本机 vmrun 与 VMX 的绝对路径。JSON 中反斜杠写为 `\\`。

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

可在 `vms` 中继续添加机器。ID 以小写字母开头，只包含小写字母、数字或下划线，最多 32 个字符；`os` 为 `linux` 或 `windows`。登记表不保存密码。新增或修改机器后重新加载 MCP，不会自动发现或热更新。

## 接入客户端

OpenCode：将以下 `mcp` 配置合并到项目 `opencode.json`。项目级启用可以减少其他项目加载的工具。

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

替换两处安装路径，重新加载客户端，再运行 `opencode mcp list` 检查连接。不要重复注册同一个服务。

其他客户端可参考 `configs/mcp-servers.json`，Codex 可参考 `configs/codex.example.toml`。模板不会自动修改客户端设置。命令使用本服务的独立 Python；如需其他登记表，在入口参数后追加 `--config` 和 JSON 的绝对路径。

## 使用

| 工具  | 功能  |
| --- | --- |
| `vmware_list()` | 返回登记机器的 ID、名称、系统类型、VMX 路径、文件存在与运行状态 |
| `vmware_start(vm_id, wait_seconds=90, gui=false)` | 启动一台机器；`gui=true` 显示 VMware 窗口，已运行时不重复启动 |
| `vmware_shutdown(vm_id)` | 请求正常关机，需要 VMware Tools；失败时不会自动强制断电 |
| `linux_run(vm_id, command, working_directory=null, timeout_seconds=60)` | 在已运行的 Linux 客体执行 Bash 命令，返回输出 |

例如，在客户端提出：“列出虚拟机，启动 kali 并显示窗口。”不需要启动的机器不会在服务初始化时自动开机。`running=true` 只表示 VMware 已启动机器，不保证客体已经就绪。

Windows 客体目前支持列表和电源操作，不支持客体命令。默认只注册四个工具。

## 客体登录凭据

列表和启动不需要密码。Linux 客体命令需要 VMware Tools / open-vm-tools，以及该虚拟机内部的登录账号。

在本机交互式终端执行：

```powershell
& .\.venv\Scripts\python.exe .\serve.py credentials kali
```

输入客体用户名和密码，密码不回显，保存到当前 Windows 用户的凭据管理器，名称为 `VMwareLab/kali`。其他机器将 `kali` 替换为其登记 ID；更换电脑或 Windows 用户后重新设置。不要将密码放进聊天、登记表或客户端配置。

客体启动且 Tools 就绪后，可调用 `linux_run` 执行 `uname -s; id -un; pwd`，工作目录设为 `/tmp`，测试返回结果。客体命令功能尚待完成端到端验收。

## 运行说明

- 每个客户端启动独立 stdio 子进程，不监听 HTTP 端口、不后台轮询，日常运行通过本机 vmrun 完成。
- 多个客户端不要同时对同一虚拟机发出相反启停操作；当前没有操作锁。
- 客体命令按客体账号权限执行。超时只限制宿主等待，不保证终止客体进程。
- 命令输出先存入客体 `/tmp` 日志，宿主临时副本读取后删除；客体日志可自行清理。vmrun 使用的密码会作为本机进程参数传入。
- 虚拟机路径和命令输出会返回给客户端；客户端使用云端模型时，这些结果可能进入模型请求。
- `exists=false` 时检查 VMX 路径；凭据缺失时运行上述凭据命令；正常关机失败时检查 Tools。
- 本机登记表、虚拟环境和密码不属于分享内容。重新分享前检查包内容；`.gitignore` 不约束普通 ZIP 打包，也不会移除已跟踪文件。
