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
            hp_total_kwh REAL,
            hp_heating_kwh REAL,
            hp_hotwater_kwh REAL,
            hp_defrost_kwh REAL,
            hp_solar_kwh REAL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS hp_pv_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pv_surplus_kw REAL,
            hp_power_kw REAL
        );
        CREATE INDEX IF NOT EXISTS idx_hp_pv_ts ON hp_pv_samples(timestamp);
    """)
    # Migrate existing tables — add new columns if missing
    for col in ["hp_total_kwh", "hp_heating_kwh", "hp_hotwater_kwh", "hp_defrost_kwh", "hp_solar_kwh"]:
        try:
            conn.execute(f"SELECT {col} FROM daily_summary LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE daily_summary ADD COLUMN {col} REAL")
    conn.commit()
    conn.close()


def save_snapshot(current_power_w: float, today_kwh: float, total_kwh: float,
                   consumption_kwh: float = 0, buy_kwh: float = 0, sell_kwh: float = 0,
                   soc: float = None, hp_total_kwh: float = None, hp_heating_kwh: float = None,
                   hp_hotwater_kwh: float = None, hp_defrost_kwh: float = None,
                   raw_json: str = None):
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
            "UPDATE daily_summary SET total_kwh=?, peak_power_w=?, consumption_kwh=?, buy_kwh=?, sell_kwh=?, "
            "min_soc=?, hp_total_kwh=?, hp_heating_kwh=?, hp_hotwater_kwh=?, hp_defrost_kwh=?, updated_at=? WHERE date=?",
            (today_kwh, peak, consumption_kwh, buy_kwh, sell_kwh, min_soc,
             hp_total_kwh, hp_heating_kwh, hp_hotwater_kwh, hp_defrost_kwh, now, today),
        )
    else:
        conn.execute(
            "INSERT INTO daily_summary (date, total_kwh, peak_power_w, consumption_kwh, buy_kwh, sell_kwh, "
            "min_soc, hp_total_kwh, hp_heating_kwh, hp_hotwater_kwh, hp_defrost_kwh, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (today, today_kwh, current_power_w, consumption_kwh, buy_kwh, sell_kwh,
             soc, hp_total_kwh, hp_heating_kwh, hp_hotwater_kwh, hp_defrost_kwh, now),
        )
    conn.commit()
    conn.close()


def save_hp_pv_sample(pv_surplus_kw: float, hp_power_kw: float, interval_minutes: int = 15):
    """Save a PV→HP sample and accumulate into daily hp_solar_kwh."""
    conn = get_db()
    now = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT INTO hp_pv_samples (timestamp, pv_surplus_kw, hp_power_kw) VALUES (?, ?, ?)",
        (now, pv_surplus_kw, hp_power_kw),
    )
    # Accumulate: energy = power * time (in hours)
    energy_kwh = hp_power_kw * (interval_minutes / 60.0)
    today = datetime.date.today().isoformat()
    row = conn.execute("SELECT hp_solar_kwh FROM daily_summary WHERE date = ?", (today,)).fetchone()
    if row:
        current = row["hp_solar_kwh"] or 0
        conn.execute(
            "UPDATE daily_summary SET hp_solar_kwh = ?, updated_at = ? WHERE date = ?",
            (round(current + energy_kwh, 3), now, today),
        )
    else:
        conn.execute(
            "INSERT INTO daily_summary (date, hp_solar_kwh, updated_at) VALUES (?, ?, ?)",
            (today, round(energy_kwh, 3), now),
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
        "SELECT date, total_kwh, peak_power_w, consumption_kwh, buy_kwh, sell_kwh, min_soc, "
        "hp_total_kwh, hp_heating_kwh, hp_hotwater_kwh, hp_defrost_kwh, hp_solar_kwh "
        "FROM daily_summary WHERE date >= ? ORDER BY date",
        (since,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_summaries() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT substr(date, 1, 7) AS month, SUM(total_kwh) AS total_kwh, MAX(peak_power_w) AS peak_power_w, "
        "SUM(consumption_kwh) AS consumption_kwh, SUM(buy_kwh) AS buy_kwh, SUM(sell_kwh) AS sell_kwh, "
        "ROUND(AVG(min_soc), 1) AS min_soc, "
        "ROUND(SUM(hp_total_kwh), 1) AS hp_total_kwh, ROUND(SUM(hp_heating_kwh), 1) AS hp_heating_kwh, "
        "ROUND(SUM(hp_hotwater_kwh), 1) AS hp_hotwater_kwh, ROUND(SUM(hp_defrost_kwh), 1) AS hp_defrost_kwh, "
        "ROUND(SUM(hp_solar_kwh), 1) AS hp_solar_kwh, "
        "COUNT(*) AS days "
        "FROM daily_summary GROUP BY substr(date, 1, 7) ORDER BY month",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_days_in_month(month: str) -> list:
    """Get daily summaries for a given month (format: YYYY-MM)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, total_kwh, peak_power_w, consumption_kwh, buy_kwh, sell_kwh, min_soc, "
        "hp_total_kwh, hp_heating_kwh, hp_hotwater_kwh, hp_defrost_kwh, hp_solar_kwh "
        "FROM daily_summary WHERE date LIKE ? ORDER BY date",
        (month + "%",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
