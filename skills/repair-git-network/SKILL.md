---
name: repair-git-network
description: Stabilize Git command execution on Windows when Codex encounters intermittent failures caused by switching between TUN, direct, and local proxy modes. Use when `git fetch`, `git pull`, `git push`, `git ls-remote`, `git clone`, or GitHub SSH/HTTPS checks fail, hang, or behave inconsistently after enabling or disabling Clash, v2rayN, sing-box, Xray, Mihomo, TUN mode, or manual HTTP/SOCKS proxy settings.
---

# Repair Git Network

## Quick Start

1. Capture the current Git and network state before changing anything:
```powershell
.\skills\repair-git-network\scripts\git_network_snapshot.ps1 -RepoRoot . -Remote origin -RunGitProbe
```

2. Read `RecommendedMode` and the `SuggestedGit*` lines near the end of the output.

3. Re-run the intended Git command with a one-off override first:
```powershell
git -c http.proxy= -c https.proxy= fetch origin
git -c http.proxy=http://127.0.0.1:10809 -c https.proxy=http://127.0.0.1:10809 fetch origin
git -c http.proxy=socks5h://127.0.0.1:10808 -c https.proxy=socks5h://127.0.0.1:10808 fetch origin
```

4. Persist proxy configuration with `git config --global` only if the user explicitly wants the behavior to survive future sessions.

## Workflow

### 1. Inspect without mutating state

- Record the repo root, remote URL, branch, Git version, proxy environment variables, and global or local Git proxy config.
- Check whether common local proxy ports are listening before assuming a proxy URL exists.
- Check whether common proxy processes are running before blaming Git itself.
- Probe `github.com:443` and `ssh.github.com:443`.
- If the situation is unclear or Git just failed, run the built-in `git ls-remote` probes with `-RunGitProbe`.

### 2. Prefer the smallest-scope repair

- Prefer `git -c http.proxy=... -c https.proxy=... <command>` over changing global Git config.
- If TUN or direct routing works, explicitly clear proxy for the one Git command instead of unsetting global config immediately.
- If only a local HTTP proxy works, use `http://127.0.0.1:<port>` for that command.
- If only a local SOCKS proxy works, use `socks5h://127.0.0.1:<port>` so DNS resolution also goes through the proxy.
- If `ssh.github.com:443` is reachable but HTTPS remains unreliable, consider SSH over port `443` only after confirming the user is comfortable with remote or SSH config changes.

### 3. Persist carefully

- Do not write `git config --global http.proxy` or `git config --global https.proxy` unless the user explicitly asks for a durable default.
- Verify the existing proxy value before changing it, and report the exact before or after state.
- Keep repo-local proxy config rare; prefer per-command overrides unless this repository genuinely needs behavior different from other repositories.
- Avoid changing credential helpers, remote URLs, or SSH config until the probe output shows proxy-mode switching is not the primary issue.

## Common Command Patterns

- Direct one-off:
```powershell
git -c http.proxy= -c https.proxy= ls-remote origin
```

- Local HTTP proxy one-off:
```powershell
git -c http.proxy=http://127.0.0.1:10809 -c https.proxy=http://127.0.0.1:10809 ls-remote origin
```

- Local SOCKS proxy one-off:
```powershell
git -c http.proxy=socks5h://127.0.0.1:10808 -c https.proxy=socks5h://127.0.0.1:10808 ls-remote origin
```

- Persist only on request:
```powershell
git config --global http.proxy http://127.0.0.1:10809
git config --global https.proxy http://127.0.0.1:10809
git config --global --unset-all http.proxy
git config --global --unset-all https.proxy
```

## When To Read References

- Read [mode-selection.md](references/mode-selection.md) when you need the decision table, proxy-port heuristics, or SSH-over-443 fallback guidance.
