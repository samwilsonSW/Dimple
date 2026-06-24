# Scorecard Entry View — Spec

> **Status:** Ready for Claude Code  
> **Owner:** Kanary (spec) → Claude Code (build) → Duk (taste test)  
> **Updated:** 2026-06-24

---

## Overview

Per-hole scorecard entry. Not post-round — **post-hole**, while waiting on the next tee box. Fast, sun-readable, hard to mis-tap.

---

## Core Mechanics

### Input: Stepper (NOT number pad)

- Large stepper buttons (+/-) for score entry
- **Default value = hole's par** (from course/tee data)
- User taps + or - to adjust from par
- Minimum value: 1 (prevent 0 or negative scores)
- No maximum enforced by UI (let user enter whatever, backend validates)

**Why stepper over number pad:**
- Sun-readable (big buttons vs small keyboard keys)
- Hard to misclick (large tap targets)
- Natural feel for golf ("1 over par, 2 under par" mental model)
- Works with gloves, sweaty fingers, beer hand

### Hole Navigation

**Auto-advance with manual override:**
1. User completes hole N (enters all fields, taps "Next Hole")
2. View advances to hole N+1 automatically
3. Stepper resets to par for hole N+1
4. **BUT:** User can always:
   - Swipe left/right between holes
   - Tap "Previous" / "Next" buttons
   - Tap any hole number in the tab bar to jump directly
   - Tap "See Scorecard" (top right) to view all holes and jump to any

**"Next Hole" button:**
- Primary action button at bottom of each hole's entry form
- Tapping it saves current hole to draft and advances
- Disabled until `score` is entered (putts/fairway/GIR are optional)

---

## Layout: Scorecard Style

### Front 9 / Back 9 Tabs

- Two tabs at top: **"Front 9"** | **"Back 9"**
- Each tab shows holes 1-9 or 10-18 in a **vertical scorecard list**
- Each row = one hole
- Active hole is highlighted/expanded
- Completed holes show summary (score, putts) in collapsed row

**Scorecard row layout (expanded/active hole):**
```
┌─────────────────────────────────────┐
│  Hole 7    Par 4    412 yds         │  ← header row
│                                     │
│  Score:    [−]  5  [+]              │  ← large stepper
│                                     │
│  Putts:    [−]  2  [+]              │  ← smaller stepper
│                                     │
│  Fairway:  [ Missed ] [ Hit ]       │  ← toggle (hidden on par 3)
│                                     │
│  GIR:      [ No ] [ Yes ]           │  ← toggle
│                                     │
│  [  ← Previous ]  [ Next Hole →  ]  │  ← nav buttons
└─────────────────────────────────────┘
```

**Collapsed row (completed hole):**
```
┌─────────────────────────────────────┐
│  Hole 3   Par 4   Score: 5   Putts: 2  Fairway: ✓  GIR: ✗  │
└─────────────────────────────────────┘
```
- Tap collapsed row to expand and edit
- Visual indicator: checkmark or "complete" badge

---

## Header Bar (Fixed at Top)

```
┌─────────────────────────────────────┐
│  ← Back    Current Hole: 7          │
│            Total Over/Under: +3     │
│            Total Strokes: 38        │
│                          [Scorecard]│  ← top right button
└─────────────────────────────────────┘
```

**Elements:**
- **Top left:** Back button (←) — returns to previous screen (course search/tee selection)
- **Center stack:**
  - "Current Hole: N" (largest/boldest)
  - "Total Over/Under: +3" (green for under, red for over, black for even)
  - "Total Strokes: 38"
- **Top right:** "Scorecard" button — opens review view (all holes, tap to jump)

**Updates live** as user enters scores.

---

## Per-Hole Fields

All 4 fields shown for every hole. No hiding fields based on par (except fairway on par 3).

