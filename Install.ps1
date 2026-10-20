param([switch]$Elevated)

$ErrorActionPreference = "Stop"

# Self-elevate if not running as Administrator.
# -RunLevel Highest on the scheduled task requires the registering process to be elevated.
$principalCheck = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Elevation required for -RunLevel Highest. Relaunching as admin..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Elevated" `
        -Verb RunAs
    exit
}

# App metadata for Apps & Features registration
$appDisplayName   = "restic-monitor"
$appDisplayVersion = "1.0.0"
$appPublisher      = "Woongbin Kang"
$appDescription    = "Backup Monitoring Tool for Scheduled Backups"

# Define paths
$installDir = Join-Path $env:LOCALAPPDATA "restic-monitor"
$appDir = Join-Path $installDir "app"
$configDir = $installDir
$taskName = $appDisplayName
$exePath = Join-Path $appDir "$appDisplayName.exe"

# Source directory (the folder this script file lives in).
# Use $PSScriptRoot, not Get-Location: -Verb RunAs starts the elevated process in system32.
$currentDir = $PSScriptRoot

Write-Host "Starting installation of restic-monitor..." -ForegroundColor Cyan

# Terminate any running restic processes to prevent file locking conflicts
$resticProcesses = Get-Process -Name "restic" -ErrorAction SilentlyContinue
if ($resticProcesses) {
    Write-Host "Found $($resticProcesses.Count) running restic process(es). Terminating..." -ForegroundColor Yellow
    $resticProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "Restic processes terminated." -ForegroundColor Green
}

try {
    # 1. Create directories
    if (-not (Test-Path $appDir)) {
        Write-Host "Creating application directory: $appDir"
        New-Item -Path $appDir -ItemType Directory -Force | Out-Null
    }

    # 1.5 Stop Scheduled Task if running (to prevent file locking during update/install)
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Write-Host "Checking if task '$taskName' is running..."
        $runningTasks = Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo
        if ($runningTasks.NumberOfRunningTasks -gt 0) {
            Write-Host "Stopping task '$taskName' to prevent file locking..."
            Stop-ScheduledTask -TaskName $taskName
            Start-Sleep -Seconds 2 # Give it a moment to release files
        }
    }

    # 1.6 Stop the running tray app to release file locks on the exe being overwritten
    $appProcesses = Get-Process -Name $appDisplayName -ErrorAction SilentlyContinue
    if ($appProcesses) {
        Write-Host "Stopping running $appDisplayName process(es)..." -ForegroundColor Yellow
        $appProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }

    # 2. Copy application files
    # We assume the 'app' folder (from PyInstaller) is in the same directory as this script is running from
    $sourceAppDir = Join-Path $currentDir "app"
    if (Test-Path $sourceAppDir) {
        Write-Host "Copying application files from $sourceAppDir to $appDir..."
        Copy-Item -Path "$sourceAppDir\*" -Destination $appDir -Recurse -Force

        # Also copy Uninstall.ps1 so it can be triggered via Apps & Features
        $uninstallSrc = Join-Path $currentDir "Uninstall.ps1"
        if (Test-Path $uninstallSrc) {
            Write-Host "Copying Uninstall.ps1 to $installDir..."
            Copy-Item -Path $uninstallSrc -Destination $installDir -Force
        }
    } else {
        Write-Warning "Could not find '$sourceAppDir'. Ensure you are running this script from the distribution folder containing the 'app' directory."
        # We don't exit here because maybe it's already installed and we just want to fix tasks/configs
    }

    # 3. Create configuration files if they don't exist
    $envJsonPath = Join-Path $configDir "env.json"
    $settingsJsonPath = Join-Path $configDir "settings.json"

    if (-not (Test-Path $envJsonPath)) {
        Write-Host "Creating default env.json..."
        $envTemplate = @'
{
    "RESTIC_REPOSITORY": "",
    "RESTIC_PASSWORD": ""
}
'@
        Set-Content -Path $envJsonPath -Value $envTemplate -Encoding UTF8
    }

    if (-not (Test-Path $settingsJsonPath)) {
        Write-Host "Creating default settings.json..."
        $settingsTemplate = @'
{
    "restic_exe": "C:\\bin\\restic.exe",
    "args": [
        "backup",
        "-v",
        "--use-fs-snapshot", 
        "--iexclude-file=C:\\Users\\myuser\\OneDrive\\restic-exclude.txt",
        "C:\\",
        "C:\\Program Files (x86)\\Battle.net", 
        "C:\\Program Files (x86)\\Origin Games",
        "C:\\Program Files (x86)\\Steam",
        "C:\\Program Files (x86)\\Ubisoft"
    ],
    "min_idle_seconds": 300,
    "min_seconds_between_backups": 900,
    "no_backup_warning_seconds": 3600,
    "ignore_exit_code_3": false
}
'@
        Set-Content -Path $settingsJsonPath -Value $settingsTemplate -Encoding UTF8
    }

    # 4. Register Scheduled Task
    Write-Host "Registering Scheduled Task: $taskName..."
    if (Test-Path $exePath) {
        $action = New-ScheduledTaskAction -Execute $exePath
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        
        # We use the principal/settings to match user's requirement for "highest privileges" and no timeout
        Register-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -TaskName $taskName -Force -ErrorAction Stop | Out-Null
        Write-Host "Successfully registered Scheduled Task." -ForegroundColor Green

        # 5. Register in Windows Apps & Features (Registry)
        $registryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\restic-monitor"
        Write-Host "Registering in Windows Apps & Features..."
        if (-not (Test-Path $registryPath)) {
            New-Item -Path $registryPath -Force | Out-Null
        }
        Set-ItemProperty -Path $registryPath -Name "DisplayName" -Value $appDisplayName
        Set-ItemProperty -Path $registryPath -Name "DisplayIcon" -Value "`"$exePath`",0"
        Set-ItemProperty -Path $registryPath -Name "QuietDescription" -Value $appDescription
        Set-ItemProperty -Path $registryPath -Name "DisplayVersion" -Value $appDisplayVersion
        Set-ItemProperty -Path $registryPath -Name "Publisher" -Value $appPublisher
        Set-ItemProperty -Path $registryPath -Name "UninstallString" -Value "powershell.exe -ExecutionPolicy Bypass -File `"$installDir\Uninstall.ps1`""
        Set-ItemProperty -Path $registryPath -Name "NoModify" -Value 1
        Set-ItemProperty -Path $registryPath -Name "NoRepair" -Value 1

        # 6. Start the app now (the AtLogOn trigger would otherwise wait for next logon)
        Write-Host "Starting scheduled task '$taskName'..."
        Start-ScheduledTask -TaskName $taskName
        Write-Host "$appDisplayName started." -ForegroundColor Green
    } else {
        Write-Error "Could not find executable at $exePath. Cannot create scheduled task."
    }

    Write-Host "Installation complete!" -ForegroundColor Green
} catch {
    Write-Error "Installation failed: $_"
    if ($Elevated) { Read-Host "Press Enter to exit" }
    exit 1
}

if ($Elevated) { Read-Host "Press Enter to exit" }
