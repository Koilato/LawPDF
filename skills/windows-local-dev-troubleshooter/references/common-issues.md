# Common Windows Failure Patterns

## Rough Frequency

These counts are overlapping and based on 43 exported Markdown threads under `exports/codex_threads`.

- Encoding, code-page mismatch, or wrong-transcoded source content: about 20 threads
- Startup, ports, detached background launch, or write-permission issues: about 13 threads
- Interpreter or workspace-root mismatch: about 10 threads
- Tk, PyInstaller, or Tcl-Tk packaging issues: about 7 threads
- Hugging Face or docling symlink failures: a strong Windows-specific pattern, surfaced across 6 related threads
- Direct network blockage: 2 threads

Use the counts only as prioritization signals. They overlap heavily.

## 1. Encoding And Wrong-Transcoded Source Content

### Signals

- The user explicitly says this is an encoding problem, not just terminal乱码.
- Files decode as UTF-8, but source contains nonsense Chinese such as `鍏夋槑`.
- Build still passes, which means the bytes are valid even though content is wrong.

### Local examples

- `exports/codex_threads/019d1def-e832-7bc2-b7a4-adf95945615e.md`
  - Frontend scan found UTF-8-readable files with content-level mojibake, especially `frontend/README.md`.
- `exports/codex_threads/019d1dfa-a079-7b83-9cc1-905e85a3ed47.md`
  - A config default keyword appeared as `鍏夋槑`.
- `exports/codex_threads/019d1d85-56f3-7530-b428-a7d67a458ec0.md`
  - `backend/app/main.py` was `UTF-8 with BOM`, but damaged string content still caused a real syntax error.
- `exports/codex_threads/019d1df1-d457-7551-b709-2f03f296c2e0.md`
  - PowerShell 5.1 session had mismatched code page and output encodings.

### What helped

- Separate display issues from content already saved wrong.
- Limit scans to maintained source first.
- Use ASCII fallback text when a blocking error string is already unstable.

## 2. Interpreter Or Workspace-Root Mismatch

### Signals

- Runtime import works from one directory, but editor analysis says `没有这个包`.
- The missing thing is a repo-local module, not an installed distribution.

### Local example

- `exports/codex_threads/019cf4f3-3d97-7b21-a92a-45f02b6b237b.md`
  - Runtime succeeded from project root because current directory was on `sys.path`, but editor analysis failed when workspace root or interpreter did not match.

### What helped

- Compare runtime cwd, workspace root, and selected interpreter before changing imports.

## 3. Windows Startup, Ports, And Background Launch Failures

### Signals

- Foreground run works, but detached start scripts fail.
- Logs say `listening`, but no port is visible.
- Child processes exit when the launcher console closes.
- `APPDATA` or log directories cause hidden failures.

### Local examples

- `exports/codex_threads/019d1d85-56f3-7530-b428-a7d67a458ec0.md`
  - Large cluster of issues around `Start-Process`, backend detaching, port probing, and environment inheritance.
- `exports/codex_threads/019cd93e-f8fd-7681-a60e-6c6ea3e5169a.md`
  - Runtime data dir under `%APPDATA%` raised permission and `WinError 183` style issues.

### What helped

- Foreground run first, detached wrapper second.
- Read logs before restarting.
- Use a project-local writable data dir or override env var when Windows profile paths are unreliable.

## 4. Hugging Face Or Docling Symlink Failures On Windows

### Signals

- `WinError 1314`
- Model download is conceptually correct, but cache population fails.

### Local example

- `exports/codex_threads/019cde4e-673f-71b0-9e94-34fd0ee80890.md`
  - `docling` failed on Windows because Hugging Face attempted symlink creation during first model download.

### What helped

- Force copy-based cache behavior or redirect cache before blaming the PDF.

## 5. Tk, PyInstaller, Or Tcl-Tk Packaging Failures

### Signals

- Packaged exe exits immediately.
- `_tkinter.TclError` or missing `init.tcl`.
- DLL warnings during build.

### Local example

- `exports/codex_threads/019cd855-3e0f-73f3-8f6c-3693631977c4.md`
  - Packaged `WordBatchReplace.exe` needed Tcl/Tk resources bundled correctly and runtime env vars set before the app could start.

### What helped

- Verify the source app first.
- Then package.
- Then run the packaged app from `cmd` or with file logging to capture the real startup failure.

## 6. Direct Network Blockage

### Signals

- `github.com:443` is unreachable, or network requests fail inside the environment.

### Local example

- `exports/codex_threads/019d1dfd-4b74-7b43-8ac5-ffa261d16915.md`
  - Local commit succeeded, but push failed because GitHub was unreachable.

### What helped

- Separate `code fixed` from `network blocked`.
- Report the exact blocked step and leave the local state clean.
