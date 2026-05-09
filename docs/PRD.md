# Agent Literature Research Assistant — PRD

## Product Definition

Agent Literature Research Assistant is a local-first research tool for turning a
research question into a reviewed set of papers, evidence, reading decisions,
and durable research assets.

The product is not a generic paper feed. Its job is to help an individual
researcher answer:

1. What am I trying to learn or decide?
2. Which papers are credible candidates for that intent?
3. What does each paper claim, prove, measure, or leave unresolved?
4. Which papers should I ignore, skim, deep read, or save?
5. What should the system keep watching as the research direction evolves?

## Core Users

- Independent researchers tracking fast-moving topics.
- Graduate students building a literature map for a thesis or project.
- Applied scientists deciding which methods are worth reading or trying.
- Engineers using papers as evidence for product or model decisions.

## Core Objects

- **Research Question**: A user-stated intent, hypothesis, method family, or
  information need. It drives discovery and later monitoring.
- **Paper Candidate**: A paper returned by arXiv, search, subscriptions, or a
  future source connector.
- **Agent Analysis**: Structured analysis generated or assembled by the system:
  contribution, method, evidence quality, limitations, relevance, and caveats.
- **Evidence**: Verifiable support for an analysis claim, including abstract
  snippets, metadata, user notes, citation context, and links to source pages.
- **Reading Decision**: A user action that moves a paper through the workflow:
  Ignore, Skim, Deep Read, or Save.
- **Research Asset**: A durable item the user wants to keep: saved paper,
  collection, note, search, decision record, or exported digest.
- **Subscription**: A long-running monitor over a question, author, venue,
  keyword cluster, or source filter.

## Core Workflow

1. **Define research intent**
   - User states a research question or maintains a profile of topics.
   - The system translates that intent into searchable queries and monitoring
     subscriptions.

2. **Discover candidates**
   - The system fetches candidate papers from configured sources.
   - Candidates are ranked by relevance, freshness, user feedback, and optional
     local context such as Zotero similarity.

3. **Agent analyzes and explains**
   - For each useful candidate, the system prepares a concise analysis with
     evidence and clear recommendation reasons.
   - The product must degrade gracefully when no AI provider is configured:
     users still get abstracts, metadata, and rule-based reasons.

4. **User decides**
   - The primary loop is decision-making, not passive browsing.
   - The expected decisions are Ignore, Skim, Deep Read, and Save.

5. **System learns and monitors**
   - User decisions update future ranking and subscriptions.
   - Saved searches and subscriptions continue watching the research area.
   - Research assets remain local and exportable.

## Target Surfaces

### Inbox

Daily agent-curated decision queue. It should show only the papers that need a
decision now, with enough analysis and evidence to act quickly.

Required target behavior:
- Show title, authors, source metadata, short abstract, agent summary, and why
  the candidate was surfaced.
- Prioritize decision actions: Ignore, Skim, Deep Read, Save.
- Avoid turning the first screen into diagnostics, export controls, or ranking
  internals.

### Search / Explore

Question-driven discovery surface. It starts from a research question and helps
the user inspect, save, and convert useful searches into subscriptions or
collections.

Required target behavior:
- Accept natural research questions and keyword queries.
- Return candidates without requiring a pre-existing daily run.
- Save result metadata so paper detail pages remain available after search.
- Allow a useful query to become a subscription or collection seed.

### Paper Detail

Single-paper evidence and action center. It should make the agent's reasoning
inspectable.

Required target behavior:
- Show structured agent analysis: problem, method, contribution, evidence,
  limitations, and relevance.
- Show why this paper matches the current research intent.
- Provide action controls for reading decision, collection, source link, and
  optional export.

### Reading

Active reading workbench. It is for papers the user has already decided deserve
attention.

Required target behavior:
- Separate skim candidates from deep-read candidates.
- Let the user advance status, save, archive, and collect papers.
- Keep reading state independent from discovery ranking.

### Watch

Long-term monitoring surface for questions, authors, venues, and other source
filters.

Required target behavior:
- Show subscriptions and recent hits.
- Explain why each hit matched.
- Let users route hits into Inbox, Reading, or saved research assets.

### Settings

Local profile, sources, AI provider, and diagnostics.

Required target behavior:
- Edit profile keywords and preferences.
- Configure sources and optional AI provider without exposing secrets.
- Provide backup, restore, database maintenance, and connection diagnostics.

## Non-Goals

- Team collaboration, shared workspaces, permissions, or comments.
- Cloud sync or hosted accounts.
- A fully automatic literature review that replaces researcher judgment.
- Mandatory external AI provider.
- Frontend framework rewrite as a product requirement.
- Full citation graph exploration in the near term.

## Current Implementation Gap

The current application has the right local-first foundation but has not reached
the target product shape yet.

- Daily recommendations, search, paper detail, reading, watch, settings, and
  onboarding exist, but the user journey still feels like separate pages rather
  than one agent-assisted research loop.
- AI analysis exists as an optional enrichment, but evidence and explanation are
  not yet strong enough to support confident reading decisions.
- Search can surface and persist candidates, but it is still keyword-oriented
  rather than fully research-question-oriented.
- Reading state exists, but active reading notes, evidence capture, and research
  asset formation are still thin.
- Watch subscriptions exist, but hit triage should become more tightly connected
  to research questions and downstream decisions.
- Documentation previously mixed old product constraints with current direction;
  the canonical docs should now describe the target assistant clearly.

## Next-Stage Priorities

1. **Make the core loop coherent**
   - Research question -> candidates -> analysis -> decision -> saved asset.
   - Every page should support this loop without forcing the user to infer what
     to do next.

2. **Strengthen paper detail**
   - Add evidence-backed analysis sections.
   - Distinguish factual metadata, model-generated analysis, and user decisions.

3. **Improve decision capture**
   - Make Ignore, Skim, Deep Read, and Save consistent across surfaces.
   - Store decisions as reusable ranking and monitoring signals.

4. **Make Watch useful**
   - Treat subscriptions as live research intents.
   - Route matched papers into the same decision workflow as daily candidates.

5. **Harden local-first operations**
   - Keep install, start, backup, restore, and no-key AI fallback reliable.
   - Ensure secrets are never rendered or exported accidentally.

## Success Criteria

- A new user can install, start, onboard, and search without editing JSON.
- The user can start with a research question and reach paper details with
  persistent metadata.
- For a candidate paper, the system explains what it is about, why it matters,
  why it was surfaced, and what evidence supports that analysis.
- The user can consistently choose Ignore, Skim, Deep Read, or Save.
- Reading and Watch surfaces preserve state across restarts.
- Optional AI analysis improves the experience but is not required for the core
  workflow to function.
- Local data remains on disk and can be backed up or restored.
