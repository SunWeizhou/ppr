# Security & Engineering Hardening

**Date:** 2026-04-27
**Status:** Approved
**Scope:** Fix 2 P1 security issues + 3 P2 engineering issues

## Fixes

### 1. XSS — HTML escape in `generate_relevance_html`
- **File:** `app/services/paper_utils.py`
- Import `html`, escape all user-data f-string interpolations in `generate_relevance_html` and `_render_structured_reason_html`
- Emoji icons and numeric `score_impact` not escaped (non-user-controlled)

### 2. CSRF — Origin/Referer check + GET→POST for refresh
- **File:** `web_server.py`, `app/routes/api/feedback.py`
- `before_request`: for POST/PUT/DELETE, check `Origin`/`Referer` matches `localhost:5555` or `127.0.0.1:5555`; also allow `None` Referer (browser direct nav to GET is safe, POST from `<form>` always sends Origin)
- `/api/refresh`: `@bp.get` → `@bp.post`; frontend JS updated accordingly

### 3. Concurrent pipeline guard
- **File:** `app/routes/api/feedback.py`
- Before creating new job, check for existing `running` `daily_recommendation` job
- Return 409 if one is already running

### 4. Force refresh bypasses seen cache
- **File:** `app/services/arxiv_source.py`
- Add `force_refresh` parameter to `fetch_all_sources`; when true, skip `is_seen` filter

### 5. defusedxml
- **Files:** `app/services/arxiv_source.py`, `requirements.txt`
- Replace `xml.etree.ElementTree` with `defusedxml.ElementTree`
- Add `defusedxml>=0.7.1` to requirements
