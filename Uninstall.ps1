$ErrorActionPreference = "Stop"

# Define paths
$installDir = Join-Path $env:LOCALAPPDATA "restic-monitor"
$appDir = Join-Path $installDir "app"
$taskName = "restic-monitor"

Write-Host "Starting uninstallation of restic-monitor..." -ForegroundColor Cyan

try {
    # 1. Remove Scheduled Task
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Write-Host "Removing Scheduled Task: $taskName..."
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false | Out-Null
        Write-Host "Successfully removed Scheduled Task." -ForegroundColor Green
    } else {
        Write-Host "Scheduled Task '$taskName' not found. Skipping."
    }

    # 2. Remove registry entry (Apps & Features)
    $registryPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\restic-monitor"
    if (Test-Path $registryPath) {
        Write-Host "Removing registry entry: $registryPath..."
        Remove-Item -Path $registryPath -Recurse -Force
        Write-Host "Successfully removed registry entry." -ForegroundColor Green
    } else {
        Write-Host "Registry entry not found. Skipping."
    }

    # 3. Remove application files
    if (Test-Path $appDir) {
        Write-Host "Removing application directory: $appDir..."
        Remove-Item -Path $appDir -Recurse -Force
        Write-Host "Successfully removed application files." -ForegroundColor Green
    } else {
        Write-Host "Application directory '$appDir' not found. Skipping."
    }

    # 4. Remove the provisioned restic binary
    $binDir = Join-Path $installDir "bin"
    if (Test-Path $binDir) {
        Write-Host "Removing provisioned restic binary: $binDir..."
        Remove-Item -Path $binDir -Recurse -Force
        Write-Host "Successfully removed restic binary." -ForegroundColor Green
    }

    # Note: We are NOT removing the configDir ($installDir) itself,
    # to allow users to keep their env.json and settings.json for future reinstalls/updates.

    Write-Host "Uninstallation complete!" -ForegroundColor Green

    # Pause so the user can read the uninstallation output
    Write-Host ""
    Write-Host "Press Enter to exit..." -ForegroundColor Yellow
    Read-Host
} catch {
    Write-Error "Uninstallation failed: $_"
    exit 1
}
