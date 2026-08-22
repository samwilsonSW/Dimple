# Manual Course Entry Spec

> **Status:** Draft — pending Duk review  
> **Owner:** Kanary (OpenClaw)  
> **Assignee:** Claude Code (frontend)  
> **Related:** `API_CONTRACT.md` v0.7.0+

---

## Problem

GolfCourseAPI.com has gaps. Small courses, new courses, renamed courses, and secondary layouts (e.g., "Creek Course" at Meadowbrook GC) don't appear in search results. Currently this blocks the entire round entry flow — no course found = no scorecard = no coach insight.

**User impact:** Duk played Creek Course at Meadowbrook, shot +18/+10 with 3 pars, and couldn't enter the round. Coach never saw it.

---

## Goal

Allow users to enter rounds for courses not in GolfCourseAPI.com, with minimal friction and without compromising data quality for coach analysis.

---

## Decision: Lightweight Manual Entry

**Not a full course editor.** A fallback path inside the existing scorecard flow that collects just enough data for meaningful coach feedback.

### What Manual Entry Provides
- Course name, city, state (free text)
- Hole count (9 or 18)
- Per-hole par values (auto-filled to 72 total, editable)
- Full scorecard entry (score, putts, fairway, GIR per hole)
- Round submission → round stats → coach access

### What Manual Entry Does NOT Provide
- Per-hole yardage (no SG baselines that require distance)
- Tee box selection (rating/slope unknown)
- Shot-by-shot mode (no yardage = no SG calculation)
- Course caching / reuse across rounds

### Trade-off Summary

| Feature | API Course | Manual Course |
|---------|-----------|---------------|
| Course name | ✅ From API | ✅ User-entered |
| City/State | ✅ From API | ✅ User-entered |
| Hole count | ✅ From API | ✅ User-selected (9/18) |
| Per-hole par | ✅ From API | ✅ User-editable (default 72) |
| Per-hole yardage | ✅ From API | ❌ Not collected |
| Tee selection | ✅ From API | ❌ Not applicable |
| Rating/Slope | ✅ From API | ❌ Not applicable |
| Scorecard entry | ✅ Full | ✅ Full |
| Shot-by-shot | ✅ Full | ❌ Disabled |
| SG calculation | ✅ Full | ⚠️ Partial (putting + approach only) |
| Coach access | ✅ Full | ✅ Full (scorecard data sufficient) |

**Key insight:** Coach only needs round stats (score, putts, fairways, GIR) to give meaningful feedback. SG baselines use handicap-adjusted averages, not course-specific data. The absence of yardage only disables shot-by-shot mode, not coach analysis.

---

## User Flow

```
Course Search Screen
  └── User types "Creek Course Meadowbrook"
      └── No results found
          └── Show "Can't find your course?" button
              └── Tap → Manual Course Entry Screen
                  └── Enter course name, city, state
                  └── Select 9 or 18 holes
                  └── Review/Edit par values (default: all par 4s = 72 total)
                  └── Tap "Continue to Scorecard"
                      └── Scorecard Entry (existing flow)
                          └── Submit → Round History → Coach
```

---

## UI Specification

### Screen 1: Course Search (Modification)

**Change:** When search returns 0 results, show a fallback action instead of empty state.

```swift
// In CourseSearchView
if searchResults.isEmpty && searchQuery.count >= 2 {
    VStack(spacing: 16) {
        Text("No courses found")
            .foregroundColor(.secondary)
        Button("Enter course manually") {
            showManualEntry = true
        }
        .buttonStyle(.borderedProminent)
    }
}
```

### Screen 2: Manual Course Entry (New)

**Layout:** Form-style, single screen, scrollable.

**Fields:**

| Field | Type | Validation | Default |
|-------|------|------------|---------|
| Course Name | Text | Required, max 100 chars | Empty |
| City | Text | Required, max 50 chars | Empty |
| State | Text | Required, 2 chars (TX, CA, etc.) | Empty |
| Holes | Segmented | 9 or 18 | 18 |
| Par Values | Editable list | Per-hole par 3-5, total 54-90 | All par 4 (72 total) |

**Par Editor:**
- Show holes 1-18 (or 1-9) in a grid or list
- Each hole: number label + stepper (3, 4, 5)
- Running total at bottom: "Total Par: 72"
- "Reset to all par 4" button

**Actions:**
- Primary: "Continue to Scorecard" (disabled until name/city/state valid)
- Secondary: "Cancel" (dismisses back to search)

**Accessibility:**
- VoiceOver labels on all fields
- Dynamic Type support
- Focus management (name → city → state → holes → par editor)

### Screen 3: Scorecard Entry (Existing, Modified)

**Change:** When entering from manual course flow:
- Skip tee selection step
- Skip yardage display (holes show par only, no yardage)
- Disable "Switch to Shot-by-Shot" button (or hide it)
- Course info header shows user-entered name + city/state

---

## Data Model

### New Type: `ManualCourse`

```swift
struct ManualCourse: Codable {
    let name: String
    let city: String
    let state: String
    let holes: Int  // 9 or 18
    let parValues: [Int]  // Array of par 3-5, count = holes
    
    var totalPar: Int { parValues.reduce(0, +) }
}
```

### Modified: `RoundPayload`

