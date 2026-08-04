# Dimple v1.0.0 Roadmap

> **Target:** Three features, then ship.
> **Branch:** Kanary (working branch)
> **Release:** Merge Kanary → main, tag `v1.0.0`

---

## The Three Features

### 1. Manual Course Entry
**Status:** Spec drafted, Duk approved  
**Branch:** `feature/manual-course-entry`  
**What:** When GolfCourseAPI.com doesn't have a course, user enters name/city/state/holes/par manually. Scorecard-only mode (no shot-by-shot), but full coach access via round stats.

**Backend:**
- `POST /api/v1/courses/manual` — create manual course
- Store in `manual_courses` table (or flag in existing courses table)
- Return course ID for round submission

**Frontend:**
- "Enter manually" button on CourseSearchView
- Form: name, city, state, hole count, par per hole
- Tee info optional (rating/slope if known)
- Flow: manual entry → RoundSetup → ScorecardEntry

**Spec:** `docs/MANUAL_COURSE_ENTRY_SPEC.md` (already written)

---

### 2. Coach Loading Indicator
**Status:** Spec drafted, ready for implementation  
**What:** Visual feedback while coach is "thinking" — no more staring at static screen for 15-30 seconds.

**Acceptance:**
- [ ] Optimistic message insertion (user message appears instantly)
- [ ] Animated "typing" indicator while waiting
- [ ] Retry UI on failure (not "Network connection was lost")
- [ ] State preserved on app background/foreground

**Spec:** `docs/FRONTEND_LOADING_INDICATOR_SPEC.md` (already written)

---

### 3. Course Selection Flow Bug Fix
**Status:** Spec below, ready for implementation  
**Bug:** After selecting tees, user gets kicked back to course search. Must re-select course, then it jumps to hole 1.

**Root cause hypothesis:** Navigation path state loss — `path` gets reset when `CourseTeePickerView` dismisses or when `RoundSetupView` triggers a state change that recreates the navigation stack.

**Spec:** See below.

---

## Release Checklist

- [ ] All three features merged to Kanary
- [ ] Duk tests on device
- [ ] Update README.md for v1.0.0
- [ ] Merge Kanary → main
- [ ] Tag `v1.0.0`
- [ ] Celebrate

---

*Roadmap by Kanary. Execution by Claude Code. Taste by Duk.*
