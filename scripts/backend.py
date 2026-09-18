"""Connect to the user's shared local service without taking ownership of it."""
import argparse
import glob
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def installed_version(home):
    script = '''export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
  nvm use default >/dev/null 2>&1 || exit 1
fi
command -v dsh
'''
    result = subprocess.run(['bash', '-c', script], env=dict(os.environ, HOME=str(home)),
                            capture_output=True, text=True, timeout=30, check=True)
    executable = Path(result.stdout.strip()).resolve(strict=True)
    data = json.loads((executable.parent.parent / 'package.json').read_text())
    if data.get('name') != '@deepseek-ai/dsh':
        raise RuntimeError('The resolved executable is not @deepseek-ai/dsh')
    version = data.get('version', '')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?', version):
        raise RuntimeError('Invalid installed Harness version')
    return version


def candidate_urls(log, port):
    matches = re.findall(r"http://[^\s\x1b<>]+", log)
    result = []
    for raw in reversed(matches):
        try:
            url = urllib.parse.urlsplit(raw)
            if (url.hostname not in ("127.0.0.1", "localhost") or url.port != port
                    or url.username or url.password or url.path not in ("", "/")):
                continue
            if not urllib.parse.parse_qs(url.query).get("token"):
                continue
            if raw not in result:
                result.append(raw)
        except ValueError:
            continue
    return result


def authenticate(url):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
    with opener.open(url, timeout=4) as response:
        html = response.read(4 * 1024 * 1024).decode("utf-8", errors="replace")
        if response.status != 200 or "__DSH_BOOT__" not in html:
            raise ValueError("The backend did not return its boot manifest")
    return True


def read_log(path):
    """Read a bounded tail; backend logs can grow for the lifetime of a service."""
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 131072))
            return stream.read().decode(errors='replace')
    except FileNotFoundError:
        return ""


def resolve(home, port, log_glob=None, journal_unit=None, launcher=None):
    def from_text(text):
        for url in candidate_urls(text, port):
            try:
                authenticate(url)
                return url
            except (OSError, ValueError, urllib.error.URLError):
                pass
        return None

    def connect():
        logs = [home / ".dsh-web.log"]
        if log_glob:
            extra = [Path(p) for p in glob.glob(log_glob)]
            extra = [p for p in extra if p.is_file() and p.stat().st_uid == os.getuid()]
            logs.extend(sorted(extra, key=lambda p: p.stat().st_mtime))
        url = from_text("\n".join(read_log(path) for path in logs))
        if url or not journal_unit:
            return url
        result = subprocess.run(
            ["journalctl", "--user", "--unit", journal_unit, "--no-pager", "-o", "cat", "-n", "500"],
            capture_output=True, text=True, timeout=10, check=True)
        return from_text(result.stdout)

    url = connect()
    if url:
        return {"url": url, "started": False}

    # An existing listener with an unknown/expired token must not be replaced.
    import socket
    with socket.socket() as probe:
        probe.settimeout(2)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError("The port is occupied but no valid login URL was found. Configure log_glob or journal_unit for the current backend; do not start a second service.")
    if journal_unit:
        command = ["systemctl", "--user", "start", journal_unit]
    else:
        launcher_path = Path(launcher).expanduser() if launcher else home / "dsh-web.sh"
        if not launcher_path.is_absolute():
            launcher_path = home / launcher_path
        if not launcher_path.is_file():
            raise RuntimeError("Backend is not running. Start dsh web, or configure journal_unit / launcher.")
        command = ["bash", str(launcher_path), "start"]
    env = dict(os.environ, HOME=str(home), DSH_HOME=str(home / ".dsh"), DSH_PORT=str(port), DSH_HOST="127.0.0.1")
    try:
        subprocess.run(command, env=env, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=75, check=True)
    except (subprocess.SubprocessError, OSError) as error:
        raise RuntimeError("The backend launcher failed; inspect its local logs") from error
    for _ in range(20):
        url = connect()
        if url:
            return {"url": url, "started": True}
        time.sleep(1)
    raise RuntimeError("Backend did not become ready with a valid boot manifest")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log-glob", help="Additional local backend log path or glob (same-user files only)")
    parser.add_argument("--journal-unit", help="Optional systemd user unit: read its journal and start it if the port is free")
    parser.add_argument("--launcher", help="Optional backend shell script, called with start when the port is free")
    parser.add_argument("--redact", action="store_true")
    parser.add_argument("--version-only", action="store_true")
    args = parser.parse_args()
    try:
        version = installed_version(Path(args.home))
        result = {"version": version} if args.version_only else dict(resolve(Path(args.home), args.port, args.log_glob, args.journal_unit, args.launcher), version=version)
        if args.redact and 'url' in result:
            result["url"] = result["url"].split("?", 1)[0] + "?token=[REDACTED]"
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({"error": str(error)}))
        raise SystemExit(1)
