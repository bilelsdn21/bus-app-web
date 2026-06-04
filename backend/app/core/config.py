"""
App-wide configuration read from the environment, plus shared constants.
Infrastructure layer — no business logic here.
"""
import os

# Categories that mean the bus is UNAVAILABLE (maintenance / rest / free),
# i.e. not a paid booking. Shared by the excursion + day-save logic.
UNAVAIL_CATS = {"Entretien", "Libre", "Repos Chauffeur"}


def cors_origins() -> list[str]:
    """Allowed CORS origins. Local dev by default; in production set
    CORS_ORIGINS="https://your-app.vercel.app" (comma-separated for several).
    Trailing slashes are stripped; any *.vercel.app URL is also allowed via the
    regex in main.py, so CORS "just works" for preview deployments too."""
    default = "http://localhost:5173,http://127.0.0.1:5173"
    raw = os.environ.get("CORS_ORIGINS", default)
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