| Field | Input | Default | Rules |
|-------|-------|---------|-------|
| **Score** | Large stepper | Hole's par | Required. Min 1. |
| **Putts** | Small stepper | 2 | Optional. Min 0. Max = score - 1 (can't putt more than strokes). |
| **Fairway** | Toggle (Hit / Missed) | null | Hidden on par 3. null = not recorded. |
| **GIR** | Toggle (Yes / No) | null | null = not recorded. |

**Field order:** Score → Putts → Fairway → GIR → Next Hole button

**Validation:**
- Score required before "Next Hole" enabled
- Putts cannot exceed score - 1 (if score = 1, putts = 0, locked)
- If score = 1 (hole-in-one), auto-set putts = 0, fairway = null (par 3) or true (par 4/5), GIR = true

---

## 9-Hole / 18-Hole / Partial Round Modes

**Mode selection at start** (after tee selection):
- "Full 18 Holes" (default)
- "Front 9 Only"
- "Back 9 Only"
- "Play until dark" (flexible — no preset limit, user submits whenever)

**Behavior:**
- Full 18: All 18 holes shown. Submit enabled after hole 18.
- Front 9: Only holes 1-9 shown. Submit enabled after hole 9.
- Back 9: Only holes 10-18 shown. Submit enabled after hole 18.
- Flexible: All 18 holes shown, but "Submit Round" button always available. User can submit at any point (e.g., after 13 holes because sun went down).

**Partial round handling:**
- Unplayed holes: score = null, not included in totals
- Backend accepts partial `hole_data` array (only include played holes)
- `total_score` and `total_putts` calculated from provided holes only

---

## Draft Auto-Save

**Local persistence (UserDefaults / SwiftData):**
- After each "Next Hole" tap, save current progress locally
- Key: `draft_round_{course_id}_{date}`
- Save: current hole index + all entered hole data
- **If app crashes / phone dies:** On relaunch, detect draft, offer "Resume Round?" with course name and last hole played
- **Discard draft:** Option in menu to clear and start over

**Draft schema (local):**
```swift
struct DraftRound: Codable {
    let courseId: String
    let courseName: String
    let teeBox: TeeBox
    let roundDate: String  // YYYY-MM-DD
    let mode: RoundMode  // full18, front9, back9, flexible
    let currentHoleIndex: Int  // 0-based
    let holes: [HoleEntry]  // only completed holes
    let lastSaved: Date
}

struct HoleEntry: Codable {
    let holeNumber: Int
    let par: Int
    let score: Int
    let putts: Int?
    let fairway: Bool?  // null on par 3 or not recorded
    let gir: Bool?      // null if not recorded
}
```

---

## Review Scorecard View

**Triggered by:**
- "Scorecard" button in header (any time)
- "Review & Submit" button after final hole

**Layout:**
```
┌─────────────────────────────────────┐
│  ← Back              Review Round   │
│                                     │
│  The Rawls Course At Texas Tech     │
│  Black Tees | Jun 24, 2026          │
│                                     │
│  Front 9                            │
│  ┌────┬────┬────┬────┬────┐        │
│  │Hole│ Par│Yards│Score│Putts│FW│GIR│
│  ├────┼────┼─────┼─────┼─────┼──┼───┤
│  │ 1  │ 4  │ 402 │  5  │  2  │✓ │ ✗ │
│  │ 2  │ 5  │ 521 │  6  │  2  │✓ │ ✓ │
│  │ ...│    │     │     │     │  │   │
│  └────┴────┴─────┴─────┴─────┴──┴───┘
│                                     │
│  Back 9                             │
│  [same table format]                │
│                                     │
│  Total: 85 (+13)  Putts: 32         │
│  FW: 7/14 (50%)  GIR: 5/18 (28%)    │
│                                     │
│  [Edit Hole 7]  [Submit Round]      │
└─────────────────────────────────────┘
```

**Features:**
- Table view of all holes (front 9 and back 9 sections)
- Each row: Hole | Par | Yardage | Score | Putts | Fairway | GIR
- Tap any row → jump back to that hole's entry view
- Summary stats at bottom (total score, over/under, putts, fairways, GIR)
- "Submit Round" button (primary, bottom)
- Confirmation alert on submit: "Submit round for [Course Name]? This cannot be undone."

---

## Submit Flow

1. User taps "Submit Round" from review view (or "Finish Round" after hole 18)
2. Show loading spinner: "Saving round..."
3. Build `RoundPayload`:
   ```json
   {
     "user_id": "...",
     "round_date": "2026-06-24",
     "course": { "name": "...", "city": "...", "state": "..." },
     "handicap_index": 13.2,
     "course_id": "21027",
     "tee_box": { "tee_name": "Black", "rating": 74.9, "slope": 134 },
     "hole_data": [
       { "hole_number": 1, "par": 4, "yardage": 402, "score": 5, "putts": 2, "fairway": true, "gir": false },
       ...
     ],
     "total_score": 85,
     "total_putts": 32
   }
   ```
4. POST to `/api/v1/rounds`
5. On success:
   - Clear local draft
   - Show success toast: "Round saved!"
   - Display `round_stats` summary (SG Putting, SG Approach, GIR%, Fairway%)
   - Navigate to Round History List (or stay on summary view)
6. On failure:
   - Show error: "Failed to save round. Retry?"
   - Keep draft, allow retry
   - Option: "Save locally and try again later"

---

## Edge Cases

| Case | Behavior |
|------|----------|
| **Par 3** | Fairway toggle hidden. Auto-set `fairway: null` in payload. |
| **Hole-in-one (score = 1)** | Auto-set putts = 0, GIR = true. Fairway = null (par 3) or true (par 4/5). Lock putts stepper. |
| **Eagle or better (score ≤ par - 2)** | Auto-set GIR = true (can't eagle without GIR). |
| **Score = par + 1 (bogey)** | No auto-changes. User enters putts/fairway/GIR manually. |
| **Putts > score - 1** | UI prevents (stepper max = score - 1). If score = 1, putts locked to 0. |
| **No fairway data** | Toggle stays in middle/null state. Payload sends `fairway: null`. |
| **No GIR data** | Toggle stays in middle/null state. Payload sends `gir: null`. |
| **Partial round (13 holes)** | Only send played holes in `hole_data`. `total_score` = sum of played holes. Backend calculates stats from provided holes only. |
| **All holes par** | Stepper starts at par every time. User mostly just taps "Next Hole" if they shot par. |
| **Network failure on submit** | Keep draft locally. Show "Retry" button. Allow "Save locally" option. |
| **App crash mid-round** | On relaunch, detect draft, show "Resume round at The Rawls Course (Hole 8)?" dialog. |
| **User goes back to course search** | Save draft automatically. Show "You have a round in progress" warning if they try to start new round. |

---

## API Integration

**Load course data:**
```
GET /api/v1/courses/{course_id}
```
- Use `holes` array to populate par and yardage for each hole
- Use `tees` array to get selected tee's `rating` and `slope`

**Submit round:**
```
POST /api/v1/rounds
```
- See API_CONTRACT.md for full payload shape
- Must include `hole_data` array with all played holes
- Must include `total_score` and `total_putts` (sum of played holes)

**Response:**
- `round_stats` object with SG Putting, SG Approach, GIR%, Fairway%, etc.
- Display these on post-submit summary screen

---

## Files to Create/Modify

**New files:**
- `ScorecardEntryView.swift` — main view
- `HoleEntryView.swift` — single hole entry (stepper + toggles)
- `ScorecardReviewView.swift` — review screen
- `DraftRoundStore.swift` — local persistence
- `RoundSummaryView.swift` — post-submit stats display

**Modify:**
- `CourseSearchView.swift` — pass `course_id` + selected tee to scorecard entry
- `Models.swift` — add `DraftRound`, `HoleEntry`, `RoundMode` structs

---

## Design Notes

- **Sun readability:** High contrast, large fonts, bold stepper buttons
- **One-handed use:** Primary actions (Next Hole, +, -) reachable with thumb
- **Glove-friendly:** Minimum tap target 44pt for all buttons
- **No keyboard:** Stepper only, no text input
- **Color coding:**
  - Under par: green
  - Over par: red
  - Even par: black
  - Par 3 fairway row: hidden/grayed out
- **Haptic feedback:** Light tap on stepper, medium on "Next Hole", success on submit

---

## Test Checklist

- [ ] Start round, enter 18 holes, submit, verify `round_stats` response
- [ ] Test 9-hole mode (front 9 only)
- [ ] Test partial round (enter 13 holes, submit)
- [ ] Test draft save: kill app mid-round, relaunch, resume
- [ ] Test par 3: fairway toggle hidden, payload has `fairway: null`
- [ ] Test hole-in-one: putts auto-0, GIR auto-yes
- [ ] Test review screen: tap hole to edit, verify changes save
- [ ] Test back button: saves draft, returns to course search
- [ ] Test offline: submit fails, retry works
- [ ] Test large stepper in sunlight (Duk on-device)

---

*Spec locked: 2026-06-24. Questions? Ask Kanary.*
