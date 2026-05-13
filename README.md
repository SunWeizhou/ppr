# Paper Agent

*Your research-question-driven AI literature workspace.*

Paper Agent is a local-first research companion for graduate students and PhD
researchers. It helps you move from a research question to a living literature
workspace — discover candidate papers, judge what matters through preview + AI
analysis, record reading progress with takeaways, and grow a Research Memo over
time — all without requiring an account.

Built with Flask + Jinja2 + SQLite + Preact, wrapped in an Apple/Claude-inspired
warm, minimalist design system.

**Home / Workspaces / Search / Recommendations / Reading / Watch / Agent / Settings**

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Build the Agent frontend panel
npm install && npm run build

# 3. Start the server
python web_server.py
```

Open http://localhost:5555. The onboarding wizard will guide you through your
first setup. All configuration can be changed later in Settings.

> AI analysis is optional. The core workflow works without any API key.
> Configure an OpenAI-compatible provider (DeepSeek, OpenAI, etc.) in Settings
> when you're ready.

## Pages

- **Home** (`/`) — Research Desk: quick-start bar, active workspace cards, today's papers
- **Workspaces** (`/workspaces/<id>`) — dedicated overview per Research Question: stats, memory, suggestions, recent papers, Research Memo, Weekly Review
- **Search** (`/search`) — workspace-aware paper discovery across arXiv, Semantic Scholar, and OpenAlex with split-panel preview
- **Recommendations** (`/recommendations`) — profile and research-context candidate set with why-recommended explanations
- **Paper Detail** (`/papers/<id>`) — full abstract, AI or rule-based analysis, evidence claims, and actions
- **Reading** (`/reading`) — unified reading list with To Read / Completed / Collections tabs and workspace filter
- **Watch** (`/watch`) — long-term monitoring for journals, conferences, scholars, and research fields with saved query searches
- **Settings** (`/settings`) — profile, sources, ranking, AI provider, and diagnostics
- **Entity Profiles** (`/entities/<id>`) — browsable pages for journals, conferences, scholars, and fields
- **Agent Panel** — Preact-based side drawer with Markdown rendering, persistent sessions, and multi-step tool execution

## Design

The UI follows an Apple/Claude-inspired design system: warm paper background
(`#FAF9F5`), terracotta accent (`#C96442`), Source Serif 4 for display text, and
Inter for body text. Card-based layout with generous whitespace, collapsible
sidebar navigation, and light/dark mode toggle.

Design tokens are defined in `static/css/tokens.css` and consumed across all
templates. The Apple/Claude-specific components live in `static/css/apple-claude.css`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask (Python 3.13+) |
| Data | SQLite via `state_store.py` (protocol-based repository pattern) |
| Templates | Jinja2 with block inheritance |
| Frontend Styling | CSS custom properties (design tokens) |
| Agent Panel | Preact (built with Vite) |
| Paper Sources | arXiv API, Semantic Scholar API, OpenAlex API |
| AI (optional) | OpenAI-compatible providers (DeepSeek, OpenAI, etc.) |

## Testing

```bash
python -m pytest tests/ -q
```

Individual test files can be run with pytest:

```bash
python -m pytest tests/test_repository_hygiene.py -v
```

## Docs

- [PRD](docs/PRD.md) — Product direction, workflows, and success criteria
- [Architecture](docs/ARCHITECTURE.md) — Runtime architecture, data flow, and state policy
- [Agent Workflow](docs/AGENT_WORKFLOW.md) — Multi-agent product development workflow
- [Deployment](docs/DEPLOYMENT.md) — Local, pip, and Docker deployment notes
- [Release Checklist](docs/RELEASE_CHECKLIST.md) — Release verification checklist

## License

MIT
