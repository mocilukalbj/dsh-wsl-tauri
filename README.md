# DSH Tauri

**将 DeepSeek Harness 的 WebUI 带到桌面，并随内核版本变化自动重建 Tauri 外壳。**

DSH Tauri 直接加载 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 服务提供的完整 WebUI。界面、工具、插件、工作区和会话由内核提供；本项目负责原生窗口、后端连接、登录校验与构建版本同步。

支持原生 Linux 和 Windows＋WSL 两种运行方式，macOS 原生路径处于待验证阶段。WSL 是 Windows 用户的一种后端运行环境，不是项目的核心依赖。项目为独立社区原型，与 DeepSeek 官方无隶属关系。

## 核心工作方式

```text
启动入口 → 检查内核版本 / 外壳源码 / 成品哈希 → 必要时构建 → Tauri 窗口
                                                             │
                                                  本地 HTTP / WebSocket
                                                             │
                                                DeepSeek Harness WebUI
                                                会话 · 工作区 · 工具 · 插件
```

- **复用内核 WebUI**：页面由运行中的内核实时提供，无需维护一套独立前端。
- **自动重建外壳**：内核版本、外壳源码或成品发生变化时，先构建，成功后启动。
- **验证后端身份**：完成登录令牌交换，并检查 `__DSH_BOOT__` 启动清单。
- **复用已有服务**：关闭窗口会保留后端；端口被占用但无法认证时会报错，不替换正在运行的服务。
- **保留失败信息**：构建失败不启动旧程序，不覆盖上次成功记录；构建锁避免并发编译。
- **限制原生能力**：后端页面不获得 Tauri 原生 IPC 权限，窗口导航限制在应用页面与本地回环地址。

这里的“生成桌面 UI”是用 Tauri 承载内核现有 WebUI。内核升级并重启后，重新加载页面即可获得新 WebUI；外壳重建用于同步构建版本与外壳代码。上游认证或接口变化仍可能需要适配。

## 环境支持

| 桌面环境 | 后端位置 | 启动入口 | 验证状态 |
| --- | --- | --- | --- |
| Linux 原生 | 同一 Linux 用户环境 | `Start-DSH.sh` | Fedora 44：release 构建、登录 helper、窗口启动与后端连接已验证 |
| Windows | WSL 发行版内 | `Start-DSH.vbs` / `Start-DSH.ps1` | 初版已验证 Windows＋Ubuntu-24.04；本次跨平台改动尚未在 Windows 复测 |
| macOS 原生 | 同一 macOS 用户环境 | `Start-DSH.sh` | 已提供通用 Unix 路径，尚未实机构建或验收 |
| Windows 原生后端 | Windows | — | 尚未实现；当前 Windows 入口使用 WSL |

当前内核验证版本为 `0.1.5-rc.2`。其他 Linux 发行版和内核版本需按实际环境验证。

## 快速开始

### 1. 准备构建工具与内核

