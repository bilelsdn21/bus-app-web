"""
Local backup of the whole database to a timestamped JSON file.

Usage (from bus-app-web/backend):
    DATABASE_URL="<supabase session pooler uri>?sslmode=require" python backup_db.py
    # optional: BACKUP_DIR to override where files are written

Writes:  <project root>/backups/bus_db_backup_YYYYMMDD-HHMM.json
Restore with restore_db.py.
"""
import os
import json
import datetime
from pathlib import Path
from sqlalchemy import create_engine, text

# Every table, ordered parents -> children (so restore can insert in this order).
TABLES = ["config", "buses", "destinations", "contracts", "fuel_months", "bookings", "audit_log"]


def _ser(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    return str(o)


def main():
    url = os.environ.get("DATABASE_URL") or os.environ.get("DBURL")
    if not url:
        raise SystemExit("Set DATABASE_URL (the Supabase session pooler URI) first.")
    engine = create_engine(url, pool_pre_ping=True)

    out = {"taken_at": datetime.datetime.utcnow().isoformat() + "Z", "table_order": TABLES, "tables": {}}
    counts = {}
    with engine.connect() as c:
        for t in TABLES:
            rows = [dict(r._mapping) for r in c.execute(text(f'SELECT * FROM "{t}"'))]
            out["tables"][t] = rows
            counts[t] = len(rows)

    backup_dir = Path(os.environ.get("BACKUP_DIR") or (Path(__file__).resolve().parents[2] / "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    path = backup_dir / f"bus_db_backup_{stamp}.json"
    path.write_text(json.dumps(out, default=_ser, ensure_ascii=False, indent=1), encoding="utf-8")

    print("Backup written to:", path)
    for t in TABLES:
        print(f"  {t:14} {counts[t]} rows")
    print(f"  total {sum(counts.values())} rows")


if __name__ == "__main__":
    main()
