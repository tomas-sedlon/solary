"""Explore SEMS API response for battery and consumption data."""

import json
import os

from dotenv import load_dotenv
from sems_api import SemsApi

load_dotenv()

api = SemsApi(os.environ["SEMS_EMAIL"], os.environ["SEMS_PASSWORD"])
api.login()
detail = api.get_station_detail()

# Check powerflow for consumption/battery
print("=== POWERFLOW ===")
print(json.dumps(detail.get("powerflow", {}), indent=2, default=str))

print("\n=== SOC (battery) ===")
print(json.dumps(detail.get("soc", {}), indent=2, default=str))

print("\n=== KPI ===")
print(json.dumps(detail.get("kpi", {}), indent=2, default=str))

print("\n=== ENERGE STATISTICS ===")
print(json.dumps(detail.get("energeStatisticsTotals", {}), indent=2, default=str))
print(json.dumps(detail.get("energeStatisticsCharts", {}), indent=2, default=str)[:1000])

print("\n=== INVERTER BATTERY FIELDS ===")
for inv in detail.get("inverter", []):
    print(f"Inverter: {inv.get('name')}")
    for k, v in inv.items():
        kl = k.lower()
        if any(x in kl for x in ["bat", "soc", "consum", "load", "buy", "grid", "import", "export"]):
            print(f"  {k}: {v}")

print("\n=== ALL TOP-LEVEL KEYS ===")
for k in detail.keys():
    val = detail[k]
    if isinstance(val, (dict, list)):
        size = len(val) if isinstance(val, list) else len(val.keys())
        print(f"  {k}: ({type(val).__name__}, {size} items)")
    else:
        print(f"  {k}: {val}")
