# Tunnel Hosting Guide — Dimple Backend Access

> **Why this exists:** The Dimple backend runs locally on Duk's MacBook Pro (M1). The iOS app needs to reach it from anywhere. This document explains how we bridge that gap, what went wrong, and where we're headed.

---

## The Problem

**Dimple's backend is not cloud-hosted.** It runs on `localhost:8000` on Duk's machine. But the iOS app (installed on Duk's phone) needs to talk to it from anywhere — home, golf course, wherever.

**Constraints:**
- No cloud VPS budget (project is pre-revenue)
- Backend must stay local (Supabase is cloud, but FastAPI app is not)
- iOS app needs a stable URL to hit
- Duk's machine sleeps, moves networks, restarts

---

## The Solution: Cloudflare Tunnel

We use **Cloudflare Tunnel** (`cloudflared`) to expose `localhost:8000` to the internet via a public URL. Think of it as a secure reverse proxy that Cloudflare manages for us.

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│  iOS App    │ ──────► │  Cloudflare Edge │ ──────► │  cloudflared│
│  (anywhere) │  HTTPS  │  (global CDN)    │  tunnel │  (local)    │
└─────────────┘         └──────────────────┘         └──────┬──────┘
                                                            │
                                                            ▼
                                                    ┌─────────────┐
                                                    │  FastAPI    │
                                                    │  localhost  │
                                                    │  :8000      │
                                                    └─────────────┘
```

**Why Cloudflare Tunnel?**
- **Free** (zero cost)
- **No open ports** on Duk's router (outbound connection only)
- **HTTPS termination** handled by Cloudflare
- **Works through NAT/firewalls** (coffee shop WiFi, cellular, whatever)

---

## Two Flavors of Tunnel

### 1. Temporary Tunnel (Quick & Dirty)

```bash
cloudflared tunnel --url http://localhost:8000
```

**What happens:**
- Cloudflare assigns a random subdomain: `https://abc123.trycloudflare.com`
- Tunnel stays alive as long as the process runs
- Kill the process → URL dies → new URL on restart

**Pros:**
- Zero config
- 30 seconds to start

**Cons:**
- URL changes every time
- Must update iOS app with new URL
- Dies if Terminal/tmux crashes
- Dies if Mac sleeps long enough

**When to use:** Local development, quick tests, emergencies.

---

### 2. Named Tunnel (The Real Setup)

```bash
# One-time setup
cloudflared tunnel create dimple-api
cloudflared tunnel route dns dimple-api dimple.chokepointmonitor.com

# Config file at ~/.cloudflared/config.yml
tunnel: <UUID>
credentials-file: ~/.cloudflared/<UUID>.json
ingress:
  - hostname: dimple.chokepointmonitor.com
    service: http://localhost:8000
  - service: http_status:404
```

**What happens:**
- Fixed hostname forever (e.g., `dimple.chokepointmonitor.com`)
- Runs as a system service (`launchd` on macOS)
- Auto-starts on boot, survives crashes, restarts on failure

**Pros:**
- Permanent URL — update iOS app once, never again
- Survives reboots, Terminal crashes, tmux deaths
- No manual intervention after setup

**Cons:**
- Requires a domain (or free `*.cfargotunnel.com` subdomain)
- One-time setup (~10 minutes)

**When to use:** Production, daily use, anything you don't want to babysit.

---

## What Went Wrong (War Stories)

### Incident 1: The HTTPS Mismatch

**Symptom:** "Invalid HTTP Request received" on server, iOS app shows HTML boilerplate error.

**Root cause:** Tunnel pointed to `https://localhost:8000` but backend runs plain HTTP.

```bash
# WRONG
cloudflared tunnel --url https://localhost:8000

# RIGHT
cloudflared tunnel --url http://localhost:8000
```

**Lesson:** Cloudflare handles HTTPS termination. The local backend stays HTTP.

---

### Incident 2: The Vanishing Terminals

**Symptom:** All tmux sessions gone overnight. Tunnel down. 12+ hours of uptime lost.

**Root cause:** Unknown. macOS did not reboot (uptime: 11+ hours). Terminal.app did not crash (no crash logs). tmux server simply ceased to exist.

**Suspects:**
- macOS aggressive app lifecycle management (App Nap, auto-quit)
- Memory pressure killing tmux server
- Terminal.app state restoration corruption
- Power/sleep event

**Lesson:** Don't rely on Terminal/tmux for infrastructure. Use `launchd` services.

---

### Incident 3: The 12-Hour Death

**Symptom:** Tunnel works fine for ~12 hours, then dies. Must manually restart.

**Root cause:** Temporary tunnel process killed by system (sleep, network change, etc.). No auto-restart.

**Lesson:** Temporary tunnels are for testing, not production.

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Backend (`localhost:8000`) | ✅ Running | Must be started manually (`uvicorn` or script) |
| Tunnel | ⚠️ Temporary | `cloudflared tunnel --url http://localhost:8000` |
| iOS App URL | 🔴 Manual update | Must update in app when tunnel restarts |
| Auto-restart | ❌ None | Tunnel dies → manual intervention required |

---

## Recommended Setup (Named Tunnel + launchd)

### Step 1: Create Named Tunnel

```bash
# Authenticate (opens browser)
cloudflared tunnel login

# Create tunnel
cd ~/Dimple
cloudflared tunnel create dimple-api
# Note the UUID output
```

### Step 2: Route DNS

```bash
# Using subdomain of existing domain
cloudflared tunnel route dns dimple-api dimple.chokepointmonitor.com
```

Or use free Cloudflare subdomain:
```bash
cloudflared tunnel route dns dimple-api dimple-<yourname>.cfargotunnel.com
```

### Step 3: Create Config

```bash
mkdir -p ~/.cloudflared

# Replace <UUID> with actual tunnel UUID
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <UUID>
credentials-file: /Users/ai-server/.cloudflared/<UUID>.json
ingress:
  - hostname: dimple.chokepointmonitor.com
    service: http://localhost:8000
  - service: http_status:404
EOF
```

### Step 4: Install as System Service

```bash
# Install launchd plist
sudo cloudflared service install

# Start service
sudo launchctl load /Library/LaunchDaemons/com.cloudflare.cloudflared.plist

# Verify it's running
sudo launchctl list | grep cloudflared
```

### Step 5: Update iOS App

Set the base URL to:
```
https://dimple.chokepointmonitor.com
```

Never change it again.

---

## Troubleshooting

| Problem | Check | Fix |
|---------|-------|-----|
| "Invalid HTTP Request" | Tunnel URL scheme | Use `http://localhost:8000`, not `https://` |
| "Something went wrong" (HTML in app) | Backend health | `curl http://localhost:8000/health` |
| Tunnel URL changes on restart | Using temporary tunnel | Switch to named tunnel |
| Tunnel dies overnight | Process not a service | Install as `launchd` service |
| Backend not reachable | `localhost:8000` down | Start backend (`uvicorn main:app`) |

---

## For Agents Reading This

**Quick context:**
- Backend = FastAPI on `localhost:8000` (Duk's Mac)
- Tunnel = `cloudflared` bridges local → internet
- iOS app hits the public tunnel URL
- Current setup is **temporary** — needs named tunnel + `launchd`

**If Duk says "tunnel is down":**
1. Check if backend is running: `curl http://localhost:8000/health`
2. Check if tunnel process exists: `ps aux | grep cloudflared`
3. If both dead → restart backend, then restart tunnel
4. If this happens repeatedly → push for named tunnel setup

**If Duk says "can't specify hostname" or "Invalid HTTP Request":**
- Tunnel is pointing to `https://localhost:8000` instead of `http://localhost:8000`
- Kill tunnel, restart with correct scheme

---

## Open Questions

1. **Should the backend also run as a `launchd` service?** Currently started manually. Auto-start on boot would mean zero intervention.
2. **What domain for production?** `dimple.chokepointmonitor.com` is temporary. Eventually `api.dimple.golf` or similar.
3. **Monitoring?** No alerting when tunnel dies. Cloudflare dashboard shows tunnel status, but no push notifications.

---

## Related Docs

- `API_CONTRACT.md` — Backend endpoints the iOS app expects
- `CHROLLO_ORCHESTRATION_PLAN.md` — How agents coordinate work
- Cloudflare docs: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

---

*Last updated: 2026-07-10*
*Status: Active issue — temporary tunnel in use, named tunnel recommended*
