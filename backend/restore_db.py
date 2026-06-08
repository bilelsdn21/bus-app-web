"""
Restore the database from a backup JSON made by backup_db.py.

⚠️  DESTRUCTIVE: this REPLACES all current data with the backup's contents.
It empties each table (children first) then re-inserts every row from the file.

Usage (from bus-app-web/backend):
    DATABASE_URL="<uri>?sslmode=require" python restore_db.py ../../backups/bus_db_backup_YYYYMMDD-HHMM.json
    # add  --yes  to skip the confirmation prompt
"""
import os
import sys
import json
import datetime
from sqlalchemy import create_engine, text


def _coerce(v):
    # turn ISO date/datetime strings back into proper types where they look like dates
    if isinstance(v, str) and len(v) >= 10 and v[4] == "-" and v[7] == "-":
        try:
            return datetime.datetime.fromisoformat(v) if "T" in v else datetime.date.fromisoformat(v)
        except ValueError:
            return v
    return v


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Pass the backup JSON path. See --help in the file header.")
    path = sys.argv[1]
    skip_confirm = "--yes" in sys.argv

    url = os.environ.get("DATABASE_URL") or os.environ.get("DBURL")
    if not url:
        raise SystemExit("Set DATABASE_URL (the Supabase session pooler URI) first.")

    data = json.loads(open(path, encoding="utf-8").read())
    order = data.get("table_order") or list(data["tables"].keys())
    print(f"Backup taken_at: {data.get('taken_at')}")
    for t in order:
        print(f"  {t:14} {len(data['tables'].get(t, []))} rows")

    if not skip_confirm:
        ans = input("\nThis REPLACES all current data with the above. Type 'RESTORE' to proceed: ")
        if ans.strip() != "RESTORE":
            raise SystemExit("Aborted.")

    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as c:
        # empty children first (reverse order), then refill parents -> children
        for t in reversed(order):
            c.execute(text(f'DELETE FROM "{t}"'))
        for t in order:
            rows = data["tables"].get(t, [])
            for row in rows:
                row = {k: _coerce(v) for k, v in row.items()}
                cols = ", ".join(f'"{k}"' for k in row)
                ph = ", ".join(f":{k}" for k in row)
                c.execute(text(f'INSERT INTO "{t}" ({cols}) VALUES ({ph})'), row)
        # reset identity sequences so new inserts don't collide
        for t in order:
            try:
                c.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('\"{t}\"', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM \"{t}\"), 1))"))
            except Exception:
                pass
    print("\nRestore complete.")


if __name__ == "__main__":
    main()
