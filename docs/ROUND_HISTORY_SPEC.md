# Round History List — Spec

> **Status:** Ready for Claude Code  
> **Owner:** Kanary (spec) → Claude Code (build) → Duk (taste test)  
> **Priority:** P0 — blocks full round flow (submit → view history → ask coach)  
> **Updated:** 2026-06-25

---

## Overview

A scrollable list of all submitted rounds. This is the "home screen" for a golfer's data — the place they check after a round, compare scores, and tap into for detailed review or coaching.

**Design principle:** Fast scan, then drill down. The list shows just enough to compare rounds at a glance. Everything else is one tap away.

---

## Data Source

```
GET /api/v1/rounds?user_id={uuid}&limit=50
```

**Response shape (from API_CONTRACT v0.6.0):**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "count": 3,
  "rounds": [
    {
      "id": 123,
      "round_date": "2026-06-24",
      "course": { "name": "Rawls Course", "city": "Lubbock", "state": "TX" },
      "handicap_index": 29.0,
      "reflection": "Driver was wild today...",
      "round_stats": {
        "total_score": 98,
        "total_putts": 34,
        "gir_count": 3,
        "gir_percentage": 0.167,
        "fairways_hit": 4,
        "fairways_possible": 14,
        "fairway_percentage": 0.286,
        "sg_putting": -2.4,
        "sg_approach": -4.1,
        "strokes_over_under": 26.0,
        "avg_putts_per_hole": 1.89,
        "avg_score_to_par": 5.44
      }
    }
  ]
}
```

**Note:** `round_stats` is a nested object (Supabase join). It may be `null` if stats calc failed.

---

## Layout: Round History List

### Empty State

```
┌─────────────────────────────────────┐
│                                     │
│         [Golf ball icon]            │
│                                     │
│      No rounds yet                  │
│                                     │
│    Play a round and enter your      │
│    scores to see them here.         │
│                                     │
│         [ + New Round ]             │  ← primary button
│                                     │
└─────────────────────────────────────┘
```

**Behavior:**
- Show when `count === 0`
- "+ New Round" button navigates to Course Search
- Icon: `flag.fill` or custom golf ball

---

### List View (with data)

```
┌─────────────────────────────────────┐
│  ← Back    Round History            │  ← nav bar
│                                     │
│  ┌───────────────────────────────┐  │
│  │  Rawls Course          +26    │  │  ← card
│  │  Lubbock, TX         98 (72)  │  │
│  │  Jun 24              3 GIR    │  │
│  │  [G] [P] [F] [A]              │  │  ← SG chips
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  The Links            +18     │  │
│  │  Houston, TX         90 (72)  │  │
│  │  Jun 20              5 GIR    │  │
│  │  [G] [P] [F] [A]              │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  Pinehurst No. 2      +14     │  │
│  │  Pinehurst, NC       88 (74)  │  │
│  │  Jun 15              8 GIR    │  │
│  │  [G] [P] [F] [A]              │  │
│  └───────────────────────────────┘  │
│                                     │
│         [ + New Round ]             │  ← floating or bottom
│                                     │
└─────────────────────────────────────┘
```

---

## Round Card Detail

Each card shows:

| Element | Data | Format |
|---------|------|--------|
| **Course name** | `course.name` | Bold, 17pt |
| **Location** | `course.city, course.state` | Subtitle, 15pt, gray |
| **Date** | `round_date` | "Jun 24", "Yesterday", "Mon" (relative if < 7 days) |
| **Score** | `round_stats.total_score` | Large, bold |
| **Par** | sum of hole pars (or `total_score - strokes_over_under`) | In parentheses next to score |
| **vs Par** | `strokes_over_under` | "+26" in red, "-2" in green, "E" in black |
| **GIR** | `round_stats.gir_count` | "3 GIR" or "3/18 GIR" |
| **SG Chips** | 4 mini chips | See below |

---

## SG Chips (Mini)

Four small colored pills showing SG categories:

```
[G -1.2]  [P -0.8]  [F +0.3]  [A -2.4]
```

| Chip | Category | Color | Data |
|------|----------|-------|------|
| **G** | Green (putting) | Blue | `sg_putting` |
| **P** | Short game | Orange | derived* |
| **F** | Fairway (driving) | Green | derived* |
| **A** | Approach | Purple | `sg_approach` |

**Colors:**
- Positive SG (good): Green text
- Negative SG (bad): Red text
- Zero: Gray text

**Derived categories:**
- Short game = `sg_putting` (simplified for now)
- Driving = not directly in stats; show "—" until we calculate it

**Note:** If `round_stats` is null, show "Stats unavailable" in gray instead of chips.

---

## Interactions

### Tap Card
- Navigates to **Round Detail View** (future spec — for now, show placeholder)
- Placeholder: "Round detail coming soon" with round summary

### Swipe Left (iOS standard)
- Reveal "Delete" action
- Confirm with alert: "Delete this round? This cannot be undone."
- Call `DELETE /api/v1/rounds/{round_id}` (not implemented yet — UI only for now)

### Pull to Refresh
- Re-fetch from `GET /api/v1/rounds`
- Show spinner while loading

### Scroll
- Standard iOS scroll
- Load more when approaching bottom (if we implement pagination later)

---

## Navigation

### Entry Points

| From | How | State |
|------|-----|-------|
| **Submit success** | Auto-navigate after round submit | Show new round at top |
| **Coach tab** | "View History" button | Normal list |
| **Tab bar** | "History" tab (if we add one) | Normal list |

### Exit Points

| To | How |
|----|-----|
| **Round Detail** | Tap card |
| **New Round** | "+ New Round" button |
| **Coach** | "Ask Coach" button (future) |

---

## Sorting & Grouping

**Default sort:** Newest first (`round_date DESC`)

**Grouping (future, not required now):**
- By month: "June 2026", "May 2026"
- By course: "Rawls Course (4 rounds)"

**For now:** Flat list, newest first.

---

## Edge Cases

| Case | Handling |
|------|----------|
| **No stats** (`round_stats` null) | Show score only, "Stats unavailable" subtitle |
| **No course name** | Show "Unknown Course" |
| **No location** | Omit location line |
| **Very long course name** | Truncate with "..." |
| **Many rounds** | Scroll naturally; no pagination for now |
| **Offline** | Show cached data with "Last updated" timestamp |
| **Loading** | Skeleton cards (3-5 gray placeholders) |
| **Error** | "Couldn't load rounds. Pull to retry." |

---

## API Integration

### Fetch Rounds

```swift
final class RoundHistoryService {
    static let shared = RoundHistoryService()
    private let baseURL = "http://localhost:8000"
    
