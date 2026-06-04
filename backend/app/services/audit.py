"""Journal / audit-log writing. One row per write action by an admin."""
from sqlalchemy.orm import Session
from .. import models


def log_action(db: Session, username: str, action: str, detail: str = ""):
    """Add a Journal entry (flushed/committed with the endpoint's own commit).
    `action` is the category label (e.g. "Contrat"); `detail` is the specifics
    (e.g. "loyer 12000 → 13000 TND")."""
    db.add(models.AuditLog(username=username, method=action, path="", status=200, detail=detail))
