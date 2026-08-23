# TODO

## Installation & Packaging Improvements
- [ ] Upgrade `Install.ps1` and `Uninstall.ps1` to include Windows "Apps & Features" registry integration (so it shows up in Settings).
- [x] Implement an "Update" capability in `Install.ps1` that doesn't lose configuration.
- [x] Create packaging automation (e.g., `package.ps1`) to automatically zip the `dist/app` folder into a distributable `.zip`.

## Future Enhancements
- [ ] Automate Restic path validation within the installation script.
- [ ] Automatically download and update the latest `restic` binary from [GitHub releases](https://github.com/restic/restic/releases).