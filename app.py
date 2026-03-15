"""Solary — Solar production tracking dashboard. Serves stored data."""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

from flask import request
from database import init_db, get_recent_snapshots, get_daily_summaries, get_monthly_summaries, get_days_in_month

load_dotenv()

app = Flask(__name__)


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/current")
def api_current():
    summaries = get_daily_summaries(days=1)
    if not summaries:
        return jsonify({})
    latest = summaries[-1]
    return jsonify({
        "current_power_w": latest.get("peak_power_w", 0),
        "today_kwh": latest.get("total_kwh", 0),
        "total_kwh": latest.get("total_kwh", 0),
        "consumption_kwh": latest.get("consumption_kwh", 0),
        "buy_kwh": latest.get("buy_kwh", 0),
        "sell_kwh": latest.get("sell_kwh", 0),
        "min_soc": latest.get("min_soc"),
        "station_name": os.environ.get("STATION_NAME", "My Solar"),
    })


@app.route("/api/today")
def api_today():
    snapshots = get_recent_snapshots(hours=24)
    return jsonify(snapshots)


@app.route("/api/history")
def api_history():
    summaries = get_daily_summaries(days=30)
    return jsonify(summaries)


@app.route("/api/monthly")
def api_monthly():
    return jsonify(get_monthly_summaries())


@app.route("/api/month/<month>")
def api_month_detail(month):
    return jsonify(get_days_in_month(month))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5555, debug=False)
