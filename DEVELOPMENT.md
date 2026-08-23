# Development Guide

This guide covers how to run and build the restic-monitor application.

## Running the program

Run `uv main.py --debug`

## Building and Packaging

To create a distribution-ready package, use the provided automation script:

1. Run `.\package.ps1`.
2. This script handles cleaning up old builds, running PyInstaller via `uv`, and creating an `app.zip` file.
3. The resulting `app.zip` contains everything needed for a clean installation using `Install.ps1`.