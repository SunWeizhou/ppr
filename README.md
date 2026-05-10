# Agent Literature Research Assistant

A local-first Agent literature research assistant for turning research
questions into discovered papers, agent analysis, reading decisions, watch
subscriptions, and saved research assets.

**Inbox / Search / Detail / Reading / Watch / Settings**

## Quick Start

```bash
python -m pip install -r requirements.txt -c constraints.txt
cp user_profile.example.json user_profile.json
python web_server.py
```

Open http://localhost:5555.

## Testing

```bash
python -m pytest tests/ -q
```

Individual test files can be run with pytest or unittest:

```bash
python -m pytest tests/test_repository_hygiene.py -v
python -m unittest tests.test_repository_hygiene -v
```

## How It Works

- **Inbox** — daily agent-curated decision queue.
- **Search / Explore** — question-driven candidate discovery.
- **Paper Detail** — agent analysis, evidence, and action center.
- **Reading** — active workbench for skim and deep-read decisions.
- **Watch** — long-term monitoring for questions, authors, venues, and hits.
- **Settings** — local profile, sources, AI provider, backup, and diagnostics.

No accounts. No cloud requirement. Durable workflow state lives in local SQLite.

## Docs

- [PRD](docs/PRD.md) — target product direction, core objects, workflow, gaps, priorities
- [Architecture](docs/ARCHITECTURE.md) — runtime architecture, data flow, and state policy
- [Agent Workflow](docs/AGENT_WORKFLOW.md) — reusable multi-agent product development workflow
- [Deployment](docs/DEPLOYMENT.md) — local, pip, and Docker deployment notes
- [Release Checklist](docs/RELEASE_CHECKLIST.md) — release verification checklist

## License

MIT
