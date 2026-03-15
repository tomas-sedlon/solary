"""Daytime PV→HP collector. Run every 15 min from 6:00–21:00 via cron.

Samples the live PV surplus and HP power from iDM, accumulates daily
hp_solar_kwh (how much solar the heat pump used for free).
"""

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from idm_api import IdmApi
from database import init_db, save_hp_pv_sample

init_db()

idm = IdmApi(
    email=os.environ.get("IDM_EMAIL", ""),
    password=os.environ.get("IDM_PASSWORD", ""),
    wp_id=os.environ.get("IDM_WP_ID", ""),
    token=os.environ.get("IDM_TOKEN"),
)

info = idm.get_live_info()
pv = info.get("quickinfo", {}).get("pv", {})

pv_surplus_kw = float(pv.get("act", 0))
hp_power_kw = float(pv.get("hp", 0))

save_hp_pv_sample(pv_surplus_kw, hp_power_kw, interval_minutes=15)

print(f"PV sample: surplus={pv_surplus_kw} kW, HP from PV={hp_power_kw} kW "
      f"(+{hp_power_kw * 0.25:.3f} kWh)")
