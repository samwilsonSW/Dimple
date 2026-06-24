# Agent Status Board

> **Who updates this:** Claude Code (frontend agent)  
> **Who reads this:** Kanary (OpenClaw orchestrator), Duk (conductor)  
> **When to update:** After every meaningful progress step, blocker, or completion  
> **Rule:** If you're Claude Code and you haven't updated this in >2 hours of work, update it.

---

## Claude Code — Current Task

- **Task:** Scorecard Entry View
- **Started:** 2026-06-23
- **Status:** Not started
- **Branch:** Kanary

## Progress

- [ ] Create ScorecardEntryView.swift
- [ ] Wire course_id + tee selection from CourseSearchView
- [ ] Build per-hole input form (score, putts, fairway, GIR)
- [ ] Handle par 3 (hide fairway toggle)
- [ ] Connect to POST /api/v1/rounds with hole_data
- [ ] Display round_stats response
- [ ] Test on device

## Blockers

- None

## Questions for Duk

- None

## Completed (Last 7 Days)

- 2026-06-23: Security fix — moved the Supabase anon key out of source into a git-ignored `Secrets.xcconfig` (build-time Info.plist injection, runtime read). Tripped GitGuardian on the public repo. Open as PR into Kanary (`security/externalize-supabase-key`). Anon key being rotated in Supabase; RLS verified (anon role has no table access).
- 2026-06-22: Course Search UI complete — search, select, tee picker working

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

*Last updated: 2026-06-23*
*Next expected update: When Claude Code starts Scorecard Entry View*
