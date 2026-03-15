"""iDM heat pump API client. Fetches energy statistics via Nav20 cloud."""

import hashlib
import re
import requests


class IdmApi:
    def __init__(self, email: str, password: str, wp_id: str, token: str = None):
        self.email = email
        self.password = password
        self.wp_id = wp_id
        self.token = token
        self.session = requests.Session()
        self.csrf = None

    def _login_old_api(self) -> str:
        """Login to old myidm.at API and return auth token."""
        pwd_hash = hashlib.sha1(self.password.encode()).hexdigest()
        for base in ["https://myidm.at", "https://www.myidm.at"]:
            try:
                resp = self.session.post(
                    f"{base}/api/user/login",
                    json={"email": self.email, "password": pwd_hash},
                    timeout=15,
                )
                data = resp.json()
                token = data.get("token") or (data.get("data") or {}).get("token")
                if token:
                    return token
            except Exception:
                continue
        return None

    def _get_csrf(self):
        """Access Nav20 cloud page and extract CSRF token."""
        if not self.token:
            self.token = self._login_old_api()
        if not self.token:
            raise Exception("Cannot get iDM token — login failed and no cached token")

        resp = self.session.get(
            f"https://nav20.cloud.myidm.at/?token={self.token}&wp_ID={self.wp_id}&source=new-api",
            timeout=30,
        )
        resp.raise_for_status()
        match = re.search(r'csrf_token="([^"]+)"', resp.text)
        if not match:
            # Token may be expired, try re-login
            new_token = self._login_old_api()
            if new_token:
                self.token = new_token
                resp = self.session.get(
                    f"https://nav20.cloud.myidm.at/?token={self.token}&wp_ID={self.wp_id}&source=new-api",
                    timeout=30,
                )
                match = re.search(r'csrf_token="([^"]+)"', resp.text)
            if not match:
                raise Exception("Cannot extract CSRF token from Nav20")
        self.csrf = match.group(1)

    def _ensure_session(self):
        """Ensure we have a valid CSRF token."""
        if not self.csrf:
            self._get_csrf()

    def _get(self, path: str) -> dict:
        """Make authenticated GET request to Nav20 data endpoint."""
        self._ensure_session()
        resp = self.session.get(
            f"https://nav20.cloud.myidm.at/data/{path}",
            headers={"CSRF-Token": self.csrf},
            timeout=30,
        )
        if resp.status_code == 403:
            # CSRF expired, refresh
            self.csrf = None
            self._get_csrf()
            resp = self.session.get(
                f"https://nav20.cloud.myidm.at/data/{path}",
                headers={"CSRF-Token": self.csrf},
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json()

    def get_hp_energy_stats(self) -> dict:
        """Get heat pump energy consumption statistics (baenergyhp).

        Returns dict with 'daily', 'monthly', 'yearly' lists.
        Each entry has: name, sum (total kWh string), values [[heating, hotwater, defrost]].
        """
        return self._get("statistics.php?type=baenergyhp")

    def get_live_info(self) -> dict:
        """Get live system info including PV surplus."""
        return self._get("info.php")

    def get_today_hp_kwh(self) -> dict:
        """Get today's heat pump energy consumption breakdown.

        Returns dict with keys: total_kwh, heating_kwh, hotwater_kwh, defrost_kwh,
        pv_surplus_kw (live), hp_power_kw (live).
        """
        stats = self.get_hp_energy_stats()
        daily = stats.get("data", {}).get("daily", [])

        result = {
            "total_kwh": 0,
            "heating_kwh": 0,
            "hotwater_kwh": 0,
            "defrost_kwh": 0,
            "pv_surplus_kw": 0,
            "hp_power_kw": 0,
        }

        # First entry is today
        if daily:
            today = daily[0]
            vals = today.get("values", [[0, 0, 0]])[0]
            result["heating_kwh"] = round(vals[0], 2) if len(vals) > 0 else 0
            result["hotwater_kwh"] = round(vals[1], 2) if len(vals) > 1 else 0
            result["defrost_kwh"] = round(vals[2], 2) if len(vals) > 2 else 0
            result["total_kwh"] = round(sum(vals), 1)

        # Get live PV data
        try:
            info = self.get_live_info()
            pv = info.get("quickinfo", {}).get("pv", {})
            result["pv_surplus_kw"] = float(pv.get("act", 0))
            result["hp_power_kw"] = float(pv.get("hp", 0))
        except Exception:
            pass

        return result
