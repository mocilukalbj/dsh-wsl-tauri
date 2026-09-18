param([switch]$BuildOnly, [switch]$ForceBuild)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$env:DSH_TAURI_ROOT = $root
$exe = Join-Path $root 'target\release\dsh-wsl-tauri.exe'
$stampPath = Join-Path $root 'ui-build.json'
$mutex = [Threading.Mutex]::new($false, 'Local\DSH-WSL-Tauri-Build')
$locked = $false
try {
    try { $locked = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw '另一个窗口正在检查或构建，请稍候。' }
    $config = Get-Content -LiteralPath (Join-Path $root 'backend.json') -Raw | ConvertFrom-Json
    $wslScript = '/mnt/' + $root.Substring(0,1).ToLowerInvariant() + $root.Substring(2).Replace('\','/') + '/scripts/backend.py'
    function Get-CoreVersion {
        $raw = & wsl.exe -d $config.distribution -u $config.user -- python3 $wslScript --home $config.home --port $config.port --version-only
        if ($LASTEXITCODE -ne 0) { throw '无法读取 WSL 内核版本。' }
        $version = ($raw | ConvertFrom-Json).version
        if ($version -notmatch '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$') { throw '内核版本格式错误。' }
        return $version
    }
    $version = Get-CoreVersion
    $stamp = $null
    if (Test-Path -LiteralPath $stampPath) {
        try { $stamp = Get-Content -LiteralPath $stampPath -Raw | ConvertFrom-Json } catch { $stamp = $null }
    }
    $needsBuild = $ForceBuild -or -not (Test-Path -LiteralPath $exe) -or $stamp.coreVersion -ne $version
    if (-not $needsBuild) { $needsBuild = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne $stamp.exeSha256 }
    if ($needsBuild) {
        $running = @(Get-Process -Name 'dsh-wsl-tauri' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe })
        if ($running.Count -gt 0) { throw '需要重新构建，请先关闭正在运行的 DSH WSL 窗口，再重新启动。后端无需关闭。' }
        Write-Host "正在构建 UI $version，与 WSL 内核版本对齐……"
        [IO.File]::WriteAllText((Join-Path $root 'core-version.txt'), $version + "`n", [Text.UTF8Encoding]::new($false))
        $env:TAURI_CONFIG = @{version=$version} | ConvertTo-Json -Compress
        Push-Location $root
        try {
            & $env:ComSpec /d /c ('""{0}" > "{1}" 2>&1"' -f (Join-Path $root 'build.cmd'), (Join-Path $root 'build.log'))
            if ($LASTEXITCODE -ne 0) { throw '构建失败，未启动旧版 UI。请查看项目中的 build.log。' }
        } finally { Pop-Location; Remove-Item Env:TAURI_CONFIG -ErrorAction SilentlyContinue }
        if ((Get-CoreVersion) -ne $version) { throw '构建期间内核版本发生变化，请重新启动以再次构建。' }
        $record = [ordered]@{coreVersion=$version; exeSha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash; builtAt=[DateTime]::UtcNow.ToString('o')}
        $temporary = $stampPath + '.tmp'
        [IO.File]::WriteAllText($temporary, ($record | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $stampPath -Force
        Write-Host "UI $version 构建完成。"
    } else { Write-Host "UI / 已安装内核 $version，版本一致，无需构建。" }
    if (-not $BuildOnly) { Start-Process -FilePath $exe -WorkingDirectory $root -WindowStyle Hidden }
} catch {
    Write-Host $_.Exception.Message
    if (-not $BuildOnly) {
        Add-Type -AssemblyName System.Windows.Forms
        [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'DSH WSL 启动失败') | Out-Null
    }
    exit 1
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
