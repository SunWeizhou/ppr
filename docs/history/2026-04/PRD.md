# PRD v2: Personalized Paper Recommender / Research Triage Desk

## 1. Product Definition

This is not a generic arXiv RSS reader or a paper search engine.

It is a local-first personalized research triage desk that helps the user answer:

1. Which papers are worth reading today?
2. What is this paper about?
3. Why was this paper recommended to me?
4. Should I ignore it, skim it, deep read it, or save it?
5. What is new from my tracked authors, venues, and research questions?

## 2. Core Product Goals

1. Personalized recommendation based on:
   - research profile keywords
   - Zotero library
   - user feedback
   - queue behavior
   - collections
   - subscriptions

2. In-app paper understanding:
   - abstract
   - AI analysis
   - why recommended
   - reading recommendation

3. Reading workflow:
   - Relevant
   - Ignore
   - Skim Later
   - Deep Read
   - Saved
   - Archived

4. Long-term monitoring:
   - research question subscriptions
   - author subscriptions
   - venue subscriptions
   - recent hits

## 3. Product Principles

- Local first
- Inbox first
- Explainable recommendation
- AI-assisted but not AI-dependent
- Progressive disclosure
- Subscription is core
- Do not show more papers; help decide which papers matter

## 4. Information Architecture

Top-level navigation:

- Inbox
- Queue
- Library
- Monitor
- Settings

Search is contextual, not a top-level destination.

## 5. Inbox Requirements

Inbox must show:

- Title
- Authors
- Abstract
- AI Analysis
- Why Recommended
- Actions

Primary actions:

- Relevant
- Ignore
- Skim Later
- Deep Read
- Open arXiv

More actions:

- Add to Collection
- View full explanation

Inbox must not expose:

- Download PDF
- Export BibTeX
- Follow author
- Archive
- full diagnostics
- ranking breakdown

## 6. AI Analysis Requirements

AI Analysis must include:

- one_sentence_summary
- problem
- method
- contribution
- limitations
- why_it_matters
- recommended_reading_level

AI Analysis must be:

- cached locally
- optional
- failure-tolerant
- testable without real API keys
- keyed by canonical paper_id

## 7. Monitor Requirements

Monitor is core and must not be deleted.

It must support:

- Research Questions
- Authors
- Venues
- Recent Hits

Eventually these should be unified as Subscription objects:

- type: query / author / venue
- name
- query_text
- payload_json
- enabled
- latest_hit_count
- last_checked_at

## 8. Non-goals

Do not implement:

- accounts
- cloud sync
- multi-user collaboration
- social recommendation
- citation graph
- desktop app
- browser extension
- large frontend rewrite
- mandatory external AI provider

## 9. Codex Constraints

Codex must not:

- rewrite the whole app
- introduce React/Vue
- require real API keys in tests
- delete Authors / Venues / Queries
- expose PDF / BibTeX / diagnostics in Inbox primary flow
- make JSON or Markdown primary state again
- add features without tests

Codex must:

- keep local-first
- keep routes thin
- move business logic into services
- use canonical arXiv IDs
- cache AI analysis
- provide no-provider fallback
- update tests
- preserve existing user data compatibility
