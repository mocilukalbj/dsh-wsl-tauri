# DSH WSL Tauri

Windows Tauri 桌面窗口，连接 WSL 中运行的 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)。

复用后端提供的完整 WebUI，不维护第二套前端。Windows 负责窗口和 WebView2；WSL 负责 Harness、工具执行、插件、工作区和会话。此项目是独立的社区原型，与 DeepSeek 官方无隶属关系。

## 功能

- 自动连接现有 WSL Web 服务并完成登录令牌交换。
- 校验页面包含 `__DSH_BOOT__` 启动清单。
- 显示 UI 构建版本及 WSL 已安装内核版本。
- 启动时比较版本和 EXE 哈希，不一致时先构建，成功后启动。
- 构建失败保留上次成功记录，不启动旧程序。
- 关闭窗口保留共享后端，不终止其他客户端使用的服务。
- 页面不获得 Tauri 原生 IPC 权限；主窗口限制为本地导航。

```text
Windows: Start-DSH → 版本检查 / Cargo 构建 → Tauri + WebView2
                                                   │
                                      localhost HTTP / WebSocket
                                                   │
WSL: Node.js → DeepSeek Harness → ~/.dsh / Linux 工作区
```

## 环境要求

Windows 10/11 x64，WSL2，已配置的 Linux 发行版，以及：

- Windows Microsoft Edge WebView2 Runtime。
- Windows Rust stable MSVC 工具链。
- Visual Studio 2022 C++ Build Tools（含 Windows SDK）。
- WSL Python 3、Node.js 和已安装且可运行的 `dsh`。
- Windows 能通过 localhost 访问 WSL 服务。

Tauri 构建环境见[官方说明](https://v2.tauri.app/start/prerequisites/)。Rust 可以装在系统 PATH 中，也可以放在项目 `tools/cargo`、`tools/rustup` 下；已有项目专用工具链时优先使用它。

## 快速开始

### 1. 准备 WSL 后端

在 WSL 中确认 `dsh` 已安装。若通过 NVM 安装，请设置正确的默认 Node 版本；版本检查会加载 NVM 并使用默认版本。

已有 `~/dsh-web.sh` 的用户可沿用自己的启动脚本。也可先在一个 WSL 终端中直接运行：

```bash
dsh web --no-open --host 127.0.0.1 --port 3080 2>&1 | tee -a ~/.dsh-web.log
```

保持该终端运行。日志需包含当前服务打印的带 token 的登录 URL；启动器从中获取认证信息。不要把此日志提交到仓库。

如果服务尚未运行，桌面启动器会尝试调用已有的 `~/dsh-web.sh start`。这个可选脚本需要在后台启动服务、写入 `~/.dsh-web.log`，并退出返回成功；本仓库不安装或替换用户的 WSL 服务脚本。

### 2. 配置 Windows 项目

克隆仓库到 Windows 本地磁盘，例如 `C:\Projects\dsh-wsl-tauri`。不支持从 UNC 路径直接运行。

```powershell
Copy-Item backend.example.json backend.json
notepad backend.json
```

填写实际的 WSL 发行版、Linux 用户、home 和端口。`home` 是 Linux 用户目录，如 `/home/alice`，不是 `/home/alice/.dsh`。`backend.json` 仅保存在本机，已被 Git 忽略。

### 3. 启动

双击 `Start-DSH.vbs`，或运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-DSH.ps1
```

首次启动需要下载 Rust 依赖并编译。构建输出在 `build.log`，EXE 位于 `target/release/dsh-wsl-tauri.exe`。启动入口同时负责初始化环境和版本检查，建议始终通过它打开应用。

C++ 工具默认通过 `vswhere` 查找。自定义安装位置可设置环境变量 `DSH_VSDEVCMD`，或创建被 Git 忽略的 `build.local.cmd`：

```bat
@set "DSH_VSDEVCMD=D:\BuildTools\Common7\Tools\VsDevCmd.bat"
```

## 内核更新与版本同步

更新 WSL 中的 dsh，保存工作并重启后端，然后关闭旧桌面窗口并重新运行启动入口。

1. 读取 NVM 默认环境中实际解析到的 `@deepseek-ai/dsh` 包版本。
2. 对比 `ui-build.json` 中上次成功版本和 EXE SHA-256。
3. 不一致时将版本嵌入 UI，并设置 Windows 程序的 ProductVersion/FileVersion。
4. 构建成功后再次检查内核版本，写入成功记录并启动。

窗口标题示例：`UI 0.1.5-rc.2 / 已安装内核 0.1.5-rc.2`。

“已安装内核”指磁盘包版本，不代表尚未重启的旧进程版本。此流程不自动升级或重启 WSL 后端，也不自动适配上游协议变化。WebUI 由服务实时提供；重新编译主要用于使壳的构建版本与内核一致。

Cargo 的 `0.1.0` 单独标识壳实现版本。直接运行 EXE 遇到内核版本不一致时，会提示使用启动入口。正在运行的 EXE 不会被强制关闭或覆盖。互斥锁防止多个启动器同时构建。

```powershell
# 仅检查并构建
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-DSH.ps1 -BuildOnly
# 修改壳源码后，强制重建
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-DSH.ps1 -BuildOnly -ForceBuild
```

## 验证

在安装了 Python 3 的环境运行：

```bash
python3 scripts/test_backend.py
```

这些测试不需要真实 WSL 服务，覆盖登录 URL 筛选、已有服务复用、端口占用保护和包版本识别。

在 WSL 内可检查实际连接；将路径替换为自己的 Windows 项目目录：

```bash
python3 /mnt/c/Projects/dsh-wsl-tauri/scripts/backend.py --home "$HOME" --port 3080 --version-only
python3 /mnt/c/Projects/dsh-wsl-tauri/scripts/backend.py --home "$HOME" --port 3080 --redact
```

不带 `--redact` 的连接输出包含临时登录信息，供桌面进程通过管道读取。

可选的 `scripts/check-webview.mjs` 通过临时 WebView2 调试端口 9227 检查真实窗口，要求 Windows Node.js 支持内置 WebSocket，并读取本机 `backend.json` 的端口。脚本会刷新页面，须在空闲窗口使用；截图和测试报告已被 Git 忽略。正常启动不启用调试端口。

## 当前状态与限制

已在 Windows + Ubuntu-24.04、Harness 0.1.5-rc.2 上验证构建、登录、工作区/会话列表、输入框、WebSocket，以及版本一致跳过、不一致重建、构建失败保留记录。

- 未提供安装包、签名、自动更新、托盘和原生文件打开功能。
- 尚未验收模型回复、工具执行及服务停止后的自动启动路径。
- 需要保留项目配置和 helper 文件，EXE 不是独立便携包。
- 不同上游版本若改变认证、启动日志或协议，需要调整适配代码。
- 默认只连接回环地址，不需要开放局域网端口或关闭后端认证。

## 许可

本项目采用 [MIT](LICENSE) 许可。DeepSeek Harness、Tauri 和各依赖分别遵循其自身许可；本仓库不包含 Harness 源码、用户数据、凭据或构建后的依赖树。