    func fetchRounds(limit: Int = 50) async throws -> [RoundHistoryItem] {
        let session = try await supabase.auth.session
        let userID = session.user.id.uuidString.lowercased()
        
        let url = URL(string: "\(baseURL)/api/v1/rounds?user_id=\(userID)&limit=\(limit)")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        let decoded = try JSONDecoder().decode(RoundHistoryResponse.self, from: data)
        return decoded.rounds
    }
}
```

### Models

```swift
struct RoundHistoryResponse: Decodable {
    let user_id: String
    let count: Int
    let rounds: [RoundHistoryItem]
}

struct RoundHistoryItem: Decodable, Identifiable {
    let id: Int
    let round_date: String
    let course: CoursePayload
    let handicap_index: Double
    let reflection: String?
    let round_stats: RoundStats?
    
    // Computed
    var displayDate: String { /* relative date */ }
    var scoreDisplay: String { /* "98 (72)" */ }
    var vsParDisplay: String { /* "+26" */ }
}
```

---

## Performance

- Fetch on view appear
- Cache in memory (no Core Data for now)
- Refresh on pull-to-refresh only
- Images: none (text-only list)

---

## Accessibility

- Dynamic Type support (list scales with system font size)
- VoiceOver: "Rawls Course, Lubbock Texas, June 24, score 98, 26 over par, 3 greens in regulation"
- High contrast: ensure red/green SG chips are distinguishable (use +/− signs, not just color)

---

## Future (Not Now)

- Round Detail View (per-hole breakdown)
- Filter by course, date range
- Search rounds
- Share round (screenshot or link)
- Compare two rounds side-by-side
- Trend graphs (handicap over time)

---

## Open Questions for Duk

1. **Tab bar or standalone?** Should Round History be a tab in the main app, or only accessible from Coach/submit flow?
2. **Delete rounds?** Should users be able to delete rounds? (UI ready, backend not)
3. **Round detail priority?** After this list, what's more important: round detail view or coach chat polish?

---

## Acceptance Criteria

- [ ] List displays all submitted rounds newest-first
- [ ] Each card shows course, date, score, vs par, GIR count
- [ ] SG chips display (or "Stats unavailable" if null)
- [ ] Empty state with "+ New Round" button
- [ ] Pull-to-refresh works
- [ ] Tap card navigates to placeholder detail
- [ ] Loading skeleton shown while fetching
- [ ] Error state with retry
- [ ] Accessible with VoiceOver
- [ ] Works in dark mode
