# 2026-04-09 System Audit And Refactor Notes

## Scope

This pass implements the first staged refactor of the local-first arXiv recommender. The goal was not a rewrite. The goal was to close the biggest product and workflow gaps while preserving the existing Flask + Jinja architecture.

## What Was Implemented

### Information architecture

- Replaced page-level navigation with six stable work objects: `Inbox`, `Track`, `Explore`, `Library`, `Insights`, `Settings`.
- Added a shared app status bar so queue, liked count, collections, saved searches, and latest job state are visible across the product.
- Introduced new first-class screens:
  - `Track` at `/track`
  - `Library` at `/library`

### Inbox workflow

- Rebuilt the home page from a deck-style single-card viewer into a three-column workspace:
  - left: date navigation, filters, themes, asset shortcuts
  - center: ranked paper list
  - right: fixed detail and action panel
- Added direct actions from the detail panel:
  - like / dislike
  - queue to any of the five statuses
  - follow first author
  - add to collection
  - export BibTeX
  - open PDF / arXiv

### Track workflow

- Merged scholar tracking and journal monitoring into a single `Track` page.
- Kept `/scholars` and `/journal` as deeper management pages, but moved the main entry point to `/track`.
- Added scholar add / parse / remove actions directly on the new `Track` page.

### Explore workflow

- Reworked `/search` into an `Explore` page instead of a one-off search page.
- Added direct actions on search results:
  - queue to `Skim Later`, `Deep Read`, `Saved`, `Archived`
  - add to collection
  - follow first author
  - export BibTeX
- Added `Save as Saved Search` and `Create Collection from current query`.

### Library workflow

- Built a unified `Library` page with tabs for:
  - `Queue`
  - `Liked`
  - `Ignored`
  - `Collections`
  - `Saved Searches`
- Added queue status filters and bulk queue moves.
- Added collection detail view, rename/delete, paper removal, and “continue exploring” link.
- Added saved search detail view, edit/delete, rerun, and convert-to-collection.

### State and settings fixes

- `theoryEnabled` is now a real setting in `user_profile.json`.
- Theory bonus logic is now gated by both:
  - `prefer_theory`
  - `theory_enabled`
- Settings save now preserves hidden demote topics instead of wiping them.
- Settings now consistently write theory keywords back to the unified profile.

### Recommendation explanation consistency

- Added dated recommendation snapshots under `cache/recommendation_runs/<date>.json`.
- Historical digest parsing now attempts to load dated structured breakdowns first.
- If historical structured data is missing, the server reconstructs a reasonable breakdown from stored text so the explanation layer degrades more gracefully.

### Missing feature closure

- Expanded collection APIs:
  - create
  - update
  - detail
  - add paper
  - remove paper
- Expanded saved search APIs:
  - create
  - update
  - delete
  - rerun
- Added queue bulk update API.
- Added BibTeX export endpoint at `/api/export/bibtex/<paper_id>`.
- Fixed `/api/related/<paper_id>` so it no longer uses broken request setup and malformed fallback logic.
- Added `follow_author` handling to `/api/feedback`.

## Product Gaps Still Intentionally Left For Later

These are not ignored. They were left out of this stage to keep the refactor incremental.

- Service-layer split is still incomplete. `web_server.py` remains too large.
- README claims and real scoring behavior still need a full assertion pass.
- Saved search “recent hits” are previewed on page render but are not yet persisted as historical runs.
- Collection collaboration / tagging / note-taking is still minimal.
- Job center is visible, but not yet a dedicated operational dashboard.
- `/liked` and `/disliked` still exist as compatibility views instead of being fully retired in favor of `/library`.

## Refactor Direction After This Pass

Next refactor should move code toward five clearer layers:

1. ingestion
2. ranking
3. profile_config
4. library_state
5. web_ui

The highest-value next step is to extract library and search workflow helpers out of `web_server.py` before adding more product surface.
