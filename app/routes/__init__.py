"""Blueprint registration for page and API routes."""

from __future__ import annotations


def register_blueprints(flask_app):
    """Register route blueprints owned by the app package."""
    from app.routes.api import bp as api_bp
    from app.routes.inbox import bp as inbox_bp
    from app.routes.onboarding import bp as onboarding_bp
    from app.routes.queue import bp as queue_bp
    from app.routes.reading import bp as reading_bp
    from app.routes.watch import bp as watch_bp
    from app.routes.settings import bp as settings_bp

    for blueprint in (
        inbox_bp,
        reading_bp,
        watch_bp,
        queue_bp,
        settings_bp,
        api_bp,
        onboarding_bp,
    ):
        flask_app.register_blueprint(blueprint)

