"""One-time backfill: import historical iDM heat pump energy data into daily_summary."""

import os
import re
import datetime

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from idm_api import IdmApi
from database import init_db, get_db

init_db()

idm = IdmApi(
    email=os.environ.get("IDM_EMAIL", ""),
    password=os.environ.get("IDM_PASSWORD", ""),
    wp_id=os.environ.get("IDM_WP_ID", ""),
    token=os.environ.get("IDM_TOKEN"),
)

stats = idm.get_hp_energy_stats()
daily = stats.get("data", {}).get("daily", [])

conn = get_db()
updated = 0
inserted = 0

for entry in daily:
    # name is like "15.03" (DD.MM) — need to figure out the year
    name = entry.get("name", "")
    match = re.match(r"(\d{2})\.(\d{2})", name)
    if not match:
        continue
    day, month = int(match.group(1)), int(match.group(2))
    # Determine year: if month > current month, it's last year
    now = datetime.date.today()
    year = now.year
    try:
        date = datetime.date(year, month, day)
        if date > now:
            date = datetime.date(year - 1, month, day)
    except ValueError:
        continue

    date_str = date.isoformat()
    vals = entry.get("values", [[0, 0, 0]])[0]
    hp_heating = round(vals[0], 2) if len(vals) > 0 else 0
    hp_hotwater = round(vals[1], 2) if len(vals) > 1 else 0
    hp_defrost = round(vals[2], 2) if len(vals) > 2 else 0
    hp_total = round(sum(vals), 1)

    row = conn.execute("SELECT * FROM daily_summary WHERE date = ?", (date_str,)).fetchone()
    if row:
        conn.execute(
            "UPDATE daily_summary SET hp_total_kwh=?, hp_heating_kwh=?, hp_hotwater_kwh=?, hp_defrost_kwh=? WHERE date=?",
            (hp_total, hp_heating, hp_hotwater, hp_defrost, date_str),
        )
        updated += 1
    else:
        conn.execute(
            "INSERT INTO daily_summary (date, hp_total_kwh, hp_heating_kwh, hp_hotwater_kwh, hp_defrost_kwh, updated_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (date_str, hp_total, hp_heating, hp_hotwater, hp_defrost),
        )
        inserted += 1
    print(f"  {date_str}: {hp_total} kWh (heating {hp_heating}, hw {hp_hotwater}, defrost {hp_defrost})")

conn.commit()
conn.close()
print(f"\nDone: {updated} updated, {inserted} inserted")
