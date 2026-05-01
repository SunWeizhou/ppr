# Paper Recommender / Research Triage Desk — PRD

## Product Definition

A local-first research triage desk for arXiv papers. The goal is not to give
researchers more papers — it is to help them decide **which papers matter today**,
move them through a reading workflow, and monitor what they care about over time.

The product answers five questions:

1. Which papers are worth reading today?
2. What is this paper about?
3. Why was this paper recommended to me?
4. Should I ignore it, skim it, deep-read it, or save it?
5. What is new from my tracked authors, venues, and research questions?

## Three Surfaces

### Today (Inbox)

Home page. The daily paper triage center. Each paper shows:

- Title, authors, abstract
- AI analysis (one-sentence summary, problem, method, contribution, limitations, why it matters)
- Why Recommended (matched topics, subscriptions, Zotero similarity, feedback signals)
- Primary actions: Relevant, Ignore, Skim Later, Deep Read, Open arXiv

Secondary actions (Add to Collection, View full explanation) are behind a
disclosure. PDF download, BibTeX export, and ranking diagnostics are not exposed
in the Inbox primary flow.

### Reading (Queue)

The reading workflow. Papers are in one of five states: Inbox → Skim Later /
Deep Read → Saved / Archived. Queue surfaces a "Today's Reading Plan" (top 3
Deep Read, top 5 Skim Later) so the user knows what to read next.

### Watch (Monitor)

Long-term tracking. Unified subscription model covers three subscription types:

- **query** — research question subscriptions (e.g. "GraphRAG compression")
- **author** — tracked authors
- **venue** — tracked journals and conferences

Recent Hits aggregates hits across all subscriptions. Each hit supports: View
detail, Send to Inbox, Skim Later, Deep Read, Add to Collection, Ignore.

## Five Principles

1. **Local First.** User data lives on disk. No accounts, no cloud sync. SQLite
   is the durable state source; JSON and Markdown are caches or export artifacts.

2. **Inbox First.** The home page serves only today's paper triage. Complex
   configuration, PDF management, and debugging tools belong elsewhere.

3. **Explainable Recommendation.** Every recommended paper must answer "why was
   this recommended?" with structured reasons (topics, subscriptions, Zotero
   similarity, feedback history), not a raw score.

4. **AI-Assisted, Not AI-Dependent.** AI analysis is a core part of the reading
   experience, but the system must work without it. Without an AI provider, the
   user still sees abstracts and rule-based recommendation reasons.

5. **Progressive Disclosure.** The default interface is simple. PDF download,
   BibTeX export, ranking diagnostics, and advanced tuning are behind secondary
   entry points or an Advanced section.

## Non-Goals

- Accounts, cloud sync, multi-user collaboration
- Social recommendation, citation graphs, automatic literature reviews
- Desktop app, browser extension, mobile client
- Frontend framework rewrite (React, Vue)
- Mandatory external AI provider

## Success Criteria

- A new user can onboard without editing JSON
- The Inbox shows today's papers with abstract, AI analysis, and recommendation reasons
- The user can triage a paper in under 30 seconds
- Queue forms a daily reading plan the user can act on
- Monitor aggregates subscription hits into a single actionable view
- All state persists locally in SQLite
- The system is fully functional without an AI provider configured
