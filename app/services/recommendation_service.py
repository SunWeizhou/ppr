"""Recommendation orchestration service boundary."""

from __future__ import annotations


class RecommendationService:
    def daily_page(self, date=None, *, auto_generate: bool = True):
        import web_server

        return web_server.generate_page(date=date, auto_generate=auto_generate)

    def status(self):
        import web_server

        return web_server.get_status()

    def export_state(self):
        import web_server

        return web_server._build_state_snapshot()

    def import_state(self, snapshot):
        import web_server

        return web_server.STATE_STORE.import_state(snapshot)

