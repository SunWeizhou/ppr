"""Settings page routes."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.viewmodels.settings_viewmodel import SettingsViewModel
from state_store import get_state_store

bp = Blueprint("settings", __name__)


@bp.get("/settings")
def settings_page():
    store = get_state_store()
    vm = SettingsViewModel(store)
    return render_template(
        "settings_research.html",
        **vm.to_template_context(tab=request.args.get("tab", "profile")),
    )
