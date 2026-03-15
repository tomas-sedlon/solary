"""SQLite database for storing solar production history."""

import sqlite3
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "solary.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            current_power_w REAL,
            today_kwh REAL,
            total_kwh REAL,
            raw_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(timestamp);

        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            total_kwh REAL,
            peak_power_w REAL,
            consumption_kwh REAL,
            buy_kwh REAL,
            sell_kwh REAL,
            min_soc REAL,
            updated_at TEXT
        );
    """)
    conn.commit()
    conn.close()


def save_snapshot(current_power_w: float, today_kwh: float, total_kwh: float,
                   consumption_kwh: float = 0, buy_kwh: float = 0, sell_kwh: float = 0,
                   soc: float = None, raw_json: str = None):
    conn = get_db()
    now = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT INTO snapshots (timestamp, current_power_w, today_kwh, total_kwh, raw_json) VALUES (?, ?, ?, ?, ?)",
        (now, current_power_w, today_kwh, total_kwh, raw_json),
    )

    today = datetime.date.today().isoformat()
    row = conn.execute("SELECT * FROM daily_summary WHERE date = ?", (today,)).fetchone()
    if row:
        peak = max(row["peak_power_w"] or 0, current_power_w or 0)
        min_soc = min(row["min_soc"], soc) if row["min_soc"] is not None and soc is not None else (soc or row["min_soc"])
        conn.execute(
            "UPDATE daily_summary SET total_kwh = ?, peak_power_w = ?, consumption_kwh = ?, buy_kwh = ?, sell_kwh = ?, min_soc = ?, updated_at = ? WHERE date = ?",
            (today_kwh, peak, consumption_kwh, buy_kwh, sell_kwh, min_soc, now, today),
        )
    else:
        conn.execute(
            "INSERT INTO daily_summary (date, total_kwh, peak_power_w, consumption_kwh, buy_kwh, sell_kwh, min_soc, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (today, today_kwh, current_power_w, consumption_kwh, buy_kwh, sell_kwh, soc, now),
        )
    conn.commit()
    conn.close()


def get_recent_snapshots(hours: int = 24) -> list:
    conn = get_db()
    since = (datetime.datetime.now() - datetime.timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT timestamp, current_power_w, today_kwh, total_kwh FROM snapshots WHERE timestamp >= ? ORDER BY timestamp",
        (since,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_summaries(days: int = 30) -> list:
    conn = get_db()
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT date, total_kwh, peak_power_w, consumption_kwh, buy_kwh, sell_kwh, min_soc FROM daily_summary WHERE date >= ? ORDER BY date",
        (since,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_summaries() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT substr(date, 1, 7) AS month, SUM(total_kwh) AS total_kwh, MAX(peak_power_w) AS peak_power_w, "
        "SUM(consumption_kwh) AS consumption_kwh, SUM(buy_kwh) AS buy_kwh, SUM(sell_kwh) AS sell_kwh, "
        "ROUND(AVG(min_soc), 1) AS min_soc, COUNT(*) AS days "
        "FROM daily_summary GROUP BY substr(date, 1, 7) ORDER BY month",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_days_in_month(month: str) -> list:
    """Get daily summaries for a given month (format: YYYY-MM)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, total_kwh, peak_power_w, consumption_kwh, buy_kwh, sell_kwh, min_soc FROM daily_summary WHERE date LIKE ? ORDER BY date",
        (month + "%",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
