# Git Network Mode Selection

## Quick Decision Table

- If `direct` probe succeeds, prefer `git -c http.proxy= -c https.proxy= ...` for the current command.
- If a local HTTP proxy probe succeeds, use `http://127.0.0.1:<port>` as a one-off override and keep global config unchanged unless the user asks for persistence.
- If a local SOCKS proxy probe succeeds, use `socks5h://127.0.0.1:<port>` so Git resolves DNS through the proxy too.
- If `github.com:443` fails but `ssh.github.com:443` succeeds, HTTPS routing may be the issue; consider SSH over `443` only after checking whether the user's SSH keys are already set up.
- If every probe fails, collect verbose evidence before changing repo config:
```powershell
curl.exe -I https://github.com
curl.exe -vk https://github.com
tracert -d github.com
git config --global --get http.proxy
git config --global --get https.proxy
```

## Common Local Proxy Ports

- HTTP candidates: `7890`, `10809`
- SOCKS candidates: `7891`, `10808`

Treat these as heuristics rather than guarantees. Probe the port before using it.

## Common Process Clues

If one of these is running, a local proxy is likely available even when Git is still pointed at the wrong mode:

- `v2rayN`
- `clash`
- `sing-box`
- `xray`
- `mihomo`

Useful check:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'v2rayN|sing-box|clash|xray|mihomo' } |
  Select-Object Name,ProcessId,ExecutablePath,CommandLine
```

## Persistence Rules

- Prefer one-off `git -c ...` overrides for `fetch`, `pull`, `push`, `clone`, and `ls-remote`.
- Set `git config --global http.proxy` or `https.proxy` only when the user explicitly wants Git to follow the same proxy mode by default.
- Unset global proxy only after confirming the current values and the user's intent.
- Avoid mixing proxy environment variables and Git global proxy settings unless there is a clear reason; mixed layers make later debugging harder.

## SSH Over 443

Use SSH over `443` only when:

- HTTPS is unreliable.
- `ssh.github.com:443` is reachable.
- The user already uses SSH keys or approves switching the remote.

Helpful probe:

```powershell
ssh -T -p 443 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL git@ssh.github.com
```

If SSH over `443` works and the user wants to switch:

```powershell
git remote set-url origin git@ssh.github.com:443/OWNER/REPO.git
```

Report the old and new remote URL explicitly before and after the change.
