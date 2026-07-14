# Tunnel Infrastructure Spec — Dimple Backend Access

> **Status:** Draft v1 — for discussion with Duk tomorrow
> **Goal:** Replace temporary Cloudflare tunnel with named tunnel + launchd service

---

## Current State (Problem)

| Component | Status | Issue |
|-----------|--------|-------|
| Backend (`localhost:8000`) | ✅ Running | Started manually, dies if Terminal closes |
| Tunnel | ⚠️ Temporary | `cloudflared tunnel --url http://localhost:8000` |
| iOS App URL | 🔴 Manual update | New random URL every restart |
| Auto-restart | ❌ None | Tunnel dies → manual intervention required |

**Pain points experienced:**
- Tunnel dies overnight (12-hour death pattern)
- tmux sessions vanish unpredictably
- iOS app breaks when URL changes
- Must babysit infrastructure

---

## Target State (Solution)

Named Cloudflare Tunnel + `launchd` service for zero-intervention operation.

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│  iOS App    │ ──────► │  Cloudflare Edge │ ──────► │  cloudflared│
│  (anywhere) │  HTTPS  │  (global CDN)    │  tunnel │  (launchd)  │
└─────────────┘         └──────────────────┘         └──────┬──────┘
                                                            │
                                                            ▼
                                                    ┌─────────────┐
                                                    │  FastAPI    │
                                                    │  localhost  │
                                                    │  :8000      │
                                                    └─────────────┘
```

**Benefits:**
- Fixed hostname forever (e.g., `dimple.chokepointmonitor.com`)
- Auto-starts on boot, survives crashes
- No manual URL updates in iOS app
- Works through sleep, network changes, reboots

---

## Implementation Steps

### Step 1: Create Named Tunnel (One-time)

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

Set base URL to:
```
https://dimple.chokepointmonitor.com
```

Never change it again.

---

## Open Questions (For Duk Tomorrow)

### Q1: Should the backend also run as a `launchd` service?

Currently started manually (`uvicorn main:app`). Options:
- **A:** Keep manual — tunnel auto-starts, backend stays manual (simplest)
- **B:** Backend as `launchd` too — fully autonomous, zero intervention (more setup)
- **C:** Hybrid — `launchd` for tunnel, shell script that starts both backend + tunnel (middle ground)

### Q2: What domain for production?

- `dimple.chokepointmonitor.com` — reuse existing domain (quick)
- `api.dimple.golf` — buy/register new domain (cleaner branding, extra cost/hassle)
- `dimple-<name>.cfargotunnel.com` — free Cloudflare subdomain (zero cost, less professional)

### Q3: Monitoring and alerting?

- **None** — check manually when app breaks (current reality)
- **Cloudflare dashboard** — check tunnel status online (passive)
- **Simple health check** — cron/heartbeat that pings `/health` and alerts if down (active)

---

## Files Referenced

- `docs/TUNNEL_HOSTING.md` — detailed guide with war stories and troubleshooting
- `docs/API_CONTRACT.md` — backend endpoints the iOS app expects

---

## Success Criteria

- [ ] Named tunnel created and DNS routed
- [ ] `launchd` service installed and running
- [ ] iOS app updated with fixed URL
- [ ] Tunnel survives reboot without manual intervention
- [ ] Backend reachable from iOS app after 24+ hours

---

*Drafted: 2026-07-14*
*Next: Review with Duk, decide on open questions, then implement*
