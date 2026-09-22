# Cloudflare Tunnel + Launchd Setup Guide

Sets up a named Cloudflare tunnel (`dimple-api`) to expose the Dimple backend (port 8000) on `dimple-api.chokepointmonitor.com`, with auto-start via launchd.

---

## Prerequisites

- `cloudflared` installed (`brew install cloudflared`)
- Domain `chokepointmonitor.com` in your Cloudflare account
- Dimple backend runs on `localhost:8000`

---

## Step 1: Authenticate cloudflared

```bash
cloudflared tunnel login
```

This opens a browser. Select `chokepointmonitor.com` and authorize. A cert downloads to `~/.cloudflared/cert.pem`.

---

## Step 2: Create the named tunnel

```bash
cloudflared tunnel create dimple-api
```

Saves a tunnel credentials file to `~/.cloudflared/`. Note the tunnel UUID output.

---

## Step 3: Route DNS

```bash
cloudflared tunnel route dns dimple-api dimple-api.chokepointmonitor.com
```

This creates the DNS record automatically. No manual DNS config needed.

---

## Step 4: Create the config file

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /Users/ai-server/.cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: dimple-api.chokepointmonitor.com
    service: http://localhost:8000
  - service: http_status:404
```

Replace `<TUNNEL_UUID>` with the actual UUID from Step 2.

---

## Step 5: Test the tunnel

```bash
cloudflared tunnel run dimple-api
```

Verify: `curl https://dimple-api.chokepointmonitor.com/health`

Hit `Ctrl+C` to stop.

---

## Step 6: Launchd service (auto-start)

Create `~/Library/LaunchAgents/com.cloudflared.dimple-api.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflared.dimple-api</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>dimple-api</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/ai-server/.cloudflared/dimple-api.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/ai-server/.cloudflared/dimple-api.err.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.cloudflared.dimple-api.plist
```

Verify it's running:

```bash
launchctl list | grep com.cloudflared.dimple-api
```

---

## Step 7: Update frontend base URL

In `frontend/dimple-frontend/CourseService.swift` (and any other hardcoded `localhost:8000`):

```swift
// Before
private let baseURL = "http://localhost:8000"

// After
private let baseURL = "https://dimple-api.chokepointmonitor.com"
```

Build and test on device.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Tunnel won't start | Check `~/.cloudflared/dimple-api.err.log` |
| DNS not resolving | Verify record in Cloudflare dashboard → DNS |
| 502 errors | Backend not running on port 8000 |
| Cert expired | Re-run `cloudflared tunnel login` |

---

## Files Created

- `~/.cloudflared/cert.pem` — Cloudflare auth cert
- `~/.cloudflared/<UUID>.json` — Tunnel credentials
- `~/.cloudflared/config.yml` — Tunnel config
- `~/Library/LaunchAgents/com.cloudflared.dimple-api.plist` — Auto-start service
