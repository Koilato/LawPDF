---
name: windows-local-dev-troubleshooter
description: Diagnose recurring Windows local development failures in this workspace and similar repos. Use when a user reports Chinese encoding or mojibake, PowerShell vs cmd confusion, VSCode or Pylance saying imports or packages are missing while runtime works, backend or frontend startup and port binding failures, APPDATA or LOCALAPPDATA write problems, detached Start-Process issues, PyInstaller or Tcl/Tk packaging crashes, or Hugging Face/docling symlink errors on Windows.
---

# Windows Local Dev Troubleshooter

## Quick Start

1. Classify the failure before editing code:
- encoding or content corruption
- interpreter or workspace-root mismatch
- startup, port, or detached-launch problem
- filesystem permission or writable-dir problem
- packaging or runtime dependency problem
- Windows model-cache or symlink problem

2. Capture a baseline when the situation is unclear:
```powershell
.\skills\windows-local-dev-troubleshooter\scripts\windows_issue_snapshot.ps1 -ProjectRoot .
```

3. Read only the relevant section in [common-issues.md](references/common-issues.md).

## Workflow

### 1. Build the baseline

- Record the absolute project root, current shell, PowerShell version, code page, console encodings, and Python encoding environment variables.
- Check repo markers before touching code. In this repo, the fastest markers are `backend/`, `frontend/`, `logs/`, `scripts/start_backend.ps1`, `scripts/start_frontend.ps1`, and `.conda\case-pipeline\python.exe`.
- Check whether ports `8000` and `5173` are already listening.
- Read the newest backend and frontend logs before attempting detached restarts.

### 2. Sort the problem into the right bucket

#### Encoding or mojibake

- Distinguish file-content corruption from terminal display issues.
- If a file decodes cleanly as UTF-8 but contains known wrong-transcoded text saved into source, treat it as wrong content already saved into source.
- If source bytes are fine but console output is wrong, fix shell and code-page settings first.
- Scan maintained source before scanning generated output. Ignore `node_modules`, `dist`, caches, and build artifacts unless the user asks.
- Prefer ASCII fallback text when a blocking error string is already unstable.

Useful checks:
```powershell
Get-Content .\frontend\README.md -Encoding UTF8 -TotalCount 20
Select-String -Path .\\frontend\\src\\*.ts* -Pattern '\\uFFFD' -SimpleMatch
cmd /c chcp
```

#### Interpreter, workspace root, or import mismatch

- Verify whether the missing module is a real installed package or a repo-local source directory.
- Compare runtime working directory with editor workspace root before changing imports.
- Check the selected VSCode interpreter and opened folder depth before changing code.
- If runtime works only from one directory, the project likely depends on current-directory lookup rather than installation.

#### Startup, ports, or detached launch

- Reproduce once in the foreground before repairing background launch scripts.
- Check existing listeners on `8000` and `5173`.
- Read `logs\backend*.log` and `logs\frontend*.log` before restarting.
- On Windows, `Start-Process` can fail because of environment inheritance, quoting, or console lifetime. Validate the direct Python or npm command first, then wrap it.

#### Filesystem permission or writable-directory issues

- Do not assume `%APPDATA%`, `%LOCALAPPDATA%`, temp directories, or cache directories are writable from Codex, child processes, or packaged apps.
- If `os.makedirs(..., exist_ok=True)` still throws `WinError 183`, suspect permission or traverse checks rather than a true duplicate directory.
- Prefer an explicit override env var or a project-local writable directory for runtime data.

#### Packaging, Tk, or PyInstaller

- For packaged app failures, verify the source app works first.
- If the exe exits immediately, run it from `cmd` once or force logs to file.
- Suspect Tcl/Tk bundling when you see `init.tcl`, `_tkinter.TclError`, or DLL warnings.
- Keep packaging fixes minimal and separate from UI or business-logic changes.

#### Hugging Face, docling, or Windows symlink failures

- If Windows raises `WinError 1314`, suspect symlink creation during model-cache setup.
- Redirect caches to a writable local path or force copy-based behavior before blaming the input PDF.
- Treat first-run model downloads as environment setup, not document parsing failure.

## Repo-Specific Shortcuts

If you are working in this repository:

- Backend Python is expected at `.conda\case-pipeline\python.exe`.
- Common startup entry points are `scripts/start_backend.ps1` and `scripts/start_frontend.ps1`.
- Common logs are `logs/backend.out.log`, `logs/backend.err.log`, `logs/frontend.out.log`, and `logs/frontend.err.log`.
- Exported troubleshooting history is under `exports/codex_threads/`. Use [common-issues.md](references/common-issues.md) first instead of re-reading every thread.

## When To Read References

- Read [common-issues.md](references/common-issues.md) for recurring local failure patterns, rough frequencies, and concrete thread examples.
