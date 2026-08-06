# Agent Status Board

> **Who updates this:** Claude Code (frontend agent)  
> **Who reads this:** Kanary (OpenClaw orchestrator), Duk (conductor)  
> **When to update:** After every meaningful progress step, blocker, or completion  
> **Rule:** If you're Claude Code and you haven't updated this in >2 hours of work, update it.

---

## Claude Code — Current Task (2026-08-05 — v1.0.0 push)

- **Task:** v1.0.0 — three features in one night (with Duk on-device testing).
- **Working branch:** `feature/v1-frontend-fixes` (off `Kanary`) → PR into `Kanary`,
  Duk merges. Per Chrollo plan: features land via PRs into Kanary, no racing the branch.
- **Build:** green (xcodebuild, generic iOS Simulator) after every change below.

**Committed on `feature/v1-frontend-fixes` (pushed):**
- 🔴→🟢 **Base URL fixed.** All 4 services pointed at a dead ephemeral tunnel
  (`evidence-dialogue-chronicle-officers.trycloudflare.com` — DNS no longer resolves;
  this URL was still committed on `Kanary`). Swapped all 4 → the stable named tunnel
  `https://dimple-api.chokepointmonitor.com` (verified live, 200). **Nothing
  connected before this.**
- ✅ **Feature #2 (Coach loading indicator).** Was ~80% already built (optimistic
  user bubble, typing indicator, inline retry all pre-existed). Added the missing
  piece: `CoachError` classification in `CoachService` → friendly copy for
  timeout / connection-lost / offline / 500, replacing the raw
  "Network connection was lost" string. Needs Duk taste test.

**In progress (NOT committed — working tree only):**
- 🟡 **Bug #3 (course-selection kickback).** Instrumented `NewRoundView` with
  `NAVLOG` tracing (DEBUG-only) + hardened the one destructive line: the
  `routeView` fallback no longer resets the nav path to root when the scorecard VM
  is momentarily nil (that reset == the "kicked back to search" symptom). Held out
  of the commit until a simulator run + `NAVLOG` console paste confirms the fix;
  debug logging will be stripped before it lands.

**Deferred per Duk:**
- 📋 **Feature #1 (Manual Course Entry).** Backend not shipped (verified live
  OpenAPI: no `/courses/manual`, no `manual_course` on `RoundPayload`). Wrote
  `docs/MANUAL_COURSE_ENTRY_BACKEND_CONTRACT.md` — the exact contract Kanary needs
  (recommends embedding `manual_course` in `POST /rounds`, no new endpoint).
  Frontend build waits on Kanary shipping the backend half.

### Kanary — action needed (contract is yours; I'm proposing, not editing)
- **`API_CONTRACT.md` — Manual Course Entry:** fold in the shape from
  `docs/MANUAL_COURSE_ENTRY_BACKEND_CONTRACT.md` (or pick an alternative) and ship
  the backend half to the live API. Per the Chrollo plan I did **not** edit
  `API_CONTRACT.md` — that seam is yours. Frontend is scoped and ready.
- **FYI (no contract change):** tonight's frontend commits change no request/response
  shape — just the base URL (not in the contract) and client-side error copy.

**Backend Status (verified live against the new tunnel):**
- ✅ `POST /api/v1/coach/chat` — verified 200, response shape matches models (zero-data fallback exercised: confidence 1, follow-up question, no drills)
- ✅ `GET /api/v1/coach/conversations` — verified 200, shape matches
- ✅ `GET /api/v1/coach/conversations/{id}/messages` — **FIXED & verified 200** (see below). **Requires `user_id` query param** (contract doc omits it; `main.py` enforces it → 422 without it). Frontend sends it.
- ⚠️ Confidence score: LLM overrides data-richness calc. Under observation.

