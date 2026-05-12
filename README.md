# Paper Agent

Paper Agent is a local-first paper discovery and research workspace. It combines
ResearchRabbit-style search and preview, arXiv + Semantic Scholar discovery,
Reading, Watch, Settings, and an executable Agent drawer for common research
tasks.

**Search / Recommendations / Preview / Reading / Watch / Settings / Agent**

No account is required. Durable workflow state lives in local SQLite, and AI is
optional through an OpenAI-compatible provider.

## Quick Start

```bash
python -m pip install -r requirements.txt -c constraints.txt
npm ci && npm run build
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

- **Home** — research-question-first workspace entry. Ask an open-ended topic and search starts from there.
- **Search** — paper, author, and topic discovery and triage workspace.
- **Recommendations** — a candidate-set workspace for profile, reading, and
  research-question recommendations with why-recommended context.
- **Preview** — selected-paper side panel with abstract, save, reading, watch,
  and detail actions.
- **Paper Detail** — full abstract, AI or rule-based analysis, evidence, notes,
  and related actions.
- **Reading** — lightweight local library for skim, deep-read, saved, archived,
  and collection workflows.
- **Watch** — long-term monitoring for research questions, authors, venues, and
  recent hits.
- **Settings** — OpenAI-compatible provider, source diagnostics, local profile,
  and runtime health.
- **Agent** — React drawer with Markdown rendering that can search, save, mark
  reading decisions, create watches, create collections, and summarize selected
  papers through local tools.

## Docs

- [PRD](docs/PRD.md) — Paper Agent product direction, workflows, gaps, and success criteria
- [Architecture](docs/ARCHITECTURE.md) — runtime architecture, data flow, and state policy
- [Agent Workflow](docs/AGENT_WORKFLOW.md) — reusable multi-agent product development workflow
- [Deployment](docs/DEPLOYMENT.md) — local, pip, and Docker deployment notes
- [Release Checklist](docs/RELEASE_CHECKLIST.md) — release verification checklist

## License

MIT
