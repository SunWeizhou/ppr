# Plan: Audit Fixes — 2026-05-01

**Goal**: Fix remaining issues from audit0501.md following priority order.

## Already Fixed (verified)
| # | Issue | Status |
|---|-------|--------|
| 1 | build_recommendation_reason | ✅ scoring_service.py:165 |
| 2 | trigger_source signature | ✅ state_store.py |
| 3 | recover_stale_jobs | ✅ state_store.py:575 |
| 14 | Embedding model mismatch | ✅ _resolve_default_model_name() |
| 23 | OpenAI fallback | ✅ returns fallback_analysis() |
| 25 | XSS escape | ✅ safe_err in inbox.py |

## Sub-tasks

### A. P0: Delete broken Windows venv
- **File**: `venv/` directory
- **Change**: `rm -rf venv/`
- **Risk**: None — user uses miniconda

### B. P1: ConfigManager thread safety (#5)
- **File**: `config_manager.py`
- **Change**: Add `threading.Lock` to `__new__`, remove redundant `_config_manager` global
- **Input**: ConfigManager._instance double-check locking
- **Risk**: Low — backward compatible

### C. P1: Skip redundant migration (#8)
- **File**: `state_store.py`
- **Change**: Track migration version in DB, skip if already migrated
- **Risk**: Medium — need to ensure first migration still works

### D. P2: API key warning (#7)
- **File**: `config_manager.py`
- **Change**: Add warning log if API key stored in plaintext config
- **Risk**: None

### E. P2: Replace pickle with json (#9)
- **File**: `app/services/daily_pipeline.py`
- **Change**: Use `json.loads/dumps` instead of `pickle`
- **Risk**: Medium — blob data must be JSON-serializable

### F. P2: Harden import_state (#10)
- **File**: `state_store.py`
- **Change**: Add row count validation, reject unreasonable payloads
- **Risk**: Low

### G. P2: Consolidate digest parsing (#11)
- **Files**: `utils.py`, `feedback_service.py`, `inbox_viewmodel.py`
- **Change**: Use single canonical parser in utils.py, others delegate to it
- **Risk**: Medium — subtle parsing differences need handling

## Not in scope
- #24 (inline HTML) — UI protected files
- #12-#22 (P3 code quality) — separate cleanup pass
- #26 (tests) — already working with conda
- #27 (subprocess compat) — low priority

## Rollback
- Revert individual commits via `git revert`