### ✅ Backend bug found during Phase B integration — RESOLVED (Kanary)
`GET /api/v1/coach/conversations/{id}/messages` was returning **502** every call.
- **Root cause:** `backend/app/main.py:747` used `.order("created_at", asc=True)`. supabase-py 2.x `order()` has no `asc` kwarg → raised → caught as HTTPException 502. Only `.order()` in the file using `asc=`; siblings use `desc=` and returned 200.
- **Fix:** Kanary committed `ff423aa` → `.order("created_at")`. Merged (fast-forward) into local Kanary. Backend restarted on M1.
- **Verified:** endpoint now returns 200 with chronological (user→assistant) ordering; shape decodes into `ConversationMessagesResponse`. Full Phase B flow unblocked end-to-end.

### 🐞 Coach chat unreliable on follow-up messages — found 2026-07-14
**Symptom (Duk, simulator):** "Couldn't reach coach" on the 3rd message of a conversation.
**Root cause is backend/Supabase slowness**, which surfaces as **two distinct failure modes** (both on the continue-conversation path):

1. **Backend 500 (fast fail):** `HTTP 500 in ~18s`, body `{"detail":"Failed to fetch conversation: [Errno 60] Operation timed out"}`. The `.single()` conversation-verify query (`main.py:561`) — which runs **only when `conversation_id` is passed**, i.e. every message after the first — times out talking to Supabase. Explains why msg 1 (new convo, no verify) works and msg 3 fails.
2. **Client cancel (slow fail):** tunnel logs `Request failed error="Incoming request ended abruptly: context canceled" ... dest=.../coach/chat`. That's the **iOS app closing the connection** because the backend took **>60s** (the app's old default URLSession timeout) — a client-side timeout, not a backend error.

Both trace to the same thing: **Supabase calls from the M1 are intermittently very slow / timing out.**
- **Evidence of intermittency (same minute):** `GET /messages` 200 in 1.1s; `POST` new convo 200 but **27.8s**; `POST` continue → 500 @18s; `GET /conversations` failed @24.7s. Not a clean outage — flaky latency.
- **Likely factors (Kanary to investigate):** Supabase free-tier throttle/cold connections, supabase-py client connection reuse (no pooling/keepalive → cold TLS each call), or M1→Supabase network. The `.single()` verify is fragile — one transient timeout 500s the whole turn.
- **Suggested backend directions:** add retry/backoff on Supabase calls; reuse/pool the client connection; make the conversation-verify non-fatal (or skip re-verify when the user owns the convo); confirm the Supabase project isn't throttled/paused.
- **Owner:** Kanary (backend / Phase A). Not touched by Claude Code.

**Frontend hardening done (Claude Code, my lane):** bumped `CoachService.send()` request timeout 60s→**180s** — directly fixes failure mode #2 (the app no longer cancels at 60s, so a slow-but-successful reply completes). Does **not** fix #1 (the backend 500s) — that's Kanary's. Uncommitted; needs a rebuild to take effect (Duk deferred re-testing for now).
**Deferred (Duk, 2026-07-14):** friendlier long-wait copy ("coach is taking longer than usual…") — leave as-is for now.

## Progress — Phase B Conversational Coach Chat UI (BUILT)

- [x] `CoachChatModels.swift` — `ChatMessage` (UI) + decodable DTOs (`CoachChatResponse`, `ConversationSummary`, `ConversationMessagesResponse`); reuses `DrillRecommendation`
- [x] `CoachService.swift` — rewritten for chat: `send()` (→ `/coach/chat`), `fetchConversations()`, `fetchMessages()` (sends required `user_id`). Old `/coach/ask` removed.
- [x] `CoachChatView.swift` — threaded bubble chat (user right / coach left), confidence bar, key-insights block, expandable drill cards in coach bubbles, typing indicator, scroll-to-bottom, inline error bubble + Retry, multi-turn threading via `conversation_id`, zero-data suggested prompts. `CoachChatSheet` wrapper for modal presentation.
- [x] `ConversationListView.swift` — Coach tab root: past conversations (loading/empty/error/loaded), pull-to-refresh, New Chat, tap → open thread.
- [x] Entry points: Coach tab (list), Round detail "Ask Coach about this round" (sheet, `round_id`), post-submit summary "Chat with Coach about this round" (sheet, `round_id` now threaded through `ScorecardViewModel`).
- [x] Old single-shot `CoachView`/`CoachViewModel` removed; shared tokens (`Color` ext, `BouncingDots`, `FlowLayout`) preserved in `CoachView.swift`.
- [x] Accessibility: VoiceOver labels on user/coach/error bubbles, confidence, drill cards, conversation cards.
- [x] Build green (xcodebuild, generic iOS Simulator).
- [ ] On-device taste test (Duk).
- [ ] Backend messages-endpoint 502 fix (Kanary) — needed for the "view saved conversation" acceptance criterion.

