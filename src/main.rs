#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Deserialize;
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::{
    path::PathBuf,
    process::{Command, Stdio},
    time::{Duration, Instant},
};
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

#[derive(Deserialize)]
struct Config {
    #[cfg(windows)]
    distribution: String,
    #[cfg(windows)]
    user: String,
    log_glob: Option<String>,
    journal_unit: Option<String>,
    launcher: Option<String>,
    home: String,
    port: u16,
}
#[derive(Deserialize)]
struct Backend {
    url: String,
    version: String,
}

const CORE_VERSION: &str = include_str!("../core-version.txt");

fn project_root() -> PathBuf {
    std::env::var_os("DSH_TAURI_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")))
}

fn backend_url() -> Result<tauri::Url, String> {
    let root = project_root();
    let config: Config = serde_json::from_slice(
        &std::fs::read(root.join("backend.json")).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    #[cfg(windows)]
    let mut command = {
        let script = root.join("scripts/backend.py").to_string_lossy().replace('\\', "/");
        let bytes = script.as_bytes();
        if bytes.len() < 3 || bytes[1] != b':' || !bytes[0].is_ascii_alphabetic() {
            return Err("The project must be on a Windows drive".into());
        }
        let wsl_script = format!("/mnt/{}/{}", (bytes[0] as char).to_ascii_lowercase(), &script[3..]);
        let mut command = Command::new("wsl.exe");
        command.args(["-d", &config.distribution, "-u", &config.user, "--", "python3", &wsl_script]);
        command
    };
    #[cfg(not(windows))]
    let mut command = {
        let mut command = Command::new("python3");
        command.arg(root.join("scripts/backend.py"));
        command
    };
    for (flag, value) in [
        ("--log-glob", &config.log_glob),
        ("--journal-unit", &config.journal_unit),
        ("--launcher", &config.launcher),
    ] {
        if let Some(value) = value {
            command.args([flag, value]);
        }
    }
    command.args(["--home", &config.home, "--port", &config.port.to_string()]);
    command
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .stdin(Stdio::null());
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    let mut child = command
        .spawn()
        .map_err(|e| format!("Cannot launch backend helper: {e}"))?;
    let deadline = Instant::now() + Duration::from_secs(120);
    loop {
        if child.try_wait().map_err(|e| e.to_string())?.is_some() {
            break;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            return Err("Backend connection timed out after 120 seconds".into());
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let output = child.wait_with_output().map_err(|e| e.to_string())?;
    if !output.status.success() {
        let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap_or_default();
        return Err(value["error"]
            .as_str()
            .unwrap_or("Backend helper failed")
            .to_string());
    }
    let backend: Backend =
        serde_json::from_slice(&output.stdout).map_err(|_| "Invalid backend response")?;
    if backend.version != CORE_VERSION.trim() {
        return Err(format!(
            "UI {} / 已安装内核 {}：请关闭此窗口，通过桌面快捷方式启动以自动构建。",
            CORE_VERSION.trim(),
            backend.version
        ));
    }
    let url = tauri::Url::parse(&backend.url).map_err(|_| "Invalid backend URL")?;
    if url.scheme() != "http"
        || !matches!(url.host_str(), Some("127.0.0.1" | "localhost"))
        || url.port() != Some(config.port)
        || url.path() != "/"
        || !url.username().is_empty()
        || url.password().is_some()
        || !url
            .query_pairs()
            .any(|(key, value)| key == "token" && !value.is_empty())
    {
        return Err("Backend URL must be the configured authenticated loopback address".into());
    }
    Ok(url)
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title(format!("DeepSeek Harness · UI {} / 已安装内核 {}", CORE_VERSION.trim(), CORE_VERSION.trim()))
                .inner_size(1280.0, 860.0).min_inner_size(800.0, 560.0)
                .on_navigation(|url| {
                    matches!(url.scheme(), "tauri" | "about")
                        || matches!(url.host_str(), Some("tauri.localhost"))
                        || (url.scheme() == "http" && matches!(url.host_str(), Some("127.0.0.1" | "localhost")))
                })
                .build()?;
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                match backend_url() {
                    Ok(url) => {
                        if window.navigate(url).is_err() {
                            let _ = window.eval("document.getElementById('status').textContent='无法打开后端页面。请检查本地后端服务。'");
                        }
                    }
                    Err(error) => {
                        let message = serde_json::to_string(&format!("连接失败：{error}")).unwrap();
                        if let Some(window) = handle.get_webview_window("main") {
                            let _ = window.eval(&format!("document.getElementById('status').textContent={message}"));
                        }
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Tauri application failed");
}
