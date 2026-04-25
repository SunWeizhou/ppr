# Paper Recommender / Research Triage Desk

A local-first research triage desk for arXiv papers. The product goal is not to
give researchers more papers; it is to help them decide what to read today, move
papers into a reading workflow, preserve long-term research assets, and monitor
authors, venues, and queries.

The intended product structure is:

```text
Inbox / Queue / Library / Monitor / Settings
```

Inbox First is the main product rule: the home page should only serve today's
paper triage.

## Product Direction

- Inbox: today's recommendation list, filters, detail panel, why recommended,
  Relevant/Ignore, Skim Later/Deep Read, and Open arXiv.
- Queue: reading workflow states such as Inbox, Skim Later, Deep Read, Saved,
  and Archived.
- Library: collections, saved papers, and history.
- Monitor: authors, venues, query subscriptions, and recent hits.
- Settings: profile, sources, ranking, and system settings.

Search remains a contextual capability. It should not be treated as a top-level
navigation destination.

## Quick Start

Install dependencies:

```bash
python -m pip install -r requirements.txt -c constraints.txt
```

Create a private local profile from the example:

```bash
cp user_profile.example.json user_profile.json
```

Edit `user_profile.json` for your research topics and optional Zotero database
path. This file is private local state and is ignored by git.

Start the Flask app:

```bash
python web_server.py
```

Open http://localhost:5555.

## Tests

Run the productization and regression tests with explicit discovery:

```bash
python -m unittest discover -s tests -v
```

`python -m unittest discover -v` is also expected to discover tests from the
repository root.

## Recommendation Evaluation

Phase 3 adds a local offline evaluator for the current heuristic ranking. It
uses SQLite workflow state and cached recommendation snapshots, and it does not
fetch arXiv or change the default recommendation pipeline.

```bash
python -m evaluation.run_evaluation --output-dir reports --k 5,10,20
```

The command writes paired JSON and Markdown reports under `reports/`, which is
ignored by git.

## Optional DeepSeek AI Analysis

AI Analysis is optional. Without an API key, the app still works and shows the
original abstract plus rule-based recommendation reasons.

To enable DeepSeek-compatible AI analysis, set:

```bash
export DEEPSEEK_API_KEY="your_api_key_here"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL="deepseek-chat"
```

Never commit your API key.

## Runtime State

Runtime data is intentionally not tracked:

- `user_profile.json`, `user_config.json`, `keywords_config.json`, and
  `my_scholars.json` are private local configuration/state.
- `cache/` contains generated caches, recommendation runs, embeddings, PDFs,
  and SQLite runtime files.
- `history/` and `daily_arxiv_digest.md` contain generated digest output.
- `reports/` is reserved for generated evaluation reports.

SQLite is the target primary state source for durable workflow state. JSON and
Markdown files should only be caches, import/export artifacts, or display
outputs unless a future architecture document explicitly says otherwise.

## Documentation Map

- `PRD.md`: canonical product direction.
- `PRODUCT_REDESIGN_EXECUTION.md`: product redesign execution notes.
- `docs/ARCHITECTURE.md`: current architecture, target architecture, and state
  source policy.
- `docs/AGENTS.md`: agent roles, PR rules, and product/architecture guardrails.
- `docs/archive/removed-artifacts.md`: record of runtime and draft artifacts
  removed during Phase 0 hygiene.

## Development Rules

- Keep the app local-first and easy to run.
- Do not introduce accounts, cloud sync, LLM summaries, graph/citation rewrites,
  or a large frontend split before the product skeleton is stable.
- Preserve existing behavior while splitting large files into routes, services,
  repositories, models, and viewmodels through small PRs.
- Add or update tests for each behavior change.
