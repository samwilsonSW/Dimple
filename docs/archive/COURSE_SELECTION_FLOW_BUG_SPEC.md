# Course Selection Flow Bug Fix Spec

> **Owner:** Claude Code  
> **Status:** Ready for implementation  
> **Branch:** Kanary  
> **Priority:** Blocker for v1.0.0

---

## The Bug

**Current broken flow:**
1. User searches for course → taps result
2. Tee picker loads → user selects tee
3. **Bug:** User gets kicked back to course search screen
4. User taps same course again
5. Jumps directly to hole 1 (skips tee selection + round setup)

**Expected flow:**
1. Search → tap course
2. Tee picker → select tee
3. Round setup (handicap, date, etc.)
4. Scorecard entry (hole 1)

---

## Root Cause Analysis

Looking at `NewRoundView.swift`:

```swift
NavigationStack(path: $path) {
    CourseSearchView()
        .navigationDestination(for: Course.self) { course in
            CourseTeePickerView(course: course) { selection in
                path.append(selection)  // Pushes RoundCourseSelection
            }
        }
        .navigationDestination(for: RoundCourseSelection.self) { selection in
            RoundSetupView(selection: selection) { start in
                scorecardVM = ScorecardViewModel(start: start)
                path.append(RoundRoute.entry)  // Pushes RoundRoute.entry
            }
        }
        // ...
}
```

**Hypothesis 1:** When `CourseTeePickerView` calls `onSelect`, it may be dismissing itself (via `presentationMode` or similar) which pops the navigation stack back to root.

**Hypothesis 2:** `RoundSetupView`'s `onStart` callback sets `scorecardVM` which triggers a view update that recreates `NavigationStack`, resetting `path`.

**Hypothesis 3:** The `path` binding is losing state because `NewRoundView` is being recreated by a parent view update.

---

## Investigation Steps

Before fixing, confirm the root cause:

1. **Add logging** to `NewRoundView`:
   ```swift
   .onChange(of: path) { old, new in
       print("Path changed: \(old) → \(new)")
   }
   ```

2. **Add logging** to `CourseTeePickerView.onSelect`:
   ```swift
   print("Tee selected: \(selection.courseName), path count: \(path.count)")
   ```

3. **Check if `presentationMode.wrappedValue.dismiss()` is being called** anywhere in `CourseTeePickerView` or `RoundSetupView`.

4. **Check if parent view of `NewRoundView` is updating** — add `.id(UUID())` or logging to `ContentView` or wherever `NewRoundView` is instantiated.

---

## Fix Options

### Option A: Remove explicit dismiss (if present)

If `CourseTeePickerView` or `RoundSetupView` calls `presentationMode.dismiss()`, remove it. The navigation stack handles popping automatically when `path` changes.

### Option B: Stabilize NavigationStack identity

If the stack is being recreated, ensure `NewRoundView` has stable identity:

```swift
// In parent view (ContentView or wherever NewRoundView is used)
NewRoundView()
    .id("new-round-view")  // Stable ID prevents recreation
```

### Option C: Use `.navigationDestination` with value-based routing only

Current code mixes `navigationDestination(for: Course.self)` and manual `path.append()`. Ensure all navigation is value-based:

```swift
// Instead of callback-based, use path.append consistently
CourseTeePickerView(course: course, onSelect: { selection in
    path.append(selection)  // This should push RoundSetupView
})
```

**Verify:** `RoundCourseSelection` conforms to `Hashable` properly.

### Option D: Replace callback pattern with binding

Instead of callbacks that may trigger side effects, use a state machine:

```swift
enum RoundFlowState: Hashable {
    case searching
    case selectingTees(Course)
    case settingUp(RoundCourseSelection)
    case enteringScorecard(ScorecardViewModel)
    case reviewing
    case summary
}

@State private var flowState: RoundFlowState = .searching
```

This is more explicit but requires more refactoring.

---

## Recommended Fix (Minimal Change)

**Step 1:** Check for `presentationMode.dismiss()` in `CourseTeePickerView` and `RoundSetupView`. Remove if found.

**Step 2:** Add `print` logging to confirm path state.

**Step 3:** If path is being reset, ensure `NavigationStack` isn't recreated by wrapping `NewRoundView` in a stable container:

```swift
// In ContentView or wherever NewRoundView is presented
.sheet(isPresented: $showNewRound) {
    NewRoundView()
        .id("new-round")  // Prevents recreation on parent update
}
```

**Step 4:** If the issue is `scorecardVM` assignment triggering recreation, defer the assignment:

```swift
// Instead of immediate assignment in callback:
RoundSetupView(selection: selection) { start in
    // Defer to next runloop to avoid triggering during navigation
    DispatchQueue.main.async {
        scorecardVM = ScorecardViewModel(start: start)
        path.append(RoundRoute.entry)
    }
}
```

---

## Acceptance Criteria

- [ ] Search → select course → tee picker appears
- [ ] Select tee → round setup appears (not kicked back to search)
- [ ] Complete round setup → scorecard entry appears at hole 1
- [ ] No double-selection of course required
- [ ] Build green (`xcodebuild`)
- [ ] Works on device (Duk test)

---

## Files to Modify

| File | Changes |
|------|---------|
| `NewRoundView.swift` | Add logging, test fixes |
| `CourseTeePickerView.swift` | Remove dismiss() if present |
| `RoundSetupView.swift` | Remove dismiss() if present, defer VM assignment |
| `ContentView.swift` | Stable ID for NewRoundView container |

---

## Open Questions for Duk

1. **Does the bug happen every time or intermittently?**
2. **Does it happen on simulator too or only device?**
3. **Any specific courses or tees that trigger it?**

---

*Spec by Kanary. Fix by Claude Code. Verification by Duk.*
