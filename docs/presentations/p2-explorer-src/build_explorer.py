"""Build the P2 explorer page by running the real planner-service code.

Run from services/planner-service (the script imports the service and its test fakes, and needs its packages):
    uv run python ../../docs/presentations/p2-explorer-src/build_explorer.py \
        ../../docs/presentations/p2-explorer-src/explorer.template.html ../../docs/presentations/p2-explorer.html
Add `--json DATA.json` to also write the embedded data on its own, for inspection.

1. It runs the real planner app through FastAPI's TestClient, with the fake registry-service and weather-service
   from tests/conftest.py, for every request scenario and calculation case. tracer.py records every line of our
   own code that runs, with its local variables.
2. It checks the results against worked-examples.md and against what each scenario must do, and checks the
   teaching content in steps.py. Any problem stops the build, so the page can never show a number the engine did
   not produce, or point at code that is not there.
3. It pastes explorer.css and explorer.js (next to the template) and the data into the template: one offline HTML
   file with no external requests.

It calculates no irrigation number itself. The few explanation values that the engine computes inside an
expression without naming them (see `derived`) are checked against the engine's own result.
It never reads .env (it uses the test settings, as tests/conftest.py does) and writes only the output files.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

SERVICE = Path.cwd().resolve()
REPO = SERVICE.parent.parent
if SERVICE.name != "planner-service" or not (SERVICE / "engine.py").is_file():
    sys.exit("Run this from services/planner-service (see the docstring at the top of this file).")
sys.path.insert(0, str(SERVICE))  # the service is not an installed package: `import engine` needs its folder

import fastapi  # noqa: E402
import httpx2  # noqa: E402
import pydantic  # noqa: E402
import starlette  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import engine  # noqa: E402
from config import Settings  # noqa: E402
from main import app  # noqa: E402
from routers.plan import utc_today  # noqa: E402
from tests.conftest import EMITTER, PLOT_ID, SOIL, TEST_SETTINGS, TODAY, FakeService, forecast_body, plot_body  # noqa: E402
import steps  # noqa: E402  (this folder: the Hebrew teaching content)
from tracer import Recorder, show, show_fraction  # noqa: E402

# Like the autouse fixture in tests/conftest.py: the test settings, never the developer's .env.
Settings.model_config["env_file"] = None
os.environ.update(TEST_SETTINGS)

PLANNER = "services/planner-service/"
TRACED = ["main.py", "routers/plan.py", "upstream.py", "engine.py", "schemas.py"]  # our code; the rest runs untraced

# Files the page shows in its code panel. Only the planner files are traced; the others are for reading.
SOURCES = [PLANNER + name for name in TRACED + ["config.py", "tests/conftest.py", "tests/test_plan.py", "tests/test_engine.py"]] + [
    "services/weather-service/routers/forecast.py",
    "services/weather-service/cache.py",
    "services/weather-service/provider.py",
    "services/weather-service/main.py",
    "services/weather-service/tests/test_forecast.py",
    "services/registry-service/routers/plots.py",
    "services/registry-service/routers/catalogues.py",
    "services/registry-service/db.py",
    "services/frontend/src/lib/planner.ts",
    "services/frontend/src/lib/registry.ts",
    "services/frontend/src/lib/health.ts",
    "services/frontend/src/app/page.tsx",
    "services/frontend/src/app/plots/[id]/page.tsx",
    "services/frontend/src/components/plan-error.tsx",
    "services/frontend/src/components/stale-badge.tsx",
    "services/frontend/src/components/today-panel.tsx",
    ".claude/skills/irrigation-calc-reference/SKILL.md",
    ".claude/skills/irrigation-calc-reference/references/worked-examples.md",
    "docs/judgment-log.md",
    "services/planner-service/docs/research/fao56.md",
]
TEXT = {path: (REPO / path).read_text(encoding="utf-8") for path in SOURCES}

PROBLEMS: list[str] = []


def check(condition: bool, problem: str) -> None:
    """Collect every problem, then stop at the end with the whole list (like P1's check_debugger.js)."""
    if not condition:
        PROBLEMS.append(problem)


def line_of(path: str, needle: str) -> int:
    """The first line of a source file that contains `needle`. The page finds code by its text, not by a fixed
    line number, so a code change that moves a line still works and a change that removes it fails the build."""
    for number, line in enumerate(TEXT[path].splitlines(), 1):
        if needle in line:
            return number
    PROBLEMS.append(f"needle not found in {path}: {needle!r}")
    return 1


# --- The fakes: registry-service and weather-service, as in tests/conftest.py ---

PLOT_PATH = f"/v1/plots/{PLOT_ID}"
URL = f"{PLOT_PATH}/plan"
ALL_CALLS = ["plot", "soil", "emitter", "forecast"]


class RecordingService(FakeService):
    """The FakeService from tests/conftest.py, which also keeps what it answered, so the page can show it."""

    def __init__(self, name: str, routes: dict, calls: list) -> None:
        super().__init__(routes)
        self.name = name
        self.calls = calls  # shared by both services, so it keeps the real order of the calls

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        call = {"service": self.name, "name": call_name(request.url.path), "path": request.url.path, "query": dict(request.url.params)}
        self.calls.append(call)
        try:
            response = super().handler(request)
        except httpx2.HTTPError as exc:  # the fake stands for a service that is down or too slow
            call["error"] = f"{type(exc).__name__}: {exc}"
            raise
        call["status"] = response.status_code
        try:
            call["body"] = response.json()
        except ValueError:
            call["body"] = response.text
        return response


def call_name(path: str) -> str:
    # /v1/plots/<id> -> plot, /v1/soils/sand -> soil, /v1/emitters/<id> -> emitter, /v1/forecast -> forecast
    return {"plots": "plot", "soils": "soil", "emitters": "emitter", "forecast": "forecast"}[path.split("/")[2]]


def west_block(changes: dict | None = None) -> dict:
    """Registry answers for the seed plot West block (Case 3), with some answers replaced."""
    routes = {PLOT_PATH: plot_body(), "/v1/soils/sand": SOIL, "/v1/emitters/dripnet-pc-0.6": EMITTER}
    routes.update(changes or {})
    return routes


def example_plot(crop_id: str, planted: date, soil_mm_per_m: int, area_m2: float, flow_lph: float) -> dict:
    """Registry answers for a worked example's plot (B1, B2, B4), with its own soil and emitter."""
    return {
        PLOT_PATH: plot_body(crop_id=crop_id, planting_date=planted.isoformat(), area_m2=area_m2, soil_id="example-soil", emitter_id="example-emitter"),
        "/v1/soils/example-soil": {"id": "example-soil", "name": "Example soil", "available_water_mm_per_m": soil_mm_per_m},
        "/v1/emitters/example-emitter": {"id": "example-emitter", "name": "Example emitter", "flow_lph": flow_lph},
    }


def forecast(**changes):
    """weather-service's answer for the number of days asked, like the `weather` fixture in tests/conftest.py."""
    return lambda request: forecast_body(days=int(request.url.params["days"]), **changes)


def forecast_missing_et0(request: httpx2.Request) -> dict:
    body = forecast_body()
    body["days"][3]["et0_mm"] = None  # one missing value: the planner must answer 503, never treat it as 0
    return body


# --- Running a request through the real app ---


class LogCapture(logging.Handler):
    """Keeps the planner's warnings (e.g. "Upstream failure: ..."), so the page can show the terminal log."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(f"{record.levelname}: {record.getMessage()}")


class Planner:
    """The real planner app in a TestClient. Every request runs with fresh fakes and is traced on its own."""

    def __enter__(self) -> "Planner":
        self.recorder = Recorder({str(SERVICE / name): PLANNER + name for name in TRACED})
        self.logs = LogCapture()
        logging.getLogger("uvicorn.error").addHandler(self.logs)
        self.today = TODAY
        app.dependency_overrides[utc_today] = lambda: self.today  # the planner's UTC date, as the tests set it
        self.recorder.install()  # before TestClient starts its threads, so they are traced too
        self.client = TestClient(app).__enter__()  # runs the lifespan: settings and two httpx2 clients
        return self

    def __exit__(self, *exc_info) -> None:
        self.client.__exit__(*exc_info)
        self.recorder.uninstall()
        app.dependency_overrides.clear()
        logging.getLogger("uvicorn.error").removeHandler(self.logs)

    def get(self, url: str, registry: dict, weather, today: date = TODAY) -> dict:
        calls: list[dict] = []
        app.state.registry_client = RecordingService("registry-service", registry, calls).client()
        app.state.weather_client = RecordingService("weather-service", {"/v1/forecast": weather}, calls).client()
        self.today = today
        self.logs.lines = []
        self.recorder.reset()
        self.recorder.active = True
        try:
            response = self.client.get(url)
        finally:
            self.recorder.active = False
            app.state.registry_client.close()
            app.state.weather_client.close()
        return {
            "request": {"method": "GET", "url": url, "utc_today": today.isoformat()},
            "response": {"status": response.status_code, "body": response.json()},
            "calls": calls,
            "logs": self.logs.lines,
            "frames": self.recorder.frames,
            "events": self.recorder.events,
        }


def api_rows(run: dict) -> list[tuple]:
    """(kc, litres, run_minutes, bucket_level_mm) of every plan day, as the API answered them."""
    return [(d["kc"], d["litres"], d["run_minutes"], d["bucket_level_mm"]) for d in run["response"]["body"]["days"]]


# --- Expected values, copied from .claude/skills/irrigation-calc-reference/references/worked-examples.md ---
# Each row is (kc, litres, run_minutes, bucket_level_mm), as the API shows them.

CASE_3 = [(1.15, 0, 0, 51.2), (1.15, 0, 0, 44.3), (1.15, 0, 0, 43.55), (1.15, 0, 0, 36.65), (1.15, 0, 0, 29.75), (1.15, 36000, 1440, 47.425), (1.15, 0, 0, 40.525)]
B7 = [(1.15, 36000, 1440, 46.15), (1.15, 0, 0, 39.25), (1.15, 0, 0, 38.5), (1.15, 0, 0, 31.6), (1.15, 36000, 1440, 48.7), (1.15, 0, 0, 42.375), (1.15, 0, 0, 35.475)]
B1 = [(0.6, 0, 0, level) for level in (58.5, 54.0, 49.5, 45.0, 40.5, 36.0, 31.5)]
B2_DAY_7 = (0.6, 27004, 972, 58.499)  # days 1-6 do not irrigate
B4 = [(1.05, litres, minutes, level) for litres, minutes, level in zip((0, 0, 0, 0, 0, 9188, 0), (0, 0, 0, 0, 0, 662, 0), (37.825, 34.15, 30.475, 26.8, 23.125, 37.825, 34.15))]
START_EMPTY_DAY_1 = (1.15, 36000, 1440, 17.1)  # B7's note: initial_soil_water_pct=0
B5 = [("0.6225", 3, "0.623"), ("0.62249", 3, "0.622"), ("9187.5", 0, "9188"), ("9187.4999", 0, "9187"), ("661.5", 0, "662"), ("86.8775", 3, "86.878"), ("86.8774", 3, "86.877")]
# B6: (crop, planting date, the field's today, days, expected status)
B6 = [
    ("tomato", date(2026, 6, 1), date(2026, 11, 21), 7, 200),
    ("tomato", date(2026, 6, 1), date(2026, 11, 22), 7, 409),
    ("tomato", date(2026, 6, 1), date(2026, 11, 22), 6, 200),
    ("tomato", date(2026, 6, 1), date(2026, 11, 27), 1, 200),
    ("tomato", date(2026, 6, 1), date(2026, 11, 28), 1, 409),
    ("bell-pepper", date(2026, 12, 1), date(2026, 11, 30), 7, 409),
    ("bell-pepper", date(2026, 12, 1), date(2026, 12, 1), 7, 200),
]


# --- Request scenarios (the request-flow walkthrough) ---

SCENARIOS = [
    {"key": "plan", "url": URL, "status": 200, "calls": ALL_CALLS, "rows": CASE_3},
    {"key": "stale", "url": URL, "weather": forecast(stale=True), "status": 200, "calls": ALL_CALLS, "rows": CASE_3},
    {"key": "simulation", "url": URL + "?initial_soil_water_pct=50", "status": 200, "calls": ALL_CALLS, "rows": B7},
    {"key": "validation", "url": URL + "?days=8", "status": 422, "code": "VALIDATION", "calls": []},
    {"key": "not-found", "registry": west_block({PLOT_PATH: httpx2.Response(404, json={"detail": "Plot not found"})}),
     "status": 404, "code": "NOT_FOUND", "calls": ["plot"]},
    # The plot is on season day 300 of 180: out of season whatever the field's date, so no weather call.
    {"key": "out-of-season", "today": TODAY + timedelta(days=200), "status": 409, "code": "PLOT_OUT_OF_SEASON", "calls": ["plot"]},
    {"key": "registry-down", "registry": west_block({PLOT_PATH: httpx2.ConnectError("connection refused")}),
     "status": 503, "code": "UPSTREAM_UNAVAILABLE", "service": "registry-service", "calls": ["plot"]},
    {"key": "weather-down", "weather": httpx2.ConnectError("connection refused"),
     "status": 503, "code": "UPSTREAM_UNAVAILABLE", "service": "weather-service", "calls": ALL_CALLS},
    {"key": "weather-bad-field", "weather": forecast_missing_et0,
     "status": 503, "code": "UPSTREAM_UNAVAILABLE", "service": "weather-service", "calls": ALL_CALLS},
]


def run_scenarios(planner: Planner) -> list[dict]:
    results = []
    for s in SCENARIOS:
        run = planner.get(s.get("url", URL), s.get("registry", west_block()), s.get("weather", forecast()), s.get("today", TODAY))
        key, status, body = s["key"], run["response"]["status"], run["response"]["body"]
        check(status == s["status"], f"scenario {key}: status {status}, expected {s['status']}")
        called = [call["name"] for call in run["calls"]]
        check(called == s["calls"], f"scenario {key}: called {called}, expected {s['calls']}")
        if "code" in s:
            check(body.get("code") == s["code"], f"scenario {key}: code {body.get('code')}, expected {s['code']}")
        if "service" in s:
            check(s["service"] in body.get("detail", ""), f"scenario {key}: detail does not name {s['service']}")
        if "rows" in s:
            check(api_rows(run) == s["rows"], f"scenario {key}: plan differs from worked-examples.md")
            expected_stale = key == "stale"
            check(all(day["stale"] == expected_stale for day in body["days"]), f"scenario {key}: stale should be {expected_stale}")
        results.append({"key": key, **run})
    return results


# --- Calculation cases (the calculation explorer) ---

# Each line of one plan day in engine.plan_days, found by its text, and the variable it sets.
ENGINE = PLANNER + "engine.py"
LOOP = [
    ("kc", "kc = kc_on(crop, plot.planting_date, day.date)"),
    ("start", "start = min(previous_end + day.rain_mm, taw)"),
    ("etc", "etc = etc_mm(kc, day.et0_mm)"),
    ("desired_mm", "desired_mm = taw - start if start - etc < threshold else Fraction(0)"),
    ("applied_l", "applied_l = min(desired_mm * plot.area_m2, daily_cap_l)"),
    ("applied_mm", "applied_mm = applied_l / plot.area_m2"),
    ("end", "end = max(start + applied_mm - etc, Fraction(0))"),
]
LOOP_LINES = {name: line_of(ENGINE, needle) for name, needle in LOOP}
SETUP_LINES = {
    "taw": line_of(ENGINE, "taw = plot.available_water_mm_per_m * crop.root_depth_m"),
    "threshold": line_of(ENGINE, "threshold = taw / 2"),
    "flow": line_of(ENGINE, "flow = system_flow_lph("),
    "daily_cap_l": line_of(ENGINE, "daily_cap_l = flow * DAILY_CAP_HOURS"),
    "previous_end": line_of(ENGINE, "previous_end = taw * initial_fraction"),
    "emitters": line_of(ENGINE, "emitters = area_m2 / (row_spacing_m * emitter_spacing_m)"),
    "run_minutes": line_of(ENGINE, "return litres / system_flow * 60"),
}


def one_frame(run: dict, function: str) -> int:
    numbers = [n for n, f in enumerate(run["frames"]) if f["file"] == ENGINE and f["function"] == function]
    check(len(numbers) == 1, f"expected one call of {function}, got {len(numbers)}")
    return numbers[0] if numbers else -1


def states_after_each_line(run: dict, frame: int) -> list[tuple[int, dict]]:
    """For each line the frame ran: (line, the frame's locals right after that line ran).

    A "line" event comes before its line runs, so the values a line sets are visible at the frame's next event.
    """
    events = [e for e in run["events"] if e["frame"] == frame]
    state: dict = {}
    states = []
    for e in events:
        state = {**state, **e["raw"]}
        states.append(state)
    return [(e["line"], states[i + 1]) for i, e in enumerate(events[:-1]) if e["event"] == "line"]


def return_values(run: dict, function: str) -> list:
    """What each call of an engine function returned, in call order."""
    frames = {n for n, f in enumerate(run["frames"]) if f["file"] == ENGINE and f["function"] == function}
    return [e["raw_return"] for e in run["events"] if e["frame"] in frames and e["event"] == "return"]


def engine_view(run: dict) -> dict:
    """What the calculation explorer shows, read from the trace of plan_days and its helpers."""
    after = states_after_each_line(run, one_frame(run, "plan_days"))
    first_day_start = next(i for i, (line, _) in enumerate(after) if line == LOOP_LINES["kc"])
    setup_state = after[first_day_start - 1][1]  # every set-up value, just before day 1 begins
    emitters = states_after_each_line(run, one_frame(run, "system_flow_lph"))[0][1]["emitters"]
    run_minutes = return_values(run, "run_minutes_for")
    plot = setup_state["plot"]

    days = []
    for (line, state) in after:
        if line == LOOP_LINES["kc"]:
            days.append({"lines": {}, "raw": {}})
        if days and line in LOOP_LINES.values():
            name = next(n for n, number in LOOP_LINES.items() if number == line)
            days[-1]["lines"][name] = line
            days[-1]["raw"][name] = state[name]
            days[-1]["raw"]["day"] = state["day"]

    out_days = []
    for n, day in enumerate(days):
        v = day["raw"]
        for name, value in v.items():
            if name != "day":
                check(type(value) is Fraction, f"day {n + 1}: {name} is {type(value).__name__}, not a Fraction")
        # Explanation values: the engine computes them inside an expression without naming them.
        without_irrigation = v["start"] - v["etc"]
        desired_l = v["desired_mm"] * plot.area_m2
        check((v["desired_mm"] != 0) == (without_irrigation < setup_state["threshold"] and v["start"] != setup_state["taw"]),
              f"day {n + 1}: the irrigation decision does not match start - etc < threshold")
        check(v["applied_l"] == min(desired_l, setup_state["daily_cap_l"]), f"day {n + 1}: applied_l is not min(desired, cap)")
        out_days.append({
            "date": v["day"].date.isoformat(),
            "et0_mm": show(v["day"].et0_mm),
            "rain_mm": show(v["day"].rain_mm),
            "values": {name: show(v[name]) for name, _ in LOOP} | {"run_minutes": show(run_minutes[n])},
            "derived": {"without_irrigation_mm": show(without_irrigation), "desired_l": show(desired_l),
                        "capped": desired_l > setup_state["daily_cap_l"]},
            "lines": day["lines"],
        })
    setup = {name: show(setup_state[name]) for name in ("taw", "threshold", "flow", "daily_cap_l", "previous_end")}
    setup["emitters"] = show(emitters)
    return {"setup": setup, "setup_lines": SETUP_LINES, "days": out_days}


CALC_CASES = [
    *[{"key": f"case3-start-{pct}", "source": "Case 3" if pct == 100 else ("B7" if pct == 50 else "Case 3, simulated start"),
       "url": f"{URL}?initial_soil_water_pct={pct}"} for pct in range(0, 101, 10)],
    {"key": "b1", "source": "B1", "today": date(2026, 11, 20), "registry": example_plot("tomato", date(2026, 11, 1), 90, 1000.0, 1.0),
     "weather": forecast(first_day=date(2026, 11, 20), et0=[7.5] * 7, rain=[0.0] * 7)},
    {"key": "b2", "source": "B2", "today": date(2026, 11, 20), "registry": example_plot("tomato", date(2026, 11, 1), 90, 1000.0, 1.0),
     "weather": forecast(first_day=date(2026, 11, 20), et0=[7.501] * 7, rain=[0.0] * 7)},
    {"key": "b4", "source": "B4", "today": date(2026, 11, 20), "registry": example_plot("bell-pepper", date(2026, 8, 1), 83, 500.0, 1.0),
     "weather": forecast(first_day=date(2026, 11, 20), et0=[3.5] * 7, rain=[0.0] * 7)},
]


def run_calc_cases(planner: Planner) -> list[dict]:
    results = []
    for c in CALC_CASES:
        run = planner.get(c.get("url", URL), c.get("registry", west_block()), c.get("weather", forecast()), c.get("today", TODAY))
        key = c["key"]
        check(run["response"]["status"] == 200, f"case {key}: status {run['response']['status']}")
        if run["response"]["status"] != 200:
            continue
        rows = api_rows(run)
        expected = {"case3-start-100": CASE_3, "case3-start-50": B7, "b1": B1, "b4": B4}.get(key)
        if expected:
            check(rows == expected, f"case {key}: plan differs from worked-examples.md: {rows}")
        if key == "case3-start-0":
            check(rows[0] == START_EMPTY_DAY_1, f"case {key}: day 1 is {rows[0]}, expected {START_EMPTY_DAY_1}")
        if key == "b2":
            check([r[1] for r in rows[:6]] == [0] * 6 and rows[6] == B2_DAY_7, f"case b2: {rows}")
        results.append({"key": key, "source": c["source"], "request": run["request"], "inputs": run["calls"],
                        "plan": run["response"]["body"], **engine_view(run)})
    return results


def run_season_rows(planner: Planner) -> list[dict]:
    """B6 through the real API: which plans are 409, and whether weather-service was asked first."""
    rows = []
    for crop_id, planted, today, days, expected in B6:
        registry = west_block({PLOT_PATH: plot_body(crop_id=crop_id, planting_date=planted.isoformat())})
        run = planner.get(f"{URL}?days={days}", registry, forecast(first_day=today), today)
        status = run["response"]["status"]
        check(status == expected, f"B6 {crop_id} {today} days={days}: status {status}, expected {expected}")
        first = engine.day_number(planted, today)
        rows.append({"crop_id": crop_id, "planting_date": planted.isoformat(), "today": today.isoformat(), "days": days,
                     "first_day": first, "last_day": first + days - 1, "status": status,
                     "weather_called": any(call["name"] == "forecast" for call in run["calls"])})
    return rows


# --- Engine functions called directly (no request needed) ---


def direct_examples() -> dict:
    tomato, pepper = engine.CROPS["tomato"], engine.CROPS["bell-pepper"]
    F = Fraction

    # Case 1: one day of a mid-season tomato's ETc as litres and run time (test_case_1_... does the same).
    kc = engine.kc_on(tomato, date(2026, 6, 1), date(2026, 6, 1) + timedelta(days=99))  # day 100
    etc = engine.etc_mm(kc, F("6.0"))
    flow = engine.system_flow_lph(F("1000"), F("1.5"), F("0.4"), F("1.0"))
    litres = etc * F("1000")  # 1 mm over 1 m² is 1 L
    minutes = engine.run_minutes_for(litres, flow)
    check((kc, etc, litres, engine.round_half_up(minutes, 0)) == (F("1.15"), F("6.9"), 6900, 248), "Case 1 differs")
    case_1 = {"kc": show(kc), "etc_mm": show(etc), "flow_lph": show(flow), "litres": show(litres),
              "run_minutes": show(minutes), "run_minutes_api": int(engine.round_half_up(minutes, 0))}

    # Case 2 and B3: Kc in pepper's development stage.
    kc_2 = engine.kc_on(pepper, date(2026, 10, 1), date(2026, 11, 19))
    kc_b3 = engine.kc_on(pepper, date(2026, 10, 1), date(2026, 11, 1))
    check(kc_2 == F("0.825") and engine.etc_mm(kc_2, F("3.0")) == F("2.475"), "Case 2 differs")
    check(kc_b3 == F("0.6225") and engine.round_half_up(kc_b3, 3) == F("0.623"), "B3 differs")
    kc_examples = [
        {"source": "Case 2", "day": engine.day_number(date(2026, 10, 1), date(2026, 11, 19)), "kc": show(kc_2),
         "kc_api": float(engine.round_half_up(kc_2, 3)), "etc_mm_at_et0_3": show(engine.etc_mm(kc_2, F("3.0")))},
        {"source": "B3", "day": engine.day_number(date(2026, 10, 1), date(2026, 11, 1)), "kc": show(kc_b3),
         "kc_api": float(engine.round_half_up(kc_b3, 3))},
    ]

    rounding = []
    for value, places, expected in B5:
        result = engine.round_half_up(F(value), places)
        check(result == F(expected), f"B5 {value} -> {result}, expected {expected}")
        rounding.append({"value": value, "places": places, "result": show_fraction(result)})

    # Kc on every day of each crop's season, from kc_on itself: the data for the Kc curve.
    curves = {}
    for crop_id, crop in engine.CROPS.items():
        planted = date(2026, 1, 1)  # any date: Kc depends only on the season day
        curves[crop_id] = {
            "stages": {"ini": crop.l_ini, "dev": crop.l_dev, "mid": crop.l_mid, "late": crop.l_late},
            "kc_ini": show(crop.kc_ini), "kc_mid": show(crop.kc_mid), "kc_end": show(crop.kc_end),
            "root_depth_m": show(crop.root_depth_m),
            "kc_by_day": [show(engine.kc_on(crop, planted, planted + timedelta(days=i))) for i in range(crop.season_length)],
        }
    return {"case_1": case_1, "kc_examples": kc_examples, "rounding": rounding, "kc_curves": curves}


# --- Output ---


def git(*args: str) -> str | None:
    """A read-only git command in the repository, or None when the sources are not a git checkout (an export)."""
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def for_page(run: dict) -> dict:
    """A run without the real Python objects the checks used; those can't be JSON and the page doesn't need them."""
    events = [{k: v for k, v in e.items() if not k.startswith("raw")} for e in run.get("events", [])]
    return {**run, "events": events} if "events" in run else run


def stop_if_problems() -> None:
    if PROBLEMS:
        print("\n".join(PROBLEMS))
        sys.exit(f"{len(PROBLEMS)} problem(s): nothing written")


# --- The teaching content (steps.py) ---

TERM = re.compile(r"\[\[([a-z0-9-]+)(?:\|([^\]]+))?\]\]")


def with_terms(text: str, where: str) -> str:
    """Turn [[key]] and [[key|shown text]] into the page's glossary markup, and check the text (rules from P1)."""
    def replace(match: re.Match) -> str:
        key, shown = match.group(1), match.group(2)
        check(key in steps.GLOSSARY, f"{where}: unknown glossary term [[{key}]]")
        label = shown or steps.GLOSSARY.get(key, {}).get("term", key)
        return f'<span class="term" data-term="{key}" tabindex="0" role="button">{label}</span>'

    check(text.count("<code>") == text.count("</code>"), f"{where}: unbalanced <code>")
    check(not re.search(r"undefined|\$\{|TODO|TBD", text), f"{where}: placeholder text")
    return TERM.sub(replace, text)


def code_ref(ref: list, where: str) -> dict:
    """A (file, needle[, what]) reference from steps.py, resolved to its line now, so the page can open it."""
    path, needle = ref[0], ref[1]
    check(path in TEXT, f"{where}: {path} is not one of the embedded SOURCES")
    line = line_of(path, needle) if path in TEXT else 1
    return {"file": path, "line": line, "label": ref[2] if len(ref) > 2 else needle}


def decision_path(run: dict) -> dict:
    """Which decision nodes this request reached, and where it ended, read from its real trace.

    A node counts as reached when its function ran (steps.DECISIONS `function`); "input" is always reached.
    A request that did not end with 200 ended at the last node it reached, with its status code.
    """
    ran = {frame["function"] for frame in run["frames"]}
    nodes = [d["id"] for d in steps.DECISIONS if d["function"] is None or d["function"] in ran]
    status = run["response"]["status"]
    return {"nodes": nodes, "outcome": "success" if status == 200 else f"{nodes[-1]}:{status}"}


def frame_state(run: dict, frame: int, upto: int) -> dict:
    """The frame's local variables (as shown on the page) at event `upto`: every change up to and including it."""
    state: dict = {}
    for e in run["events"][: upto + 1]:
        if e["frame"] == frame:
            state.update(e["changed"])
    return state


def resolve_step(run: dict, key: str) -> dict:
    """One walkthrough step: the authored text from steps.py, plus what really happened at its anchor in this run."""
    step, where = steps.STEPS[key], f"walkthrough {run['key']}/{key}"
    out = {"key": key, "lane": step["lane"], "to": step.get("to"), "kind": step.get("kind", ""), "title": step["title"],
           "badges": step.get("badges", []), "unobserved": step.get("unobserved")}
    for field in ("goal", "what", "why"):
        out[field] = with_terms(step[field], where)
    observed: dict = {}
    if "at" in step:
        path, function, needle = step["at"]
        line = line_of(path, needle)
        index = next((i for i, e in enumerate(run["events"]) if e["event"] == "line" and e["line"] == line
                      and run["frames"][e["frame"]]["file"] == path and run["frames"][e["frame"]]["function"] == function), None)
        check(index is not None, f"{where}: line {line} of {function} never ran in this scenario")
        if index is not None:
            out["event"] = index
            state = frame_state(run, run["events"][index]["frame"], index)
            for name in step.get("show", []):
                check(name in state, f"{where}: {name} is not a local variable of {function} there")
            observed["vars"] = {name: state.get(name, "") for name in step.get("show", [])}
        out["code"] = {"file": path, "line": line, "label": function}
    if "code" in step:
        out["code"] = code_ref(step["code"], where)
    returns = {}
    for function in step.get("returns", []):
        frames = {n for n, f in enumerate(run["frames"]) if f["function"] == function}
        detail = next((e["detail"] for e in run["events"] if e["frame"] in frames and e["event"] == "return"), None)
        check(detail is not None, f"{where}: {function} never returned in this scenario")
        returns[function] = detail
    if returns:
        observed["returns"] = returns
    if "calls" in step:
        calls = [c for c in run["calls"] if c["name"] in step["calls"]]
        check(sorted({c["name"] for c in calls}) == sorted(step["calls"]), f"{where}: expected calls {step['calls']}")
        observed["calls"] = calls
    if step.get("response"):
        observed["response"] = run["response"]
    if step.get("logs"):
        observed["logs"] = run["logs"]
    if step.get("response_request"):
        observed["request"] = run["request"]
    if "test" in step:
        out["test"] = code_ref(step["test"], where)
    out["observed"] = observed
    return out


def learning_content(scenarios: list[dict]) -> dict:
    """steps.py, checked against the traces, the views and the source files, with glossary markup applied."""
    by_key = {s["key"]: s for s in scenarios}
    check(set(steps.SCENARIO_LABELS) == set(by_key), "steps.SCENARIO_LABELS must name every traced scenario")

    # The decision flow: what each outcome claims must be what the real runs did.
    claimed = {}
    for d in steps.DECISIONS:
        for fail in d["fails"]:
            for key in fail["scenarios"]:
                claimed[key] = f"{d['id']}:{fail['status']}"
    for key in steps.SUCCESS["scenarios"]:
        claimed[key] = "success"
    check(set(claimed) == set(by_key), f"every scenario must end at exactly one outcome: {sorted(set(by_key) ^ set(claimed))}")
    check(set(steps.WALKTHROUGH) == set(by_key), "steps.WALKTHROUGH must cover every traced scenario")
    used = {key for keys in steps.WALKTHROUGH.values() for key in keys}
    check(used <= set(steps.STEPS), f"unknown walkthrough steps: {sorted(used - set(steps.STEPS))}")
    check(set(steps.STEPS) <= used, f"walkthrough steps never used: {sorted(set(steps.STEPS) - used)}")
    for s in scenarios:
        s["walkthrough"] = [resolve_step(s, key) for key in steps.WALKTHROUGH.get(s["key"], []) if key in steps.STEPS]
        s["decision_path"] = decision_path(s)
        check(claimed.get(s["key"]) == s["decision_path"]["outcome"],
              f"decision flow: scenario {s['key']} really ends at {s['decision_path']['outcome']}, steps.py says {claimed.get(s['key'])}")

    def node(d: dict, where: str) -> dict:
        out = {k: v for k, v in d.items() if k not in ("code", "test", "text", "fails")}
        out["text"] = with_terms(d["text"], where)
        if "code" in d:
            out["code"] = code_ref(d["code"], where)
        if "test" in d:
            out["test"] = code_ref(d["test"], where)
        if "fails" in d:
            out["fails"] = [{**f, "test": code_ref(f["test"], where)} for f in d["fails"]]
        return out

    services = {}
    for key, s in steps.SERVICES.items():
        where = f"service {key}"
        services[key] = {**s, **{field: with_terms(s[field], where) for field in ("role", "not")},
                         "inputs": [with_terms(x, where) for x in s["inputs"]],
                         "outputs": [with_terms(x, where) for x in s["outputs"]],
                         "code": [code_ref(ref, where) for ref in s["code"]]}
        if s["example"]:
            check(s["example"]["scenario"] in by_key, f"{where}: unknown example scenario")
    for a, b, _ in steps.MAP_EDGES:
        check(a in steps.SERVICES and b in steps.SERVICES, f"map edge {a} -> {b}: unknown service")

    for path_key, path in steps.PATHS.items():
        for n, stop in enumerate(path["stops"], 1):
            where = f"path {path_key} stop {n}"
            check(stop["view"] in steps.VIEWS, f"{where}: unknown view {stop['view']}")
            built = "stage" not in stop
            if built:
                check(steps.VIEWS[stop["view"]]["stage"] <= steps.CURRENT_STAGE, f"{where}: its view is not built yet; give the stop a stage")
            else:
                check(stop["stage"] > steps.CURRENT_STAGE, f"{where}: stage {stop['stage']} is already built; remove it")
            check(stop.get("service") in (None, *steps.SERVICES), f"{where}: unknown service")
            if "step" in stop:
                check(stop["step"] in steps.WALKTHROUGH.get(stop.get("scenario"), []), f"{where}: step {stop['step']} is not in its scenario")
            if "scenario" not in stop:
                continue
            run = by_key.get(stop["scenario"])
            check(run is not None, f"{where}: unknown scenario {stop['scenario']}")
            target = stop.get("at")
            if run and target:  # the function must really run in that scenario
                found = any(f["file"] == target["file"] and f["function"] == target["function"] for f in run["frames"])
                check(found, f"{where}: {target['function']} does not run in scenario {stop['scenario']}")
    return {
        "current_stage": steps.CURRENT_STAGE,
        "intro": with_terms(steps.WALKTHROUGH_INTRO, "walkthrough intro"),
        "lanes": steps.LANES,
        "services": services,
        "map_edges": steps.MAP_EDGES,
        "decisions": [node(d, f"decision {d['id']}") for d in steps.DECISIONS],
        "success": node(steps.SUCCESS, "success"),
        "frontend": {**steps.FRONTEND_OUTCOME, "text": with_terms(steps.FRONTEND_OUTCOME["text"], "frontend"),
                     "code": [code_ref(ref, "frontend") for ref in steps.FRONTEND_OUTCOME["code"]]},
        "weather_flow": [node(w, f"weather step {n}") for n, w in enumerate(steps.WEATHER_FLOW, 1)],
        "spec_url": steps.SPEC_URL,
        "sources": {k: {**v, "text": with_terms(v["text"], f"source {k}")} for k, v in steps.SOURCES.items()},
        "values": {k: {**v, "text": with_terms(v["text"], f"value {k}")} for k, v in steps.VALUES.items()},
        "glossary": {k: {**v, "text": with_terms(v["text"], f"term {k}")} for k, v in steps.GLOSSARY.items()},
        "views": steps.VIEWS,
        "scenario_labels": steps.SCENARIO_LABELS,
        "paths": steps.PATHS,
        # Lines of each judgment-log entry ("## JL-014: ..."), so a badge can open the decision itself.
        "jl_lines": {m.group(1): TEXT["docs/judgment-log.md"].count("\n", 0, m.start()) + 1
                     for m in re.finditer(r"^## (JL-\d+)", TEXT["docs/judgment-log.md"], re.M)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the P2 explorer page (see the docstring).")
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--json", type=Path, help="also write the embedded data here")
    args = parser.parse_args()
    template = args.template.read_text(encoding="utf-8")
    css = (args.template.parent / "explorer.css").read_text(encoding="utf-8")
    js = (args.template.parent / "explorer.js").read_text(encoding="utf-8")
    for marker in ("__DATA_JSON__", "/*__CSS__*/", "/*__JS__*/"):
        check(template.count(marker) == 1, f"the template must contain {marker} exactly once")
    check("</style" not in css and "</script" not in js, "explorer.css/js must not close their own <style>/<script>")
    check(not re.search(r"https?://", template + css + js), "the page must not load anything from the network")
    stop_if_problems()  # a needle that no longer matches the code: reading the trace would make no sense

    with Planner() as planner:
        scenarios = run_scenarios(planner)
        cases = run_calc_cases(planner)
        season = run_season_rows(planner)
    direct = direct_examples()
    learning = learning_content(scenarios)
    stop_if_problems()

    data = {
        "meta": {
            "commit": git("rev-parse", "--short", "HEAD"),
            # Changes to tracked files only: the page embeds tracked files, so a new untracked file doesn't matter.
            "uncommitted_changes": None if (status := git("status", "--porcelain", "--untracked-files=no")) is None else bool(status),
            "versions": f"FastAPI {fastapi.__version__} · Starlette {starlette.__version__} · Pydantic {pydantic.VERSION}"
                        f" · httpx2 {httpx2.__version__} · Python {sys.version.split()[0]}",
        },
        "sources": TEXT,
        "scenarios": [for_page(s) for s in scenarios],
        "cases": cases,
        "season": season,
        **direct,
        "learning": learning,
    }
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    # "</" would end the <script> element early, so escape it inside the JSON (as P1's build_debugger.py does).
    # Plain str.replace, never re.sub: the CSS, JS and JSON contain backslashes that must stay as they are.
    page = template.replace("/*__CSS__*/", css).replace("/*__JS__*/", js).replace("__DATA_JSON__", text.replace("</", "<\\/"))
    args.output.write_text(page, encoding="utf-8")

    print("scenarios (status, upstream calls, traced events):")
    for s in scenarios:
        print(f"  {s['key']:<18} {s['response']['status']}  {' → '.join(c['name'] for c in s['calls']) or '(none)':<34} {len(s['events'])}")
    print("calculation cases (bucket at the end of each day; irrigation days):")
    for c in cases:
        ends = " ".join(day["values"]["end"] for day in c["days"])
        irrigation = [f"day {n + 1}: {d['values']['applied_l']} L" for n, d in enumerate(c["days"]) if d["values"]["applied_l"] != "0"]
        print(f"  {c['key']:<17} {ends}  {'; '.join(irrigation) or 'none'}")
    print(f"B6 season rows: {len(season)} · B5 rounding rows: {len(direct['rounding'])} · Kc curves: tomato, bell-pepper")
    print(f"commit {data['meta']['commit'] or 'unknown (not a git checkout)'}{' + uncommitted changes' if data['meta']['uncommitted_changes'] else ''}")
    print(f"wrote {args.output} ({len(page):,} characters) · all checks passed")


if __name__ == "__main__":
    main()