### Superseded — old backend status block
- ⚠️ iOS connection issue (July 9): root cause was a paused Supabase project + rotating tunnel URL, not app code. New tunnel URL wired in.

## Progress — Round History List (COMPLETE)

- [x] `RoundHistoryView` — scrollable list of round cards
- [x] `RoundHistoryService` — fetch from `GET /api/v1/rounds`
- [x] `RoundHistoryItem` models — decode response (tolerant `round_stats` array/object; `id` is Int)
- [x] Round card UI — course name, date, score, vs par, GIR, SG chips
- [x] Empty state — "No rounds yet" with "+ New Round" button
- [x] Pull-to-refresh
- [x] Loading skeleton
- [x] Error state with retry
- [x] Tap card → placeholder detail view (`RoundDetailView`)
- [x] Accessibility (per-card VoiceOver label, Dynamic Type via semantic fonts)
- [x] Dark mode support (semantic colors throughout)
- [x] Build green (xcodebuild, generic iOS Simulator)
- [x] Merged to Kanary (PR #9, 2026-06-27)
- [ ] On-device taste test (Duk) — scheduled for Sunday round

**Reality vs spec (verified against the live backend):**
- `GET /api/v1/rounds` returns `id` as an **Int** (BIGSERIAL), and **`round_stats` as an array** (PostgREST embed), not the object the spec assumed — decoder tolerates array/object/null.
- **SG chips:** only **G (putting)** and **A (approach)** have real backend data; **P (short game)** and **F (driving)** show "—" placeholders (backend doesn't expose those SG categories yet) rather than duplicating/fabricating values.
- **Surfaced as a 3rd tab** ("History") — answers spec open-question #1 (tab vs standalone) with *tab*; "+ New Round" switches to the New Round tab. Easy to change if Duk prefers standalone.
- **Swipe-to-delete deferred** — backend `DELETE /rounds/{id}` doesn't exist yet; omitted rather than shipping a dead/fake button.

## Previous — Scorecard Entry View (COMPLETE)

- [x] Handicap setup screen + `HandicapStore` (UserDefaults) + Settings access (Coach menu)
- [x] Round setup screen (mode select + handicap pre-fill) from tee picker
- [x] Models: `RoundMode`, `DraftRound`, `HoleEntry`, encodable `RoundPayload`, `RoundStats`
- [x] `ScorecardEntryView` — Front/Back 9 tabs, per-hole steppers, nav, live totals
- [x] Per-hole form (score/putts/fairway/GIR) + edge cases (par 3, ace, eagle, putts cap)
- [x] Draft auto-save / resume (`DraftRoundStore`)
- [x] Review screen + submit to `POST /api/v1/rounds`
- [x] `RoundSummaryView` — display `round_stats`
- [x] Build green (xcodebuild, generic iOS Simulator)
- [x] Duk taste refinements: focused single-hole layout, score at bottom, type-in handicap (no stepper), centered + evenly-spaced middle
- [ ] On-device taste test (Duk) — sun readability, one-handed steppers, full flow

**Notes for Duk/Kanary:** 
- Round History List spec is at `docs/ROUND_HISTORY_SPEC.md` — read before building
- Scorecard: swipe-between-holes deferred (tap-to-jump + Front/Back tabs + Prev/Next cover navigation); per-hole yardage comes from `/courses/{id}` (first tee set, not the selected tee); post-submit stays on summary screen until Round History List ships
- Duk should test scorecard on device while Claude Code builds Round History List in parallel

## Blockers

- None. All known issues resolved (PR #10, PR #11, migration 015 applied).

## New Issue for Claude Code — iOS App Cannot Connect to Backend

**Reported by:** Duk  
**Date:** 2026-07-09  
**Status:** Open — needs Claude Code investigation  
**Branch:** Kanary

### Problem
iOS app shows error: **"A server with the specified hostname could not be found"** on login.

### Context
- Backend is running on M1 server (always-on)
- Cloudflare Tunnel is running on M1 in tmux session `dimple-tunnel`
- Tunnel URL: `https://links-authority-weddings-times.trycloudflare.com`
- URL responds with `{"status": "ok"}` from phone browser (both WiFi and cellular)
- iOS app baseURL updated to the Cloudflare URL in all 4 service files

### What Works
- ✅ Backend health check via browser on phone
- ✅ Backend reachable from M1 localhost
- ✅ Tunnel is active and connected

### What Doesn't Work
- ❌ iOS app cannot connect — hostname not found error

### Possible Causes (for Claude Code to investigate)
1. **App Transport Security (ATS)** — iOS may block non-standard domains or require specific entitlements
2. **URL format in Swift** — trailing slash, http vs https, or string interpolation issue
3. **DNS resolution on device** — iOS DNS cache or network configuration
4. **Build/clean issue** — Old URL cached in build, needs clean build folder
5. **Info.plist configuration** — Missing `NSAppTransportSecurity` settings for arbitrary loads

### Suggested Fix Path
1. Check `Info.plist` for `NSAppTransportSecurity` → `NSAllowsArbitraryLoads` = true (for development)
2. Verify all `baseURL` strings in Swift services are exactly `https://links-authority-weddings-times.trycloudflare.com` with no trailing slashes
3. Clean build folder in Xcode (Shift+Cmd+K), rebuild
4. Test with a hardcoded URL in a simple `URLSession` request to isolate
5. Check Console app on Mac for iOS device logs during connection attempt

### Questions for Claude Code
- Is there any URLSession configuration that might block this domain?
- Should we add exception domains to Info.plist for `.trycloudflare.com`?
- Is the baseURL being constructed correctly (no accidental `localhost` fallback)?

**Priority:** Blocks Sunday test. Fix before end-to-end validation.

## Questions for Duk

- None

## Completed (Last 7 Days)

- 2026-06-25: **Claude Code — Scorecard Entry View merged to Kanary (PR #8).** Full per-hole entry flow + Duk's taste refinements (focused single-hole screen, score at bottom, type-in handicap, centered/even middle). `xcodebuild` green; on-device taste test pending.
- 2026-06-24: **Claude Code — Supabase key rotation complete (Path B).** Installed `supabase==2.30.0` into the local `.venv` (the upgrade Kanary pinned in requirements). Verified the backend connects with the new `sb_secret_…` key — `GET /api/v1/rounds` returns 200 (was 500 under 2.10.0). Verified the iOS side: `supabase-swift` has no JWT-format gate, and Supabase accepts the new `sb_publishable_…` key (401 permission-denied = valid key, RLS-locked). Duk disabled the legacy keys → the leaked anon key is revoked and the GitGuardian incident is resolved. Security thread fully closed.
- 2026-06-23: **Kanary (backend/orchestrator) — supabase-py upgrade** — Bumped `supabase==2.10.0` → `supabase==2.30.0` in `backend/requirements.txt`. Fixes 500 errors caused by v2.10.0's hard JWT regex rejecting new `sb_secret_…` anon keys. Committed and pushed to `main`.
- 2026-06-23: **Kanary (backend/orchestrator) — main branch catch-up** — `main` is now the single source of truth. All Kanary branch work merged. Docs updated (TASK_BOARD, WAKE_UP, CHROLLO_ORCHESTRATION_PLAN). AGENT_STATUS.md created for Claude Code heartbeat.
- 2026-06-23: Security fix — moved the Supabase anon key out of source into a git-ignored `Secrets.xcconfig` (build-time Info.plist injection, runtime read). Tripped GitGuardian on the public repo. Open as PR into Kanary (`security/externalize-supabase-key`). Anon key being rotated in Supabase; RLS verified (anon role has no table access).
- 2026-06-22: Course Search UI complete — search, select, tee picker working

---

## Session Decisions Log (2026-06-24 → 06-25)

**Security / keys**
- Supabase **anon key removed from source** → git-ignored `Secrets.xcconfig`, injected into the generated `Info.plist` via `$(SUPABASE_ANON_KEY)`, read at runtime. Project URL stays in source (not secret; `//` breaks xcconfig parsing).
- **Migrated to Supabase's new API keys**: `sb_publishable_…` (iOS) + `sb_secret_…` (backend). Required upgrading `supabase-py` 2.10 → 2.30 (old version's JWT regex rejected the non-JWT keys). Legacy keys **disabled** → leaked anon key revoked; **GitGuardian incident resolved**. RLS verified (anon role has no table access — the leaked key was inert even before rotation).

**Workflow**
- **Kanary = working branch, `main` = release; Duk merges.** Never push to `main` without explicit, per-instance permission. Features land via PRs into Kanary (PR #7 = security, PR #8 = scorecard).

**Scorecard feature (Duk taste calls)**
- **Hole screen = focused single-hole layout** (replaced the spec's scrolling scorecard list): top = hole + running totals, middle = fairway/GIR/putts (centered, evenly spaced), bottom = score +/- and a large pinned Next/Submit (thumb zone). The full all-holes scorecard lives behind the top-right "Scorecard" button (review screen).
- **Handicap = type-in only** (no 0.1 stepper); stored locally in `UserDefaults` (first-launch setup + Coach-menu settings); per-round override does not change the stored default.
- Round modes: Full 18 / Front 9 / Back 9 / Play Until Dark (flexible early submit). **Quick round mode cancelled** (Duk taste).
- Edge cases: hole-in-one → putts 0 / GIR yes / locked; eagle-or-better → auto-GIR; putts capped at score−1. Single active draft in `UserDefaults` with a resume prompt.

**Deferred / known limits**
- Swipe-between-holes deferred (tap-to-jump + Prev/Next + "Scorecard" jump view cover navigation).
- Per-hole yardage comes from `/courses/{id}` (backend derives it from the first tee set, not the selected tee).
- Post-submit stays on the summary screen until **Round History List** exists (next task).

---

## How Claude Code Uses This File

1. **Update as you go.** After every session or meaningful milestone, edit this file.
2. **Be specific.** "Building view" is bad. "Created ScorecardEntryView.swift with hole list" is good.
3. **Flag blockers immediately.** If you're stuck, write it here. Kanary will surface it to Duk.
4. **Ask questions here.** If you need a taste decision from Duk, put it in "Questions for Duk".
5. **Commit with the code.** This file lives in the repo. Update it, commit it, push it.

## How Kanary Uses This File

1. **Read during wake-up.** Check this file every session to see Claude Code's current state.
2. **Surface blockers.** If there's a blocker, ping Duk with context.
3. **Route questions.** If Claude Code has a question for Duk, relay it or answer if within my authority.
4. **Update TASK_BOARD.** Cross-reference this file when updating the task board.

## Format

```markdown
## Claude Code — Current Task
- **Task:** [Task name from TASK_BOARD.md]
- **Started:** [YYYY-MM-DD]
- **Status:** Not started / In Progress / Blocked / Complete
- **Branch:** [branch name]

## Progress
- [x] Done item
- [ ] Todo item

## Blockers
- [Description and context]

## Questions for Duk
- [Question that needs taste/priority decision]

## Completed (Last 7 Days)
- [YYYY-MM-DD]: [What was completed]
```

---

*Last updated: 2026-07-08 (Kanary — docs refresh, all tasks complete)*
*Next expected update: When Duk assigns next task or provides taste feedback*
