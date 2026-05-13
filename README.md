# ⛳ Dimple

Golf Intelligence — track your game, improve your score.

## What is this?

A mobile-first PWA for tracking golf shots during a round. Designed for fast, one-handed operation on the course.

## Features (MVP)

- [x] One-tap shot entry (club + result)
- [x] GPS capture per shot
- [x] Offline-first (localStorage)
- [x] Round history
- [ ] Course database
- [ ] Strokes gained analysis
- [ ] Shot dispersion visualization
- [ ] Export to Kepler.gl

## Development

```bash
# Serve locally (Python 3)
python -m http.server 8000

# Or Node
npx serve .
```

Open `http://localhost:8000` on your phone or browser.

## Install as App

1. Open in mobile Safari/Chrome
2. Tap "Share" → "Add to Home Screen"
3. Launch from home screen like a native app

## Data Model

See `docs/data-model.md` for the JSON schema.

## Stack

- Vanilla JS (no build step)
- PWA (service worker, manifest)
- localStorage (SQLite later if needed)
- GPS API for shot locations

## Branch Strategy

- `main` — production
- `feature/*` — merge requests only
