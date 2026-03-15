"""Daily solar production collector. Run via cron at end of day."""

import json
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sems_api import SemsApi
from idm_api import IdmApi
from database import init_db, save_snapshot

init_db()

# --- SEMS (solar) ---
api = SemsApi(os.environ["SEMS_EMAIL"], os.environ["SEMS_PASSWORD"])
detail = api.get_station_detail()

kpi = detail.get("kpi", {})
charts = detail.get("energeStatisticsCharts", {})
powerflow = detail.get("powerflow", {})

current_power = float(kpi.get("pac", 0))
today_kwh = float(kpi.get("power", 0))
total_kwh = float(kpi.get("total_power", 0))
consumption_kwh = float(charts.get("consumptionOfLoad", 0))
buy_kwh = float(charts.get("buy", 0))
sell_kwh = float(charts.get("sell", 0))
soc = float(powerflow.get("soc", 0))

# --- iDM (heat pump) ---
hp_total_kwh = None
hp_heating_kwh = None
hp_hotwater_kwh = None
hp_defrost_kwh = None

try:
    idm = IdmApi(
        email=os.environ.get("IDM_EMAIL", ""),
        password=os.environ.get("IDM_PASSWORD", ""),
        wp_id=os.environ.get("IDM_WP_ID", ""),
        token=os.environ.get("IDM_TOKEN"),
    )
    hp = idm.get_today_hp_kwh()
    hp_total_kwh = hp["total_kwh"]
    hp_heating_kwh = hp["heating_kwh"]
    hp_hotwater_kwh = hp["hotwater_kwh"]
    hp_defrost_kwh = hp["defrost_kwh"]
    print(f"Heat pump: {hp_total_kwh} kWh total "
          f"(heating {hp_heating_kwh}, hot water {hp_hotwater_kwh}, defrost {hp_defrost_kwh})")
except Exception as e:
    print(f"Warning: Could not fetch iDM data: {e}")

save_snapshot(
    current_power, today_kwh, total_kwh,
    consumption_kwh=consumption_kwh,
    buy_kwh=buy_kwh,
    sell_kwh=sell_kwh,
    soc=soc,
    hp_total_kwh=hp_total_kwh,
    hp_heating_kwh=hp_heating_kwh,
    hp_hotwater_kwh=hp_hotwater_kwh,
    hp_defrost_kwh=hp_defrost_kwh,
    raw_json=json.dumps(detail),
)

print(f"Saved: {today_kwh} kWh produced, {consumption_kwh} kWh consumed, "
      f"bought {buy_kwh} kWh, sold {sell_kwh} kWh, battery {soc}%")