桌面侧需要 Rust stable / Cargo，以及对应系统的 [Tauri 构建依赖](https://v2.tauri.app/start/prerequisites/)。后端环境需要 Bash、Python 3、Node.js 和已安装且可运行的 `dsh`。

Linux 使用 GTK3 / WebKitGTK；Windows 使用 WebView2、MSVC 工具链与 Visual Studio C++ Build Tools；macOS 需要 Xcode Command Line Tools。具体安装命令以 Tauri 官方说明为准。

### 2. 准备后端

如果已有可用的 `dsh web` 服务，直接配置其日志来源。否则可在**后端所在环境**的终端运行：

```bash
# umask 保护含临时登录 URL 的新日志文件；保持此终端运行
umask 077
dsh web --no-open --host 127.0.0.1 --port 3080 2>&1 | tee -a ~/.dsh-web.log
```

日志必须包含当前进程输出的带 token 的登录 URL。已有服务占用 3080 时不要重复启动。

### 3. 选择桌面环境

**Linux 原生：**

```bash
git clone https://github.com/mocilukalbj/dsh-wsl-tauri.git
cd dsh-wsl-tauri
cp backend.example.json backend.json
```

编辑 `backend.json` 中的 `home` 为实际用户目录，例如 `/home/alice`，然后运行：

```bash
./Start-DSH.sh
```

**Windows＋WSL：**按 [Windows＋WSL 指南](docs/windows-wsl.md) 配置发行版和用户，再双击 `Start-DSH.vbs`。Windows 项目需位于本地盘符路径。

**macOS（待验证）：**可以尝试 Linux 的同一启动流程，将 `home` 改为 `/Users/alice`。本项目尚未提供 `.app` / DMG、签名或 macOS 桌面快捷方式。

> 仓库地址、Cargo 包名和二进制名称暂时保留 `dsh-wsl-tauri`，应用标识保持不变，以兼容已有安装与链接。显示名称为 **DSH Tauri**。

## 后端配置

`backend.json` 仅保存在本机，已被 Git 忽略。默认示例适用于原生 Unix；Windows 请使用 `backend.wsl.example.json`。

| 字段 | 用途 |
| --- | --- |
| `home` | 后端用户目录，如 `/home/alice`，不是 `~/.dsh`；使用绝对路径 |
| `port` | 本地回环端口，如 `3080` |
| `distribution` / `user` | 仅 Windows＋WSL 必需，分别为发行版名与 Linux 用户 |
| `log_glob` | 可选：额外日志绝对路径或 glob；只读取当前后端用户拥有的文件 |
| `journal_unit` | 可选：systemd **用户服务**名；文件日志不可用时查其 journal，端口空闲时可启动该服务 |
| `launcher` | 可选：后端 Bash 启动脚本；绝对路径或相对于 `home` 的路径，调用方式为 `bash <script> start` |

默认读取 `home` 下的 `.dsh-web.log`。所有路径和服务名均属于**后端环境**；Windows 配置中也应填写 WSL 路径。

systemd 用户服务示例：

```json
{
  "home": "/home/alice",
  "port": 3080,
  "journal_unit": "dsh-web.service"
}
```

其他启动器日志示例：

```json
{
  "home": "/home/alice",
  "port": 3080,
  "log_glob": "/home/alice/.local/state/dsh/*.log"
}
```

若端口空闲，配置的 `journal_unit` 优先用于启动；未配置时调用 `launcher`，默认尝试 `~/dsh-web.sh start`。脚本须后台启动服务、写入可读取的日志并退出。项目不安装服务、不升级内核、不自动重启已有后端。systemd 路径已有模拟测试，尚未验收真实服务冷启动。

不要把 token 写进配置、桌面快捷方式或 Git。当前服务日志丢失时，应先保存工作，再通过自己的后端启动方式重启并保留新日志。

## 内核更新与重建

1. 更新实际后端环境中的 `dsh`。
2. 保存工作，重启后端，让运行中的 WebUI 使用新内核。
3. 关闭旧桌面窗口，再通过启动入口打开。
4. 启动器比较已安装内核版本、外壳源码和二进制哈希；有变化就重建，无变化则直接启动。

窗口显示外壳构建时内核版本与当前磁盘上已安装的内核版本。**磁盘版本不代表运行中的服务版本**，启动器不会把旧后端强制重启。

```bash
./Start-DSH.sh --build-only    # 检查并按需构建
./Start-DSH.sh --force-build   # 强制重建并启动
```

Windows 对应 `-BuildOnly` / `-ForceBuild`，详见平台指南。

Linux 构建/运行日志为 `build-linux.log` / `desktop-linux.log`，macOS 对应 `build-darwin.log` / `desktop-darwin.log`。Windows 构建日志为 `build.log`。成功记录为 `ui-build-<platform>.json`（Windows 为 `ui-build.json`），均不提交到 Git。

Linux 桌面快捷方式应执行项目的 `Start-DSH.sh`，图标可使用 `icons/icon.png`。始终通过启动入口打开，才能执行版本检查与自动构建。需要保留项目目录、配置和 helper；二进制尚非独立便携应用。

## 验证与限制

后端和 Unix 启动器回归测试（Linux / macOS）：

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```

在实际后端环境验证版本与登录：

```bash
python3 scripts/backend.py --home "$HOME" --port 3080 --version-only
python3 scripts/backend.py --home "$HOME" --port 3080 --redact
# 使用 systemd 时追加 --journal-unit dsh-web.service
# 使用其他日志时追加 --log-glob '/absolute/path/*.log'
```

Linux 上可运行真实 WebKitGTK 认证回归检查（需要 Python GI 的 Gtk 3 / WebKit2 4.1 绑定）：

```bash
python3 scripts/check-webkit-auth.py
```

此测试使用本地模拟服务，验证首次认证、刷新和跨进程 cookie 持久化，不使用真实账号。主窗口直接以认证 URL 创建；本地连接提示页使用独立窗口，避免 WebKit 将认证 cookie 的跳转视为跨站访问。正常使用无需先在外部浏览器登录本地 WebUI。

不带 `--redact` 的结果包含临时登录 URL，供桌面进程通过管道读取。可选的 `scripts/check-webview.mjs` 是 Windows WebView2 调试工具，不作为跨平台验收结果。

- 尚未完整验收模型回复、工具执行及所有平台的服务冷启动流程。
- 尚未提供发布安装包、签名、自动更新、托盘或原生文件打开集成。
- 当前连接目标为本地回环地址，不支持任意远端 URL。
- 本地单元测试或一次编译成功不代表所有平台均已通过 UI 验收。

## 许可

[MIT](LICENSE)。DeepSeek Harness、Tauri 和依赖分别遵循其自身许可。本仓库不包含 Harness 源码、用户数据、凭据或构建依赖树。
