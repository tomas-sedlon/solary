"""GoodWe SEMS Portal API client."""

import json
import requests

BASE_URL = "https://www.semsportal.com/api/"
TOKEN_HEADER = {"version": "v3.1", "client": "web", "language": "en"}


class SemsApi:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.token = None
        self.uid = None
        self.timestamp = None
        self.api_url = BASE_URL
        self.station_id = None

    def _headers(self, authenticated=False):
        token_val = dict(TOKEN_HEADER)
        if authenticated and self.token:
            token_val.update({
                "token": self.token,
                "uid": self.uid,
                "timestamp": self.timestamp,
            })
        return {
            "Content-Type": "application/json",
            "token": json.dumps(token_val),
        }

    def login(self):
        """Authenticate and store session token."""
        url = self.api_url + "v2/Common/CrossLogin"
        payload = {"account": self.email, "pwd": self.password}
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("hasError"):
            raise Exception(f"SEMS login failed: {data.get('msg')}")

        info = data["data"]
        self.token = info["token"]
        self.uid = info["uid"]
        self.timestamp = info["timestamp"]
        # API URL can be in the top-level response or inside data
        api_url = data.get("api") or info.get("api")
        if api_url:
            self.api_url = api_url
            if not self.api_url.endswith("/"):
                self.api_url += "/"

    def _post(self, endpoint: str, payload: dict) -> dict:
        """Make an authenticated POST request, re-login if needed."""
        if not self.token:
            self.login()

        url = self.api_url + endpoint
        resp = requests.post(url, json=payload, headers=self._headers(authenticated=True), timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Token expired — re-login and retry once
        if str(data.get("code")) == "100001":
            self.login()
            resp = requests.post(url, json=payload, headers=self._headers(authenticated=True), timeout=30)
            resp.raise_for_status()
            data = resp.json()

        return data

    def get_station_list(self) -> list:
        """Get list of power stations for this account."""
        data = self._post("v2/HistoryData/QueryPowerStationByHistory", {})
        inner = data.get("data") or {}
        stations = inner.get("list", []) if isinstance(inner, dict) else []
        if stations and not self.station_id:
            self.station_id = stations[0].get("id")
        return stations

    def get_station_detail(self, station_id: str = None) -> dict:
        """Get detailed monitoring data for a power station."""
        sid = station_id or self.station_id
        if not sid:
            self.get_station_list()
            sid = self.station_id
        if not sid:
            raise Exception("No power station found")

        data = self._post(
            "v2/PowerStation/GetMonitorDetailByPowerstationId",
            {"powerStationId": sid},
        )
        return data.get("data", {})

    def get_graph_data(self, station_id: str = None, date: str = None) -> dict:
        """Get daily power output graph data. date format: YYYY-MM-DD."""
        sid = station_id or self.station_id
        if not sid:
            self.get_station_list()
            sid = self.station_id

        import datetime
        if not date:
            date = datetime.date.today().isoformat()

        data = self._post(
            "v2/PowerStationMonitor/GetPowerStationPowerAndIncomeByDay",
            {"id": sid, "date": date},
        )
        return data.get("data", {})