Add optional `manual_course` field. When present, `course_id` and `tee_box` are omitted.

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "round_date": "2026-08-02",
  "course": {
    "name": "Creek Course",
    "city": "Lubbock",
    "state": "TX"
  },
  "manual_course": {
    "holes": 18,
    "par_values": [4, 4, 3, 4, 5, 4, 4, 3, 4, 4, 4, 3, 4, 5, 4, 4, 3, 4]
  },
  "handicap_index": 13.2,
  "hole_data": [...],
  "total_score": 94,
  "total_putts": 36
}
```

**Validation rules:**
- Either `course_id` (API course) OR `manual_course` (user-entered) must be provided, not both
- `manual_course.holes` must be 9 or 18
- `manual_course.par_values` count must equal `holes`
- Each par value must be 3, 4, or 5
- `total_par` calculated server-side for validation

---

## API Changes

### Modified Endpoint: `POST /api/v1/rounds`

**Request body** now accepts either:
- `course_id` + `tee_box` (existing API course flow)
- `manual_course` (new manual entry flow)

**Backend behavior when `manual_course` present:**
1. Skip course cache lookup
2. Skip tee box validation
3. Store `course` JSONB as user-entered name/city/state
4. Store `manual_course` JSONB for reference
5. Calculate round stats using par values for strokes-over-under
6. **Disable shot embedding** — `shots` array rejected with 422 if `manual_course` present (no yardage = no SG)
7. Return same `RoundIngestResponse` shape

**New error codes:**
- `422` — `manual_course` and `course_id` both provided
- `422` — Invalid par values (not 3-5, wrong count)
- `422` — `shots` provided with `manual_course` (not allowed)

### Database Schema Change

**Migration 019:** Add `manual_course` column to `rounds` table

```sql
-- Migration 019: Support manually entered courses
ALTER TABLE rounds ADD COLUMN manual_course JSONB NULL;

-- Add index for filtering manual vs API courses (analytics)
CREATE INDEX idx_rounds_manual_course ON rounds((manual_course IS NOT NULL));
```

**`rounds` table updated:**
- `course_id` (text, nullable) — now truly optional
- `manual_course` (jsonb, nullable) — new
- Constraint: CHECK (course_id IS NOT NULL OR manual_course IS NOT NULL)

---

## Backend Implementation Notes

### Round Stats Calculation

When `manual_course` is present:
- `strokes_over_under` = `total_score` - `manual_course.par_values.sum()`
- `sg_putting` and `sg_approach` still calculated from `hole_data` (putts + score vs par)
- `sg_driving` and `sg_short_game` omitted (require shot-level distance data)
- `gir_percentage`, `fairway_percentage` unchanged

### Coach Behavior

No changes needed. Coach already handles missing shot data gracefully (data-source-aware prompts). A manual course round appears as "scorecard-only" data with putting + approach SG.

### Analytics / Future Use

Manual course entries flagged in database. Future feature: "Popular missing courses" report → submit to GolfCourseAPI.com or build our own course DB.

---

## Frontend Implementation (Claude Code)

### New Files

```
Dimple/
├── Views/
│   └── CourseSearch/
│       └── ManualCourseEntryView.swift      # Form for manual entry
├── ViewModels/
│   └── ManualCourseEntryViewModel.swift     # Validation, par calculation
├── Models/
│   └── ManualCourse.swift                   # Data model
```

### Modified Files

```
Dimple/
├── Views/
│   └── CourseSearch/
│       └── CourseSearchView.swift           # Add "Enter manually" fallback
│   └── Scorecard/
│       └── ScorecardEntryView.swift         # Handle manual course (no yardage, no shot mode)
├── Services/
│   └── RoundService.swift                   # Send manual_course in payload
├── Models/
│   └── RoundPayload.swift                   # Add manual_course field
```

### Tasks for Claude Code

- [ ] Create `ManualCourse.swift` model
- [ ] Create `ManualCourseEntryView.swift` — form with par editor
- [ ] Create `ManualCourseEntryViewModel.swift` — validation logic
- [ ] Modify `CourseSearchView.swift` — show manual entry button on empty results
- [ ] Modify `ScorecardEntryView.swift` — conditional layout for manual courses
- [ ] Modify `RoundPayload.swift` — add `manual_course` field
- [ ] Modify `RoundService.swift` — include manual_course in submission
- [ ] Update `API_CONTRACT.md` — document manual_course field
- [ ] Build green on simulator
- [ ] Test: empty search → manual entry → scorecard → submit → coach

---

## Tasks for Kanary

- [ ] Write migration 019 (manual_course column + constraint)
- [ ] Modify `POST /api/v1/rounds` — accept manual_course, reject shots
- [ ] Update round stats calculation for manual courses
- [ ] Update API contract (this spec → API_CONTRACT.md)
- [ ] Update WAKE_UP.md and TASK_BOARD.md
- [ ] Deploy migration
- [ ] Verify end-to-end with test payload

---

## Open Questions

1. **Should we allow manual 9-hole rounds?** Yes — par values for 9 holes, submit as 9-hole round. Round stats calculate accordingly.
2. **Should manual courses appear in search later?** No — not in scope. Manual entry is a fallback, not a course database.
3. **Can users edit a manual course after creation?** No — edit the round's hole_data, not the course definition. Course is immutable after round creation.
4. **What if GolfCourseAPI.com later adds the course?** Existing manual rounds stay manual. Future rounds can use the API course. No migration needed.

---

## Success Criteria

- [ ] User can enter a round for any course, even if not in GolfCourseAPI.com
- [ ] Coach provides meaningful feedback on manual course rounds
- [ ] Shot-by-shot mode disabled for manual courses (no yardage)
- [ ] Round history displays manual courses correctly (name + city/state)
- [ ] No regression in API course flow

---

## Changelog

| Date | Change |
|------|--------|
| 2026-08-03 | Initial spec draft |

---

*This spec is the plan. Review, iterate, then build.*
