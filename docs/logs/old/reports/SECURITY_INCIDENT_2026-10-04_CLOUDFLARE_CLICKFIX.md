# Security incident 2026-10-04: Cloudflare takeover and ClickFix infection

All times are JST (UTC+9) unless marked UTC. URLs are defanged. This report contains no executable malicious code.

## Summary

1. **Cloudflare account takeover.** Someone logged into the Cloudflare dashboard as the account owner and created an API token. That token was used to add an account-level Bulk Redirect. All 43 zones then returned `301 → hxxps://get-verification[.]co/<path>`, a ClickFix lure. Affected hosts included `be-flama`, `flama`, `flama-connect`, `gen-web` and every generated site. The origin servers and DNS were not modified.
2. **Dev PC infected through the lure.** The owner visited the redirected site and pasted the "verification" command into PowerShell. A PowerShell loader downloaded and started `update-KB5782864.exe`. Microsoft Defender blocked it about 2 s after launch and killed it about 36 s after launch.
3. **No data exfiltration found from the PC infection.** The takeover happened about 10 h before the PC infection, so the infection cannot be its cause. The root cause of the Cloudflare credential leak is still open.

## Timeline

| Time | Event |
|---|---|
| 10-03 15:58 UTC (10-04 00:58:48 JST) | Cloudflare `LOGIN` as the owner, followed by creation of the token `bulk-redirect-bot` (Config Settings Write, Dynamic URL Redirects Write) 5 s later. The speed suggests automation. |
| 10-04 01:03:03–07 | The new token creates a list, list items and an account ruleset with rules (Bulk Redirect). |
| 10-04 10:44:04 | The owner opens Windows Terminal and runs the pasted `irm … \| iex` command. |
| 10:44:26 | A hidden child PowerShell (`-nop -w 1`) runs the stage-3 loader. |
| 10:44:32.968 | `%LOCALAPPDATA%\Temp\update-KB5782864.exe` starts as PID 31372, user `chungtv\chung`. |
| 10:44:35.15 | Defender RTP blocks the process from opening its own image (`Reason: OnOpen`), which prevents unpacking of the embedded payload. Detection: `Trojan:Script/Wacatac.H!ml`. |
| 10:45:09.39 | Defender terminates PID 31372 and quarantines the file. |
| ~11:00 | The owner removes the Bulk Redirect. All sites serve normally again. |

## Evidence that no data left the PC

- **SRUM network usage** for the interval 09:54–10:54 records 35 apps but has no row for `update-KB5782864.exe`: 0 bytes sent and 0 bytes received. The next interval (10:54–11:43) has no row either.
- **SRUM app resource usage** shows 0 bytes read and 0 bytes written by the payload, in both foreground and background. Other apps in the same interval show normal counters. CPU use was about 0.05 s.
- **Prefetch** for the first 10 s lists 49 entries, all Windows system DLLs plus the executable itself. No networking or crypto DLLs (ws2_32, winhttp, wininet, crypt32) appear, and no browser `Cookies`, `Login Data`, `Local State`, SSH key or wallet paths.
- **Child processes:** MPLog shows no child or tainted processes of PID 31372. No new executables appear in SRUM or Prefetch after the payload. There is no persistence (Run keys, Startup, Scheduled Tasks, Services, WMI) and no Defender exclusions.
- **Hidden copies:** the loader tries to overwrite existing files in Recent, Temp, CrashDumps and the Edge/Chrome caches and rename them to `.exe`. No file matching the payload's size, hash or MZ header remains in those folders.
- **What the attacker did receive** were the loader beacons to `renotad[.]com/cloud/api` (launch status and VM status) and the victim's public IP.
- **Limitations:** process-creation and network auditing were off, and the firewall log was off.

## IOCs

| Type | Value |
|---|---|
| Lure domain | `get-verification[.]co` |
| Loader / C2 domain | `renotad[.]com` (paths `/cloud/<id>`, `/p?t=…`, `/cloud/api?…&event=launch_ok\|launch_fail`) |
| Loader UA / header | `WUA/5dd08126ca`, header `X-WUA: 5dd08126ca` |
| Payload SHA256 | `34c6dfffd1fbcad3f56a4b9e3c8bde28c1797544a0097c9760227bc3f35d2223` |
| Payload SHA1 | `4608bc4a9c60571a4d377bfcdf0a88432beecd14` |
| Payload MD5 | `941d025b471f45382acb36164d0d3101` |
| Payload size | 10,012,653 bytes (32-bit PE, not on VirusTotal as of 2026-10-04) |
| Stage hashes (from Codex analysis) | stage1 `7bf0dfeaa0ba10b7f61e64615a3905f9c3f536fa37fa0bc884caefce976ce5cf`, stage2 `594f1f5dda4d325214936939c5f711cadd52437d58157019c1944d9d66801089`, stage3 hex `6018d703fc500129b0dd5582f04d1cade9cb962c7f2213cd9c2411559be183ab`, stage3 decoded `10a9ca290f585897a421f6d941bbd2a2cb78aa51366c78006d8bb25be5702a27`, child launcher `3ff064629cff014e574823b5d2e2bda31d6bb01be0b7b25729c4b524145363fb` |
| Cloudflare token | `bulk-redirect-bot` (created 2026-10-04 00:58:53 JST) |

## Actions taken

- **VPS `chung_hostinger_vps`:**
  - No intrusion was found. The 2026-10-01 SSH brute force (about 980 attempts) failed.
  - Root password SSH is now allowed only from the host itself and from `wg0` (`/etc/ssh/sshd_config.d/00-incident-hardening.conf` plus a `Match` block). The previous config is backed up at `/root/backups/ssh-config-pre-incident-20261004T020149Z.tgz`.
  - ufw is enabled and allows 22, 80, 443, 51820/udp and all traffic on `wg0`. Ports 4789, 9090 and 9100 are closed to the internet.
- **Integrity checks:**
  - The Flama release `1775860` matches git byte-for-byte (1114 files).
  - ToolDeploy's git tree is clean. Neither app's database shows new users or admin changes.
- **PC containment (by Codex):** a `renotad.com` hosts entry and an outbound firewall rule were added, and the malicious line was removed from the PSReadLine history.
- **Cloudflare:** the Bulk Redirect was removed.

## Open items

- Delete the `bulk-redirect-bot` token. Roll all other Cloudflare tokens and the Global API Key. Change the Cloudflare and Gmail passwords from a clean device, enforce 2FA, and revoke sessions.
- Find the root cause of the Cloudflare credential leak. Check the actor IP and user agent of the 00:58:48 LOGIN, whether 2FA was enabled, and password reuse. Check infostealer and leak databases. A historical risk factor is the cracked Photoshop 2024 installed on 2025-08-05.
- Rotate the secrets that existed on the PC: the SSH keys `chung_hostinger_vps`, `sangserver` and `github_trinhchung_infra_vpn`, the GitHub CLI token, the AI tool tokens and the project `.env` secrets. Update the GitHub deploy secret after rotating the VPS key.
- Remove the Defender quarantine items (Windows Security → Protection history → Remove). Remove UltraViewer if it is not needed.
