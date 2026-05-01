# Paper Recommender / Research Triage Desk

A local-first research triage desk that helps researchers decide which arXiv
papers matter today.

**Inbox / Queue / Library / Monitor / Settings**

## Quick Start

```bash
python -m pip install -r requirements.txt -c constraints.txt
cp user_profile.example.json user_profile.json
python web_server.py
```

Open http://localhost:5555.

## How It Works

- **Inbox** — today's paper triage with AI analysis and recommendation reasons.
- **Queue** — reading workflow: Skim Later, Deep Read, Saved, Archived.
- **Watch** — monitor authors, venues, and research questions over time.

No accounts. No cloud. All state lives in local SQLite.

## Docs

- [PRD](docs/PRD.md) — product definition, surfaces, principles, success criteria
- [Architecture](docs/ARCHITECTURE.md) — backend layering and state source policy
- [Agent Guide](docs/AGENTS.md) — agent roles, PR rules, and guardrails
- [Deployment](docs/DEPLOYMENT.md) — Docker and production notes

## License

MIT
