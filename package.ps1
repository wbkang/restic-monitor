$ErrorActionPreference = "Stop"

Write-Host "Starting packaging process..." -ForegroundColor Cyan

# 1. Clean up previous builds
$buildDirs = @("build", "dist")
foreach ($dir in $buildDirs) {
    if (Test-Path $dir) {
        Write-Host "Removing old build directory: $dir"
        Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 2. Run PyInstaller
if (Test-Path "main.spec") {
    Write-Host "Running PyInstaller via uv..."
    # Using uv run pyinstaller to ensure we use the environment's PyInstaller
    uv run pyinstaller --noconfirm main.spec
} else {
    Write-Error "main.spec not found!"
    exit 1
}

# 3. Verify result
if (Test-Path "app.zip") {
    Write-Host "Packaging successful! Created app.zip in the current directory." -ForegroundColor Green
} else {
    Write-Warning "Packaging finished but app.zip was not found. Check PyInstaller output or main.spec configuration."
}