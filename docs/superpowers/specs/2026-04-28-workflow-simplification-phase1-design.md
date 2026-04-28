# Phase 1: Workflow Simplification — Information Architecture

## Context

The system has sufficient capabilities (recommendations, subscriptions, collections, AI, backup) but the five pages have overlapping responsibilities and unclear boundaries. Phase 1 tightens each page's purpose without adding new features or changing backend APIs.

## Design

### Inbox — "What to read today, where to route it"

Primary actions (prominent): `Relevant` / `Ignore` / `Skim Later` / `Deep Read`
Secondary actions (menu): `Saved` / `Add to Collection` / `Follow Author`
Post-triage CTA: After finishing today's papers → "Go to Queue"

Right panel always answers: what this paper is, why it was recommended, what to do next.

Files: `templates/home_research.html`, `static/js/inbox.js`

### Queue — "What I'm reading, how far along"

Tabs reduced to active reading states only: `Skim Later` / `Deep Read` / `In Progress`
`Saved` / `Archived` removed from Queue — these belong in Library.
Top area merged with list into a unified reading workbench.

Files: `templates/queue_research.html`, `app/viewmodels/queue_viewmodel.py`, `app/routes/queue.py`

### Library — "What I keep long-term"

`Collections` as primary entry. `Saved Papers` as secondary section. `History` demoted to a footer link, not a main tab.

Files: `templates/library_research.html`, `app/viewmodels/library_viewmodel.py`

### Monitor — "What changed in my tracked topics"

Default view: `Recent Hits`. Subscription types (`Authors` / `Venues` / `Queries`) become filter pills, not primary tabs.

Files: `templates/monitor_research.html`, `app/viewmodels/monitor_viewmodel.py`

### Settings — "Configure and diagnose"

Split into sections: `Profile` / `Sources` / `Ranking` / `Diagnostics`
System health, backup/restore, DB repair, job repair → all under Diagnostics.

Files: `templates/settings_research.html`, `app/viewmodels/settings_viewmodel.py`

## Non-goals

- No backend API changes
- No database schema changes
- No new AI features
- No new data sources

## Acceptance Criteria

- Each page has a single clear purpose, obvious on first glance
- No action appears with the same semantics on two different pages
- Inbox → Queue → Library forms a coherent forward flow
- Monitor → Inbox/Queue/Collection handoff works
