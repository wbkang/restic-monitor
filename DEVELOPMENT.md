# Development Guide

This guide covers how to run and build the restic-monitor application.

## Running the program

Run `uv main.py --debug`

## Building and Packaging

To create a distribution-ready package, use the provided automation script:

1. Run `.\package.ps1`.
2. This script handles cleaning up old builds, running PyInstaller via `uv`, and creating an `app.zip` file.
3. The resulting `app.zip` contains everything needed for a clean installation: extract it and double-click `install.cmd` (or run `Install.ps1` from a terminal; `.ps1` cannot be double-clicked from Explorer).

## Install behavior

- `Install.ps1` self-elevates, always downloads the latest restic release from GitHub into `%LOCALAPPDATA%\restic-monitor\bin` (verified against the release `SHA256SUMS`), copies the app, registers the scheduled task and the Apps & Features entry, then starts the app.
- Re-running the installer upgrades in place: existing `settings.json` and `env.json` are untouched.
- `restic_exe` in `settings.json` is optional; when omitted the app uses the provisioned `bin\restic.exe`.