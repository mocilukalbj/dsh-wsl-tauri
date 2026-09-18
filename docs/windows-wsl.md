# Windows＋WSL

此模式由 Windows 承载 Tauri / WebView2 窗口，WSL 运行 DeepSeek Harness、工具和工作区。项目也提供 [Linux 原生路径](../README.md)，无需 WSL。

## 环境

- Windows 10/11 x64、WSL2 和已配置的发行版。
- Microsoft Edge WebView2 Runtime。
- Rust stable MSVC 与 Visual Studio 2022 C++ Build Tools（含 Windows SDK）。
- WSL 中可运行的 Bash、Python 3、Node.js 和 `dsh`。
- Windows 可经 localhost 访问 WSL 后端。

完整构建要求见 [Tauri 官方说明](https://v2.tauri.app/start/prerequisites/)。

## 配置与启动

在 WSL 中按 [后端准备步骤](../README.md#2-准备后端) 启动或确认现有服务。使用 NVM 时需配置默认 Node 版本；版本检查会加载 NVM 默认环境。

将仓库放在 Windows 本地盘，例如 `C:\Projects\dsh-wsl-tauri`。当前不支持 UNC 路径。

```powershell
Copy-Item backend.wsl.example.json backend.json
notepad backend.json
```

填写实际的发行版、用户和 home：

```json
{
  "distribution": "Ubuntu-24.04",
  "user": "alice",
  "home": "/home/alice",
  "port": 3080
}
```

可追加与原生 Linux 相同的 `log_glob`、`journal_unit`、`launcher` 字段，路径均在 WSL 内。旧版 `backend.json` 仍然兼容。

双击 `Start-DSH.vbs`，或执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-DSH.ps1
# 只检查和构建
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-DSH.ps1 -BuildOnly
# 强制构建
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-DSH.ps1 -BuildOnly -ForceBuild
```

启动器会检查内核版本、源码与 EXE 哈希，必要时构建。构建失败不会启动旧程序；运行中的 EXE 不会被强制关闭或覆盖。构建日志为 `build.log`，成品为 `target/release/dsh-wsl-tauri.exe`。

已有项目专用 Rust 工具链时，优先使用 `tools/cargo`、`tools/rustup`。C++ 工具默认通过 `vswhere` 查找。自定义路径可设置 `DSH_VSDEVCMD`，或创建已忽略的 `build.local.cmd`：

```bat
@set "DSH_VSDEVCMD=D:\BuildTools\Common7\Tools\VsDevCmd.bat"
```

## 验证状态

初版在 Windows＋Ubuntu-24.04、Harness 0.1.5-rc.2 上验证了构建、登录、工作区/会话列表、输入框、WebSocket 和版本重建流程。本次新增的源码哈希检查、通用日志参数尚未在 Windows 实机复测。

后端 helper 测试可在 WSL 中运行：

```bash
python3 scripts/test_backend.py
```

项目在 Windows 盘上时，使用 `/mnt/c/.../scripts/backend.py` 检查实际连接。
可选 `scripts/check-webview.mjs` 使用 WebView2 调试端口 9227 检查窗口，会刷新页面，应在空闲窗口运行；正常启动不启用调试端口。
