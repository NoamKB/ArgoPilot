"""The explorer's Hebrew teaching content, as plain Python data. build_explorer.py checks it and embeds it.

Markup inside texts:
- <code>...</code> for code and identifiers (shown left-to-right inside the Hebrew text).
- [[key]] or [[key|shown text]] for a glossary term: the page underlines it and opens its definition.

Only write what the code, tests, spec or judgment log say. A stop whose content does not exist yet is marked with
the increment that builds it (`stage`), and the page says so instead of showing an invented explanation.
"""

SPEC_URL = "https://github.com/alonitac/OzVeruach26/blob/main/tasks/p2.md"

# Where a statement comes from. The page shows one badge per source next to a formula, rule or decision.
SOURCES = {
    "p2": {"label": "דרישה רשמית P2", "text": "כתוב במפרט המטלה (tasks/p2.md). חובה, לא בחירה שלנו."},
    "fao": {"label": "FAO-56", "text": "נוסחה או ערך מהמדריך FAO Irrigation and Drainage Paper 56, לפי סיכום המחקר ב-fao56.md."},
    "project": {"label": "החלטה שלנו", "text": "הנחה או פישוט שבחרנו בעצמנו, עם החלופות והמחיר שלה ביומן ההחלטות (JL)."},
    "units": {"label": "חשבון יחידות", "text": "נובע מהיחידות עצמן, למשל: 1 מ\"מ מים על 1 מ\"ר הוא ליטר אחד."},
}

# Where a number on the page comes from.
VALUES = {
    "authored": {"label": "הסבר שכתבנו", "text": "טקסט שכתבנו כדי להסביר את הצעד, על סמך הקוד, הבדיקות והמפרט. הוא לא נמדד: "
                                              "מה שנמדד בריצה מוצג לידו, בנפרד."},
    "traced": {"label": "נמדד בריצה", "text": "הערך נלקח מהרצה אמיתית של הקוד בזמן בניית הדף, כמו בדיבאגר."},
    "derived": {"label": "ערך הסבר", "text": "חושב בזמן הבנייה מערכים שנמדדו, רק כדי להסביר צעד שהמנוע מחשב בתוך ביטוי בלי לתת לו שם. "
                                         "הבנייה בודקת שהוא מתאים לתוצאה של המנוע."},
}

GLOSSARY = {
    "trace": {"term": "מעקב (trace)", "text": "רשימת השורות שרצו בפועל, לפי הסדר, עם ערכי המשתנים. "
              "היא נאספת בזמן בניית הדף, מהרצה של הקוד האמיתי עם registry ו-weather מדומים."},
    "fake": {"term": "שירות מדומה", "text": "במקום רשת אמיתית, <code>httpx2.MockTransport</code> קורא לפונקציה שלנו שמחזירה תשובה מוכנה. "
             "אלה אותם שירותים מדומים שהבדיקות משתמשות בהם (<code>tests/conftest.py</code>)."},
    "endpoint": {"term": "endpoint", "text": "הפונקציה שמטפלת בכתובת HTTP אחת. כאן <code>GET /v1/plots/{plot_id}/plan</code> מגיע ל-<code>get_plan</code>."},
    "worker": {"term": "worker thread", "text": "FastAPI מריץ endpoint שמוגדר ב-<code>def</code> רגיל (לא <code>async</code>) בתהליכון נפרד, "
               "כדי שהמתנה לקריאת HTTP לא תעצור את שאר השרת."},
    "loop": {"term": "event loop", "text": "הלולאה שמריצה את הקוד שמוגדר ב-<code>async def</code>. "
             "כאן אלה ה-[[handler|exception handlers]] שב-<code>main.py</code>."},
    "handler": {"term": "exception handler", "text": "פונקציה ב-<code>main.py</code> שהופכת חריגה לתשובת HTTP עם <code>code</code> ו-<code>detail</code>. "
                "למשל <code>UpstreamUnavailable</code> הופכת ל-503."},
    "exception": {"term": "חריגה (exception)", "text": "דרך של פייתון לעצור פונקציה באמצע ולדווח על בעיה. החריגה עולה מפונקציה לפונקציה "
                  "שקראה לה, עד שמישהו תופס אותה."},
    "callstack": {"term": "מחסנית קריאות", "text": "הפונקציות שפתוחות כרגע: למעלה זו שרצה עכשיו, ומתחתיה מי שקרא לה. "
                  "כאן מוצגות רק הפונקציות שלנו; FastAPI וספריות אחרות לא נכנסות למעקב."},
    "fraction": {"term": "Fraction", "text": "<code>fractions.Fraction</code> שומר מספר כמונה חלקי מכנה, בדיוק מלא, בלי שגיאת העיגול של float. "
                 "המנוע מחשב רק איתו (JL-019)."},
    "et0": {"term": "ET0", "text": "כמה מים (במ\"מ ליום) מאבד שטח דשא סטנדרטי לשמש ולרוח. המספר מגיע מ-weather-service."},
    "kc": {"term": "Kc", "text": "מקדם הגידול: מכפיל את ET0 לפי סוג הגידול ושלב הגדילה שלו באותו יום."},
    "etc": {"term": "ETc", "text": "צריכת המים של הגידול באותו יום, במ\"מ: <code>ETc = Kc × ET0</code>."},
    "taw": {"term": "TAW", "text": "גודל ה\"דלי\" של הקרקע: כמה מים (במ\"מ) אזור השורשים מחזיק. "
            "<code>TAW = available_water_mm_per_m × Zr</code>."},
    "threshold": {"term": "סף (threshold)", "text": "חצי מ-TAW. אם הדלי היה יורד מתחתיו עד סוף היום, משקים באותו יום."},
    "stale": {"term": "stale", "text": "תחזית ישנה מהזיכרון של weather-service, כש-Open-Meteo לא עונה. "
              "התוכנית עדיין נבנית, וכל יום בה מסומן <code>stale: true</code>."},
    "validation": {"term": "בדיקת קלט (validation)", "text": "FastAPI קורא את הטיפוסים והמגבלות בחתימה של ה-endpoint, למשל "
                   "<code>Query(ge=1, le=7)</code>, ובודק כל פרמטר לפני שהפונקציה רצה. ערך לא תקין יוצר "
                   "<code>RequestValidationError</code>, וה-planner הופך אותה ל-422."},
    "dependency": {"term": "dependency", "text": "<code>Depends(...)</code>: פונקציה ש-FastAPI מריץ לפני ה-endpoint, ומעביר את התוצאה שלה כפרמטר. "
                   "כאן <code>utc_today</code> נותנת את התאריך, והבדיקות מחליפות אותה בתאריך קבוע."},
    "lifespan": {"term": "lifespan", "text": "קוד ב-<code>main.py</code> שרץ פעם אחת כשהשרת עולה: קורא את ההגדרות מ-<code>.env</code> "
                 "ופותח שני לקוחות HTTP, אחד ל-registry ואחד ל-weather."},
    "timeout": {"term": "timeout", "text": "כמה זמן לחכות לתשובה לפני שמוותרים: ל-registry 3 שניות ול-weather 12 (ב-<code>.env</code>). "
                "תשובה שלא הגיעה בזמן היא <code>httpx2.ReadTimeout</code>, וה-planner עונה 503."},
    "upstream": {"term": "upstream", "text": "שירות שה-planner תלוי בו: registry-service או weather-service. "
                 "אם אחד מהם לא זמין, התשובה היא 503 <code>UPSTREAM_UNAVAILABLE</code>, ולעולם לא תוכנית של אפסים."},
}

# The increment that is built now. A view or stop with a later `stage` says so on the page instead of inventing content.
CURRENT_STAGE = 4

VIEWS = {
    "map": {"label": "ארכיטקטורה", "stage": 3},
    "flow": {"label": "זרימת בקשה", "stage": 4},
    "calc": {"label": "חישוב ההשקיה", "stage": 5},
    "sources": {"label": "מקורות ומושגים", "stage": 2},
}

# Short Hebrew names for the traced request scenarios (build_explorer.py SCENARIOS), as "what if ...?".
SCENARIO_LABELS = {
    "plan": "הכול עובד",
    "stale": "התחזית ישנה",
    "simulation": "סימולציה: דלי חצי מלא",
    "validation": "days=8",
    "not-found": "חלקה לא קיימת",
    "out-of-season": "מחוץ לעונה",
    "registry-down": "registry לא זמין",
    "weather-down": "weather לא זמין",
    "weather-bad-field": "חסר ערך בתחזית",
}

# Learning paths. A stop opens a view: on "map" a panel ("system" or "decisions"), optionally a service or a
# scenario whose path is lit; on "flow" a scenario at the first line of a function (raw trace, explorer mode).
# A stop with `stage` is built by that later increment.
PATHS = {
    "A": {
        "label": "ארכיטקטורה",
        "stops": [
            {"title": "מפת המערכת: מי מדבר עם מי", "view": "map", "panel": "system"},
            {"title": "planner-service במרכז: מה הוא מקבל ומה הוא מחזיר", "view": "map", "panel": "system", "service": "planner"},
            {"title": "זרימת ההחלטות: מתי שגיאה ומתי תוכנית", "view": "map", "panel": "decisions"},
            {"title": "registry לא זמין: המסלול ל-503", "view": "map", "panel": "decisions", "scenario": "registry-down"},
            {"title": "ערך חסר בתחזית: 503, לעולם לא אפס", "view": "map", "panel": "decisions", "scenario": "weather-bad-field"},
            {"title": "בקשה אחת מקצה לקצה, צעד אחר צעד", "view": "flow", "scenario": "plan"},
            {"title": "registry לא זמין: מחריגה ל-503 ולהודעה למשתמש", "view": "flow", "scenario": "registry-down", "step": "front_err"},
        ],
    },
    "B": {
        "label": "שירות מזג האוויר",
        "stops": [
            {"title": "תא רשת של 0.1° ומטמון בזיכרון", "view": "map", "stage": 6},
            {"title": "ניסיון ועוד שני ניסיונות חוזרים", "view": "map", "stage": 6},
            {"title": "תחזית stale, או 503", "view": "map", "stage": 6},
        ],
    },
    "C": {
        "label": "מתכנן וחישובים",
        "stops": [
            {"title": "המנוע מתחיל: plan_days", "view": "flow", "scenario": "plan", "step": "engine"},
            {"title": "הקלטים ומאיפה הם מגיעים", "view": "calc", "stage": 5},
            {"title": "Kc ושלבי הגדילה", "view": "calc", "stage": 5},
            {"title": "ETc: כמה הגידול שותה היום", "view": "calc", "stage": 5},
            {"title": "TAW והסף: גודל הדלי וחציו", "view": "calc", "stage": 5},
            {"title": "יום אחד בדלי, חמישה צעדים", "view": "calc", "stage": 5},
            {"title": "שבעה ימים, והתקרה של 24 שעות", "view": "calc", "stage": 5},
            {"title": "עיגול בסוף בלבד, ולמה Fraction", "view": "calc", "stage": 5},
            {"title": "מה המודל לא יודע", "view": "calc", "stage": 5},
        ],
    },
}

# --- The system map (Increment 3) ---
# Code references are (file, needle, what it is): build_explorer.py finds the needle's line and fails if it is gone.
# `example` names real data from a traced scenario; services that don't run during the build say so instead.
PLANNER = "services/planner-service/"
WEATHER = "services/weather-service/"
REGISTRY = "services/registry-service/"
FRONTEND = "services/frontend/src/"

SERVICES = {
    "browser": {
        "name": "Browser", "title": "הדפדפן", "port": "",
        "short": "מציג את הדפים. לא פונה לשום שירות בעצמו.",
        "role": "הגולש פותח את <code>/</code> (כל החוות והחלקות) או <code>/plots/{id}</code> (התוכנית של חלקה). "
                "הדפדפן מקבל מ-Next.js דף HTML מוכן.",
        "not": "לא מכיר את כתובות השירותים ולא פונה אליהם. כל הקריאות לשירותים קורות בשרת של Next.js.",
        "inputs": ["מה שהגולש לוחץ: רשימת החוות, או חלקה אחת"],
        "outputs": ["בקשת דף ל-Next.js, למשל <code>GET /plots/{id}</code>"],
        "code": [],
        "badges": [["p2", "FR-2.15"], ["p2", "FR-2.16"]],
        "example": None,
    },
    "next": {
        "name": "Next.js", "title": "האתר (frontend)", "port": ":3000",
        "short": "בונה כל דף בשרת, מתוך registry ו-planner.",
        "role": "שרת Next.js בונה כל דף לפני שהוא נשלח לדפדפן. דף הבית מבקש מ-registry את החוות ואת החלקות. "
                "דף החלקה מבקש מ-planner את התוכנית ומציג קודם את ההמלצה להיום. שורת הסטטוס שואלת את "
                "<code>/health</code> של שלושת השירותים.",
        "not": "לא מחשב שום מספר של השקיה: הוא מציג את מה ש-planner החזיר. כל הקריאות לשירותים נמצאות ב-<code>src/lib/</code>.",
        "inputs": ["בקשת דף מהדפדפן", "כתובות השירותים מ-<code>.env.local</code>: <code>REGISTRY_URL</code>, <code>WEATHER_URL</code>, <code>PLANNER_URL</code>"],
        "outputs": ["HTML לדפדפן", "כשה-planner עונה בשגיאה: הודעה שאומרת מה קרה, למשל איזה שירות לא זמין"],
        "code": [
            [FRONTEND + "lib/planner.ts", "export async function getPlan(", "getPlan: הבקשה ל-planner, וטיפול בשגיאה שלו"],
            [FRONTEND + "lib/registry.ts", "export async function getFarmsWithPlots(", "getFarmsWithPlots: החוות והחלקות מ-registry"],
            [FRONTEND + "lib/health.ts", "export async function getServiceStatus(", "getServiceStatus: שורת הסטטוס"],
            [FRONTEND + "app/plots/[id]/page.tsx", "getPlan(id, pct)", "דף החלקה: התוכנית והחלקה במקביל"],
            [FRONTEND + "components/plan-error.tsx", "export function PlanError(", "PlanError: הודעת השגיאה למשתמש"],
        ],
        "badges": [["p2", "FR-2.16"], ["p2", "FR-2.18"], ["p2", "FR-2.19"]],
        "example": None,
        "no_example": "לא נמדד: הקוד של ה-frontend לא רץ בזמן בניית הדף.",
    },
    "planner": {
        "name": "planner-service", "title": "המתכנן", "port": ":8002",
        "short": "מחבר חלקה ותחזית לתוכנית של 1–7 ימים.",
        "role": "מקבל <code>GET /v1/plots/{id}/plan?days=</code>. מבקש מ-registry את החלקה, הקרקע והטפטפת, ומ-weather את "
                "התחזית לנקודה של החלקה, ומעביר הכול ל-מנוע החישוב (<code>engine.py</code>). בסוף מעגל את התוצאה לתשובה.",
        "not": "אין לו מסד נתונים, והוא לא מכיר את Open-Meteo. כשחסר לו ערך הוא עונה בשגיאה, לעולם לא באפס.",
        "inputs": ["<code>plot_id</code>, <code>days</code> (1–7), ואופציונלית <code>initial_soil_water_pct</code> (0–100)",
                   "התשובות של registry ושל weather"],
        "outputs": ["תוכנית: לכל יום <code>kc</code>, <code>litres</code>, <code>run_minutes</code>, <code>bucket_level_mm</code>, <code>stale</code>",
                    "או שגיאה: 422, 404, 409 או 503, עם <code>code</code> ו-<code>detail</code>"],
        "code": [
            [PLANNER + "routers/plan.py", "def get_plan(", "get_plan: ה-endpoint, וסדר הצעדים"],
            [PLANNER + "upstream.py", "def get_plot(", "get_plot: החלקה מ-registry, בבדיקה קפדנית"],
            [PLANNER + "upstream.py", "def get_forecast(", "get_forecast: התחזית מ-weather"],
            [PLANNER + "main.py", "@app.exception_handler(UpstreamUnavailable)", "הפיכת חריגה ל-503"],
            [PLANNER + "config.py", "class Settings(BaseSettings):", "Settings: הכתובות וזמני ההמתנה מ-.env"],
        ],
        "badges": [["p2", "FR-2.9"], ["p2", "FR-2.12"], ["p2", "FR-2.14"]],
        "example": {"scenario": "plan", "kind": "request"},
    },
    "engine": {
        "name": "engine.py", "title": "מנוע החישוב", "port": "",
        "short": "כל המספרים בתוכנית",
        "role": "פונקציה טהורה: מקבלת את נתוני החלקה והתחזית, ומחזירה את התוכנית יום אחר יום לפי הנוסחאות שב-"
                "<code>irrigation-calc-reference</code>. מחשבת רק עם [[fraction]].",
        "not": "לא שולח בקשות HTTP ולא מעגל. העיגול קורה ב-<code>routers/plan.py</code>, רק לתשובה.",
        "inputs": ["<code>PlotInputs</code>: גידול, תאריך שתילה, מים זמינים בקרקע, שטח, מרווחים, ספיקת טפטפת",
                   "רשימת <code>WeatherDay</code>: ET0 וגשם לכל יום", "<code>initial_fraction</code>: כמה מלא הדלי הבוקר"],
        "outputs": ["<code>PlanResult</code>: TAW, הסף, ולכל יום Kc, ליטרים, דקות ומפלס הדלי, בלי עיגול"],
        "code": [
            [PLANNER + "engine.py", "def plan_days(", "plan_days: הדלי, יום אחר יום"],
            [PLANNER + "engine.py", "def kc_on(", "kc_on: Kc לפי יום בעונה"],
            [PLANNER + "engine.py", "def check_season(", "check_season: הבדיקה הסופית של העונה"],
            [PLANNER + "engine.py", "def round_half_up(", "round_half_up: העיגול לתשובה"],
        ],
        "badges": [["p2", "FR-2.11"], ["project", "JL-019"]],
        "example": {"scenario": "plan", "kind": "frame", "function": "plan_days"},
    },
    "registry": {
        "name": "registry-service", "title": "המרשם", "port": ":8000",
        "short": "חוות, חלקות, וקטלוג של גידולים, קרקעות וטפטפות.",
        "role": "שירות ה-API מ-P1. ה-planner מבקש ממנו שלושה דברים: את החלקה (<code>/v1/plots/{id}</code>), את הקרקע שלה "
                "(<code>/v1/soils/{id}</code>) ואת הטפטפת שלה (<code>/v1/emitters/{id}</code>). ה-frontend מבקש ממנו את החוות והחלקות.",
        "not": "לא יודע דבר על מזג אוויר או על תוכניות השקיה.",
        "inputs": ["בקשות GET מ-planner ומ-Next.js"],
        "outputs": ["JSON של חלקה, של קרקע (<code>available_water_mm_per_m</code>) ושל טפטפת (<code>flow_lph</code>)"],
        "code": [
            [REGISTRY + "routers/plots.py", "def get_plot(", "get_plot: חלקה לפי id"],
            [REGISTRY + "routers/catalogues.py", "def get_soil(", "get_soil: קרקע לפי id"],
            [REGISTRY + "routers/catalogues.py", "def get_emitter(", "get_emitter: טפטפת לפי id"],
        ],
        "badges": [["p2", "FR-2.1"], ["project", "JL-007"]],
        "example": {"scenario": "plan", "kind": "calls", "service": "registry-service"},
    },
    "db": {
        "name": "PostgreSQL · SQLite", "title": "המסד של registry", "port": "",
        "short": "PostgreSQL בייצור, SQLite במחשב המפתח.",
        "role": "בייצור: PostgreSQL בקונטיינר Docker, מסד <code>registry</code>. במחשב המפתח ובבדיקות: קובץ SQLite. "
                "רק המשתנה <code>DATABASE_URL</code> קובע איזה מהם, בלי שינוי קוד.",
        "not": "רק registry ניגש אליו. planner ו-weather לא מכירים אותו.",
        "inputs": ["שאילתות SQL מ-registry (SQLAlchemy Core)"],
        "outputs": ["שורות מהטבלאות"],
        "code": [[REGISTRY + "db.py", "def get_db(", "get_db: טרנזקציה אחת לכל בקשה"]],
        "badges": [["p2", "FR-2.1"], ["p2", "NFR-2.1"], ["project", "JL-007"]],
        "example": None,
        "no_example": "לא נמדד: בבניית הדף registry מדומה, ואין מסד.",
    },
    "weather": {
        "name": "weather-service", "title": "שירות מזג האוויר", "port": ":8001",
        "short": "תחזית ET0 וגשם מ-Open-Meteo, שמורה בזיכרון.",
        "role": "מקבל <code>GET /v1/forecast?lat=&lon=&days=</code>. נקודות באותו תא של 0.1° חולקות תחזית אחת, שנשמרת בזיכרון "
                "וטרייה 3 שעות. כש-Open-Meteo נכשל: מנסה עוד פעמיים, ואז עונה בתחזית השמורה אם היא בת 24 שעות לכל היותר, "
                "עם [[stale|<code>stale: true</code>]], ואחרת 503.",
        "not": "יודע רק קואורדינטות ותאריכים: לא חוות, לא חלקות ולא גידולים. אין לו מסד נתונים.",
        "inputs": ["<code>lat</code>, <code>lon</code>, <code>days</code> (1–7)"],
        "outputs": ["לכל יום <code>date</code>, <code>et0_mm</code>, <code>rain_mm</code>, ועוד <code>fetched_at</code> ו-<code>stale</code>",
                    "או 503 <code>UNAVAILABLE</code> עם <code>Retry-After: 60</code>"],
        "code": [
            [WEATHER + "routers/forecast.py", "def get_forecast(", "get_forecast: מטמון, ספק, stale או 503"],
            [WEATHER + "cache.py", "def grid_cell(", "grid_cell: התא של 0.1°"],
            [WEATHER + "provider.py", "def fetch_forecast(", "fetch_forecast: ניסיון ועוד שניים"],
            [WEATHER + "main.py", "async def forecast_unavailable_handler(", "503 עם Retry-After"],
        ],
        "badges": [["p2", "FR-2.3"], ["p2", "FR-2.5"], ["p2", "FR-2.6"], ["p2", "FR-2.8"], ["project", "JL-021"]],
        "example": {"scenario": "plan", "kind": "calls", "service": "weather-service"},
    },
    "openmeteo": {
        "name": "Open-Meteo", "title": "ספק התחזית", "port": "",
        "short": "שירות חיצוני: תחזית יומית.",
        "role": "weather-service מבקש ממנו תחזית של 7 ימים לנקודת המרכז של התא, עם שני משתנים יומיים: "
                "<code>et0_fao_evapotranspiration</code> ו-<code>precipitation_sum</code>, במ\"מ.",
        "not": "שמות השדות שלו מופיעים רק ב-<code>provider.py</code>. שום שירות אחר לא מכיר אותו.",
        "inputs": ["<code>latitude</code>, <code>longitude</code> של מרכז התא, והמשתנים היומיים"],
        "outputs": ["JSON עם רשימת ערכים לכל משתנה, ויחידות"],
        "code": [
            [WEATHER + "provider.py", 'ET0 = "et0_fao_evapotranspiration"', "שמות המשתנים של Open-Meteo"],
            [WEATHER + "provider.py", "def parse_forecast(", "parse_forecast: בדיקה של כל שדה, יחידה ותאריך"],
        ],
        "badges": [["p2", "FR-2.3"]],
        "example": None,
        "no_example": "לא נמדד: בבניית הדף weather-service מדומה כולו, ולכן אין פנייה ל-Open-Meteo.",
    },
}

# Arrows on the map: who calls whom (an HTTP request; the answer comes back the same way). Kept short on purpose.
MAP_EDGES = [
    ["browser", "next", "בקשת דף"],
    ["next", "registry", "חוות וחלקות"],
    ["next", "planner", "תוכנית"],
    ["planner", "registry", "חלקה, קרקע, טפטפת"],
    ["planner", "weather", "תחזית"],
    ["registry", "db", "SQL"],
    ["weather", "openmeteo", "ET0 וגשם"],
]

# --- The decision flow of one plan request (planner-service) ---
# Each node's `function` is how build_explorer.py recognises in a trace that the request reached it.
# Each outcome lists the traced scenarios that end there; the build checks this against the real runs.
TEST_PLAN = PLANNER + "tests/test_plan.py"
TEST_FORECAST = WEATHER + "tests/test_forecast.py"

DECISIONS = [
    {"id": "input", "function": None, "title": "FastAPI בודק את הקלט",
     "text": "<code>plot_id</code> חייב להיות UUID, <code>days</code> בין 1 ל-7, ו-<code>initial_soil_water_pct</code> בין 0 ל-100. "
             "הבדיקה קורית לפני שהקוד שלנו רץ.",
     "code": [PLANNER + "routers/plan.py", "days: Annotated[int, Query(ge=1, le=7)] = 7"],
     "badges": [["p2", "FR-2.12"]],
     "fails": [{"status": 422, "code": "VALIDATION", "label": "קלט לא תקין", "scenarios": ["validation"],
                "test": [TEST_PLAN, "def test_bad_days_is_422_and_calls_no_service("]}]},
    {"id": "plot", "function": "get_plot", "title": "ה-planner מבקש את החלקה מ-registry",
     "text": "אם registry עונה 404, החלקה לא קיימת. אם הוא לא עונה בזמן, או עונה משהו שאי אפשר להשתמש בו, זו תקלה של registry.",
     "code": [PLANNER + "upstream.py", "def get_plot("],
     "badges": [["p2", "FR-2.12"], ["p2", "FR-2.14"]],
     "fails": [{"status": 404, "code": "NOT_FOUND", "label": "החלקה לא קיימת", "scenarios": ["not-found"],
                "test": [TEST_PLAN, "def test_unknown_plot_is_404_and_weather_is_not_called("]},
               {"status": 503, "code": "UPSTREAM_UNAVAILABLE", "label": "registry לא זמין", "scenarios": ["registry-down"],
                "test": [TEST_PLAN, "def test_registry_failure_is_503_naming_registry("]}]},
    {"id": "early", "function": "definitely_out_of_season", "title": "בדיקת עונה מוקדמת, עוד לפני התחזית",
     "text": "ה-planner יודע רק את התאריך שלו ב-UTC, והתאריך בשדה יכול להיות יום לפני או אחרי. "
             "אם התוכנית מחוץ לעונה בכל שלושת התאריכים, אין טעם לבקש תחזית.",
     "code": [PLANNER + "routers/plan.py", "if engine.definitely_out_of_season("],
     "badges": [["project", "JL-020"]],
     "fails": [{"status": 409, "code": "PLOT_OUT_OF_SEASON", "label": "מחוץ לעונה, בלי לשאול את weather", "scenarios": ["out-of-season"],
                "test": [TEST_PLAN, "def test_clearly_out_of_season_plot_is_409_without_soil_emitter_or_weather_calls("]}]},
    {"id": "catalog", "function": "get_soil_water", "title": "הקרקע והטפטפת מ-registry",
     "text": "<code>get_soil_water</code> ו-<code>get_emitter_flow</code>. קרקע או טפטפת שחסרה היא תקלה של registry, לא 404 למשתמש.",
     "code": [PLANNER + "upstream.py", "def get_soil_water("],
     "badges": [["p2", "FR-2.14"]],
     "fails": [{"status": 503, "code": "UPSTREAM_UNAVAILABLE", "label": "registry לא זמין", "scenarios": [],
                "test": [TEST_PLAN, "def test_registry_failure_is_503_naming_registry("]}]},
    {"id": "forecast", "function": "get_forecast", "title": "התחזית מ-weather, לנקודה של החלקה",
     "text": "<code>upstream.get_forecast</code> בודק כל יום: תאריך, ET0 וגשם. ערך חסר או שלילי הוא תקלה, לעולם לא 0.",
     "code": [PLANNER + "upstream.py", "def get_forecast("],
     "badges": [["p2", "FR-2.13"], ["p2", "FR-2.14"]],
     "weather": True,
     "fails": [{"status": 503, "code": "UPSTREAM_UNAVAILABLE", "label": "weather לא זמין, או תחזית פגומה",
                "scenarios": ["weather-down", "weather-bad-field"],
                "test": [TEST_PLAN, "def test_weather_failure_is_503_naming_weather("]}]},
    {"id": "engine", "function": "plan_days", "title": "המנוע: בדיקת העונה הסופית, ואז החישוב",
     "text": "<code>engine.plan_days</code> בודק שוב את העונה, הפעם לפי תאריכי התחזית, שהם התאריך המקומי של החלקה, ומחשב את כל הימים.",
     "code": [PLANNER + "engine.py", "def plan_days("],
     "badges": [["p2", "FR-2.11"], ["project", "JL-020"]],
     "fails": [{"status": 409, "code": "PLOT_OUT_OF_SEASON", "label": "מחוץ לעונה לפי תאריכי התחזית", "scenarios": [],
                "test": [TEST_PLAN, "def test_forecast_dates_outside_the_season_are_409_after_the_weather_call("]}]},
]

SUCCESS = {
    "status": 200, "label": "תוכנית",
    "text": "התשובה מעוגלת ב-<code>routers/plan.py</code> ונשלחת. אם התחזית הייתה stale, כל יום בתוכנית מסומן <code>stale: true</code>.",
    "code": [PLANNER + "routers/plan.py", "return Plan("],
    "badges": [["p2", "FR-2.10"], ["p2", "FR-2.13"]],
    "scenarios": ["plan", "stale", "simulation"],
    "test": [TEST_PLAN, "def test_plan_reproduces_case_3_end_to_end("],
}

FRONTEND_OUTCOME = {
    "title": "Next.js מציג את התשובה",
    "text": "תוכנית: ההמלצה להיום בגדול, ואחריה כל הימים. מספרים מתחזית ישנה מקבלים סימון stale לידם. "
            "שגיאה: <code>PlanError</code> מציג מה קרה, למשל איזה שירות לא זמין, לפי ה-<code>code</code> וה-<code>detail</code> של ה-planner. "
            "אם ה-planner עצמו לא עונה, <code>getPlan</code> מחזיר <code>PLANNER_UNREACHABLE</code>.",
    "code": [
        [FRONTEND + "components/plan-error.tsx", "export function PlanError(", "PlanError"],
        [FRONTEND + "components/stale-badge.tsx", "export function StaleBadge(", "StaleBadge"],
        [FRONTEND + "lib/planner.ts", 'code: "PLANNER_UNREACHABLE"', "PLANNER_UNREACHABLE"],
    ],
    "badges": [["p2", "FR-2.16"], ["p2", "FR-2.17"], ["p2", "FR-2.18"]],
}

# Inside weather-service. Not traced in the build (the planner runs against a fake weather-service); every row
# points at the real code and at the test that covers it. Path B (V2) adds a real trace.
WEATHER_FLOW = [
    {"title": "באיזה תא של 0.1° הנקודה?", "text": "<code>grid_cell(lat, lon)</code>: כל הנקודות באותו תא חולקות תחזית אחת.",
     "code": [WEATHER + "cache.py", "def grid_cell("], "badges": [["p2", "FR-2.5"]],
     "test": [TEST_FORECAST, "def test_points_in_the_same_cell_share_one_provider_call("]},
    {"title": "יש בזיכרון תחזית טרייה שמכסה את הימים?",
     "text": "טרייה: פחות מ-<code>FORECAST_FRESH_HOURS</code> (3 שעות). אם כן, התשובה יוצאת בלי לפנות ל-Open-Meteo.",
     "code": [WEATHER + "routers/forecast.py", "if cached and cached.age(now) < timedelta(hours=settings.forecast_fresh_hours):"],
     "badges": [["p2", "FR-2.5"]],
     "yes": "200, <code>stale: false</code>, מהזיכרון",
     "test": [TEST_FORECAST, "def test_fresh_forecast_is_served_without_a_provider_call("]},
    {"title": "Open-Meteo: ניסיון אחד ועוד שני ניסיונות חוזרים",
     "text": "כל ניסיון מחכה עד <code>PROVIDER_TIMEOUT_SECONDS</code>. כל תשובה נבדקת: שדות, יחידות ותאריכים.",
     "code": [WEATHER + "provider.py", "attempts = 1 + settings.provider_retries"],
     "badges": [["p2", "FR-2.6"], ["p2", "FR-2.8"]],
     "yes": "נשמר בזיכרון ונשלח: 200, <code>stale: false</code>",
     "test": [TEST_FORECAST, "def test_a_forecast_with_a_missing_value_returns_503_not_zeros("]},
    {"title": "כל הניסיונות נכשלו: יש בזיכרון תחזית בת 24 שעות לכל היותר?",
     "text": "<code>FORECAST_MAX_STALE_HOURS</code> הוא 24. אם יש תחזית כזו והיא עדיין מכסה את הימים, היא נשלחת כ-stale. אחרת: 503.",
     "code": [WEATHER + "routers/forecast.py", "if cached and cached.age(now) <= timedelta(hours=settings.forecast_max_stale_hours):"],
     "badges": [["p2", "FR-2.6"], ["p2", "FR-2.7"], ["project", "JL-021"]],
     "yes": "200, <code>stale: true</code>", "no": "503 <code>UNAVAILABLE</code>, <code>Retry-After: 60</code>",
     "test": [TEST_FORECAST, "def test_provider_failure_serves_the_last_forecast_as_stale("]},
]

# --- The guided request walkthrough (Increment 4) ---
# A step is an authored explanation (goal, what, why) tied to a real moment in the trace:
#   at:       (file, function, needle) the line where the step is anchored. The build finds that line in the
#             scenario's trace and fails if it never ran, so a step can't describe something that didn't happen.
#   show:     local variables to show from that function at that moment (the observed values)
#   returns:  functions whose real return value to show
#   calls:    upstream calls to show (plot, soil, emitter, forecast), with the fake service's real answer
#   response: show the planner's real response
#   code:     the line to highlight, if not the anchor line; test: the test that proves the step
# Steps in the browser and Next.js are not traced (the frontend doesn't run during the build): they say so.

WALKTHROUGH_INTRO = (
    "הבקשה <code>GET /v1/plots/{id}/plan</code> עונה על השאלה של המגדל: להשקות היום, וכמה דקות? "
    "ה-planner אוסף את נתוני החלקה מ-registry ואת התחזית מ-weather, מחשב במנוע, ומחזיר תוכנית ל-1 עד 7 ימים. "
    "כל תרחיש כאן הוא ריצה אמיתית של הקוד, עם שירותים מדומים כמו בבדיקות. "
    "בכל צעד ההסבר כתוב בידינו, ו\"מה נמדד בריצה\" נלקח מהריצה עצמה."
)

LANES = [
    ["browser", "דפדפן"], ["next", "Next.js"], ["fastapi", "FastAPI"], ["router", "get_plan"],
    ["upstream", "upstream.py"], ["registry", "registry"], ["weather", "weather"], ["engine", "engine.py"], ["handler", "main.py"],
]

ROUTER = PLANNER + "routers/plan.py"
UP = PLANNER + "upstream.py"
MAIN = PLANNER + "main.py"
ENGINE = PLANNER + "engine.py"

STEPS = {
    "intro": {
        "title": "המשתמש פותח את דף החלקה", "lane": "browser", "to": "next",
        "goal": "לקבל תוכנית השקיה לחלקה אחת, וקודם כול את ההמלצה להיום.",
        "what": "הדפדפן מבקש מ-Next.js את <code>/plots/{id}</code>. השרת של Next.js קורא ל-<code>getPlan</code>, "
                "ששולח ל-planner <code>GET /v1/plots/{id}/plan?days=7</code>, עם timeout של 25 שניות.",
        "why": "הדפדפן לא פונה לשירותים בעצמו. הכתובות שלהם והטיפול בשגיאות נשארים בשרת.",
        "code": [FRONTEND + "lib/planner.ts", "export async function getPlan("],
        "unobserved": "לא נמדד: ה-frontend לא רץ בבניית הדף. המדידה מתחילה כשהבקשה מגיעה ל-planner.",
        "response_request": True,
        "badges": [["p2", "FR-2.16"]],
    },
    "fastapi": {
        "title": "FastAPI בודק את הקלט ומריץ את get_plan", "lane": "fastapi", "to": "router",
        "goal": "לוודא שהבקשה תקינה לפני שהקוד שלנו רץ.",
        "what": "FastAPI מוצא את ה-[[endpoint]] לפי השיטה והכתובת. הוא ממיר כל פרמטר לפי החתימה ובודק אותו ([[validation]]): "
                "<code>plot_id</code> ל-UUID, <code>days</code> למספר שלם בין 1 ל-7, <code>initial_soil_water_pct</code> בין 0 ל-100. "
                "את <code>today</code> הוא מקבל מה-[[dependency]] <code>utc_today</code>. רק אז <code>get_plan</code> רצה, ב-[[worker]].",
        "why": "קלט לא תקין נעצר כאן עם 422, בלי לפנות לאף שירות.",
        "at": [ROUTER, "get_plan", "settings = request.app.state.settings"],
        "code": [ROUTER, "def get_plan("],
        "show": ["plot_id", "today", "days", "initial_soil_water_pct"],
        "test": [TEST_PLAN, "def test_days_sets_the_plan_length("],
        "badges": [["p2", "FR-2.9"], ["p2", "FR-2.12"]],
    },
    "validation_fail": {
        "title": "days=8: הבדיקה נכשלת, והתשובה 422", "lane": "fastapi", "to": "handler", "kind": "error",
        "goal": "להחזיר שגיאה ברורה על קלט לא תקין.",
        "what": "<code>days=8</code> לא עובר את <code>Query(ge=1, le=7)</code>. FastAPI יוצר <code>RequestValidationError</code> "
                "עוד לפני ש-<code>get_plan</code> מתחילה. ה-[[handler]] שלנו ב-<code>main.py</code> הופך אותה לתשובה "
                "<code>{code: VALIDATION, detail}</code>.",
        "why": "כל השגיאות של ה-planner באותה צורה, <code>{code, detail}</code> (FR-2.12). ה-planner לא פנה לאף שירות.",
        "at": [MAIN, "validation_error_handler", 'return JSONResponse(status_code=422, content={"code": "VALIDATION", "detail": detail})'],
        "show": ["detail"],
        "response": True,
        "test": [TEST_PLAN, "def test_bad_days_is_422_and_calls_no_service("],
        "badges": [["p2", "FR-2.12"]],
    },
    "settings": {
        "title": "get_plan לוקחת את ההגדרות ואת לקוחות ה-HTTP", "lane": "router",
        "goal": "לדעת לאן לפנות, וכמה זמן לחכות.",
        "what": "ה-[[lifespan]] ב-<code>main.py</code> יצר כשהשרת עלה את ההגדרות ושני לקוחות <code>httpx2</code>, "
                "עם [[timeout]] של 3 שניות ל-registry ו-12 ל-weather. <code>get_plan</code> רק לוקחת אותם מ-<code>app.state</code>.",
        "why": "הכתובות וזמני ההמתנה באים מ-<code>.env</code>, לא מהקוד. בבדיקות ובכלי הזה הלקוחות מוחלפים ב-[[fake|שירותים מדומים]].",
        "at": [ROUTER, "get_plan", "plot = upstream.get_plot(registry, settings.registry_url, plot_id)"],
        "code": [MAIN, "async def lifespan("],
        "show": ["settings"],
        "test": [TEST_PLAN, "def test_registry_and_weather_base_urls_come_from_settings("],
        "badges": [["p2", "FR-2.14"]],
    },
    "plot": {
        "title": "בקשה ראשונה ל-registry: החלקה", "lane": "upstream", "to": "registry",
        "goal": "לקבל את נתוני החלקה: גידול, תאריך שתילה, שטח, מרווחים, קרקע, טפטפת ומיקום.",
        "what": "<code>get_plot</code> בונה את הכתובת <code>/v1/plots/{id}</code> ושולחת <code>GET</code> דרך <code>send</code>. "
                "<code>send</code> תופסת כל שגיאת רשת או timeout והופכת אותה לשגיאה עם שם השירות.",
        "why": "זו קריאת HTTP לשירות אחר ([[upstream]]): היא יכולה להיכשל, ולכן כל תשובה נבדקת לפני שמשתמשים בה.",
        "at": [UP, "get_plot", "if response.status_code == 404:"],
        "code": [UP, "response = send(client, REGISTRY,"],
        "calls": ["plot"],
        "test": [TEST_PLAN, "def test_plan_asks_registry_then_weather_for_the_plot_point("],
        "badges": [["p2", "FR-2.14"]],
    },
    "plot_ok": {
        "title": "התשובה נבדקת ונהפכת ל-Plot", "lane": "upstream", "to": "router",
        "goal": "לעבוד רק עם נתונים שבטוח אפשר להשתמש בהם.",
        "what": "כל שדה נבדק: טקסט, תאריך, מספר חיובי, קואורדינטה. כל מספר נהפך ל-[[fraction]] פעם אחת, עם "
                "<code>Fraction(str(value))</code>. שדה חסר או בפורמט אחר יוצר <code>UpstreamUnavailable</code>, לעולם לא ערך ברירת מחדל.",
        "why": "אם registry ישנה פורמט, למשל <code>latitude</code> במקום <code>lat</code>, התשובה תהיה 503 שמסבירה מה קרה, ולא תוכנית שגויה.",
        "at": [ROUTER, "get_plan", "crop = engine.crop_profile(plot.crop_id)"],
        "code": [UP, "return Plot("],
        "show": ["plot"],
        "test": [TEST_PLAN, "def test_registry_failure_is_503_naming_registry("],
        "badges": [["p2", "FR-2.14"], ["project", "JL-019"]],
    },
    "plot_404": {
        "title": "registry עונה 404: החלקה לא קיימת", "lane": "upstream", "to": "router", "kind": "error",
        "goal": "להבדיל בין \"אין חלקה כזו\" לבין \"registry תקול\".",
        "what": "התשובה היא 404, ו-<code>get_plot</code> זורקת [[exception|חריגה]] <code>PlotNotFound</code>. "
                "אף פונקציה בדרך לא תופסת אותה, ולכן היא עולה מ-<code>get_plot</code> ל-<code>get_plan</code> ומשם החוצה.",
        "why": "404 אומר למשתמש שהכתובת שגויה. 503 היה אומר לו לנסות שוב, וזה לא יעזור.",
        "at": [UP, "get_plot", "raise PlotNotFound()"],
        "calls": ["plot"],
        "test": [TEST_PLAN, "def test_unknown_plot_is_404_and_weather_is_not_called("],
        "badges": [["p2", "FR-2.12"]],
    },
    "handler_404": {
        "title": "ה-handler של PlotNotFound מחזיר 404", "lane": "handler", "kind": "error",
        "goal": "להפוך את החריגה לתשובת HTTP.",
        "what": "FastAPI מחפש [[handler]] שנרשם לסוג החריגה, <code>@app.exception_handler(PlotNotFound)</code>, "
                "ומריץ אותו ב-[[loop]]. התשובה: <code>404</code>, <code>{code: NOT_FOUND}</code>.",
        "why": "הקוד שמזהה את הבעיה (<code>upstream.py</code>) לא צריך לדעת דבר על HTTP. רק <code>main.py</code> מחליט על הסטטוס.",
        "at": [MAIN, "plot_not_found_handler", 'return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "detail": "Plot not found."})'],
        "response": True,
        "test": [TEST_PLAN, "def test_unknown_plot_is_404_and_weather_is_not_called("],
        "badges": [["p2", "FR-2.12"]],
    },
    "plot_connect": {
        "title": "registry לא עונה: ConnectError הופכת ל-UpstreamUnavailable", "lane": "upstream", "to": "registry", "kind": "error",
        "goal": "לדווח שהשירות לא זמין, ואיזה שירות.",
        "what": "<code>httpx2</code> לא מצליח להתחבר ל-registry וזורק <code>ConnectError</code>. <code>send</code> תופסת כל "
                "<code>httpx2.HTTPError</code>, כולל timeout, וזורקת במקומה <code>UpstreamUnavailable</code> עם שם השירות. "
                "החריגה החדשה עולה דרך <code>get_plot</code> ו-<code>get_plan</code>.",
        "why": "המשתמש צריך לשמוע שהשירות לא זמין, ולא לקבל תוכנית של אפסים או דף ריק (FR-2.14).",
        "at": [UP, "send", 'raise UpstreamUnavailable(service, f"request failed: {type(exc).__name__}") from exc'],
        "show": ["service", "exc"],
        "calls": ["plot"],
        "test": [TEST_PLAN, "def test_registry_failure_is_503_naming_registry("],
        "badges": [["p2", "FR-2.14"]],
    },
    "handler_503": {
        "title": "ה-handler של UpstreamUnavailable מחזיר 503", "lane": "handler", "kind": "error",
        "goal": "תשובה שאומרת איזה שירות לא זמין, וסיבה מפורטת ללוג בלבד.",
        "what": "ה-[[handler]] כותב את הסיבה המלאה ללוג (<code>logger.warning</code>) ומחזיר <code>503</code> עם "
                "<code>{code: UPSTREAM_UNAVAILABLE}</code>. ה-<code>detail</code> אומר רק איזה שירות.",
        "why": "הסיבה הטכנית עוזרת למי שמתחזק את המערכת, והיא נשארת בלוג. המשתמש מקבל משפט ברור.",
        "at": [MAIN, "upstream_unavailable_handler", 'logger.warning("Upstream failure: %s", exc)'],
        "show": ["exc"],
        "response": True, "logs": True,
        "test": [TEST_PLAN, "def test_upstream_failure_reason_is_logged("],
        "badges": [["p2", "FR-2.14"]],
    },
    "early": {
        "title": "בדיקת עונה מוקדמת: עוד לפני שמבקשים תחזית", "lane": "router", "to": "engine",
        "goal": "לא לבקש תחזית לחלקה שבוודאות מחוץ לעונה.",
        "what": "ה-planner יודע רק את התאריך שלו ב-UTC (<code>today</code>). בשדה עצמו התאריך יכול להיות יום לפני או אחרי. "
                "<code>definitely_out_of_season</code> בודקת את שלושתם, ומחזירה <code>True</code> רק אם כולם מחוץ לעונה.",
        "why": "כך חלקה שמחוץ לעונה מקבלת 409 גם כש-weather למטה, ואף פעם לא נדחית לפי תאריך שבו השדה לא נמצא (JL-020).",
        "at": [ROUTER, "get_plan", "soil_water = upstream.get_soil_water(registry, settings.registry_url, plot.soil_id)"],
        "code": [ROUTER, "if engine.definitely_out_of_season(crop, plot.planting_date, today, days):"],
        "show": ["today", "days"],
        "returns": ["definitely_out_of_season"],
        "test": [TEST_PLAN, "def test_planner_a_day_ahead_of_the_field_on_the_last_season_day_still_plans("],
        "badges": [["project", "JL-020"]],
    },
    "early_409": {
        "title": "מחוץ לעונה בכל תאריך אפשרי: עוצרים", "lane": "router", "to": "handler", "kind": "error",
        "goal": "לענות מיד, בלי פניות מיותרות.",
        "what": "<code>definitely_out_of_season</code> החזירה <code>True</code>, ו-<code>get_plan</code> זורקת <code>OutOfSeason</code>. "
                "ה-[[handler]] שלה מחזיר <code>409</code> עם <code>{code: PLOT_OUT_OF_SEASON}</code>.",
        "why": "אין טעם לבקש קרקע, טפטפת ותחזית לחלקה בלי תוכנית. ברשימת הקריאות רואים שנשלחה רק אחת.",
        "at": [ROUTER, "get_plan", "raise engine.OutOfSeason()"],
        "show": ["today", "days"],
        "returns": ["definitely_out_of_season"],
        "response": True,
        "test": [TEST_PLAN, "def test_clearly_out_of_season_plot_is_409_without_soil_emitter_or_weather_calls("],
        "badges": [["project", "JL-020"]],
    },
    "catalog": {
        "title": "עוד שתי בקשות ל-registry: הקרקע והטפטפת", "lane": "upstream", "to": "registry",
        "goal": "לקבל את שני המספרים שהמנוע צריך מהקטלוג.",
        "what": "<code>get_soil_water</code> מחזירה את <code>available_water_mm_per_m</code>, כמה מים הקרקע מחזיקה לכל מטר עומק. "
                "<code>get_emitter_flow</code> מחזירה את <code>flow_lph</code>, ליטרים לשעה לכל טפטפת.",
        "why": "קרקע או טפטפת שחסרה בקטלוג היא תקלה של registry: התשובה 503, לא 404, כי החלקה עצמה קיימת.",
        "at": [ROUTER, "get_plan", "forecast = upstream.get_forecast(weather, settings.weather_url, plot.lat, plot.lon, days)"],
        "code": [ROUTER, "soil_water = upstream.get_soil_water(registry, settings.registry_url, plot.soil_id)"],
        "show": ["soil_water", "emitter_flow"],
        "calls": ["soil", "emitter"],
        "test": [TEST_PLAN, "def test_registry_failure_is_503_naming_registry("],
        "badges": [["p2", "FR-2.14"]],
    },
    "forecast": {
        "title": "בקשה ל-weather: התחזית לנקודה של החלקה", "lane": "upstream", "to": "weather",
        "goal": "לקבל ET0 וגשם לכל יום בתוכנית.",
        "what": "<code>get_forecast</code> שולחת את <code>lat</code> ו-<code>lon</code> של החלקה ואת <code>days</code>. "
                "היא בודקת ש-<code>stale</code> הוא true או false, ולכל יום תאריך, <code>et0_mm</code> ו-<code>rain_mm</code> לא שליליים, "
                "ובדיוק <code>days</code> ימים רצופים.",
        "why": "ערך חסר הוא תקלה, לעולם לא 0: תחזית של אפסים נראית כמו \"לא צריך להשקות\" (FR-2.8).",
        "at": [ROUTER, "get_plan", "result = engine.plan_days("],
        "code": [UP, "def get_forecast("],
        "show": ["forecast"],
        "calls": ["forecast"],
        "test": [TEST_PLAN, "def test_et0_and_rain_are_shown_as_weather_service_sent_them("],
        "badges": [["p2", "FR-2.8"], ["p2", "FR-2.14"]],
    },
    "forecast_connect": {
        "title": "weather לא עונה: 503 בשם weather-service", "lane": "upstream", "to": "weather", "kind": "error",
        "goal": "לדווח שהתחזית לא זמינה.",
        "what": "ה-planner כבר קיבל את החלקה, הקרקע והטפטפת. עכשיו <code>httpx2</code> לא מצליח להתחבר ל-weather, ו-<code>send</code> "
                "הופכת את ה-<code>ConnectError</code> ל-<code>UpstreamUnavailable</code> בשם weather-service.",
        "why": "בלי תחזית אין תוכנית. ה-planner לא מנחש ולא משלים ערכים.",
        "at": [UP, "send", 'raise UpstreamUnavailable(service, f"request failed: {type(exc).__name__}") from exc'],
        "show": ["service", "exc"],
        "calls": ["forecast"],
        "test": [TEST_PLAN, "def test_weather_failure_is_503_naming_weather("],
        "badges": [["p2", "FR-2.14"]],
    },
    "forecast_bad": {
        "title": "ביום 4 חסר ET0: התחזית נדחית", "lane": "upstream", "to": "weather", "kind": "error",
        "goal": "לעולם לא להפוך ערך חסר לאפס.",
        "what": "weather ענה 200, אבל ב-<code>et0_mm</code> של היום הרביעי יש <code>null</code>. <code>exact</code> דוחה כל מה שאינו מספר "
                "(<code>ValueError</code>), ו-<code>get_forecast</code> תופסת אותה וזורקת <code>UpstreamUnavailable</code> בשם weather-service.",
        "why": "גם תשובה עם סטטוס 200 יכולה להיות לא שמישה. בדיקה של כל שדה היא מה שמונע תוכנית שגויה (FR-2.8).",
        "at": [UP, "get_forecast", 'raise UpstreamUnavailable(WEATHER, f"unusable forecast: {exc!r}") from exc'],
        "show": ["exc"],
        "calls": ["forecast"],
        "test": [TEST_PLAN, "def test_weather_failure_is_503_naming_weather("],
        "badges": [["p2", "FR-2.8"]],
    },
    "engine": {
        "title": "המנוע מחשב את התוכנית", "lane": "engine",
        "goal": "להפוך נתוני חלקה ותחזית לליטרים ולדקות, יום אחר יום.",
        "what": "<code>plan_days</code> בודקת את הקלט, ואז בודקת שוב את העונה, הפעם לפי התאריך הראשון בתחזית, שהוא התאריך המקומי של החלקה. "
                "אחר כך היא מחשבת את גודל הדלי (TAW), את הסף, ולולאה של יום אחר יום. את הנוסחאות עצמן מסביר \"חישוב ההשקיה\" (שלב 5).",
        "why": "המנוע טהור: בלי HTTP ובלי עיגול, ורק עם [[fraction]]. לכן אפשר לבדוק אותו לבד, מול חישובים ביד.",
        "at": [ENGINE, "plan_days", "taw = plot.available_water_mm_per_m * crop.root_depth_m  # bucket size, mm [FAO Eq. 82]"],
        "code": [ENGINE, "check_season(crop, plot.planting_date, forecast[0].date, len(forecast))"],
        "show": ["initial_fraction", "crop"],
        "returns": ["plan_days"],
        "test": [PLANNER + "tests/test_engine.py", "def test_case_3_tomato_on_sand_seven_days("],
        "badges": [["p2", "FR-2.11"], ["project", "JL-019"], ["project", "JL-020"]],
    },
    "simulation_start": {
        "title": "סימולציה: הדלי מתחיל חצי מלא", "lane": "engine",
        "goal": "לראות מה התוכנית הייתה אומרת אם הקרקע לא מלאה הבוקר.",
        "what": "<code>initial_soil_water_pct=50</code> הפך ב-router ל-<code>Fraction(50, 100)</code>, כלומר חצי. "
                "המנוע מתחיל את יום 1 מ-<code>TAW × ½</code> במקום מדלי מלא. TAW, הסף והתקרה לא משתנים.",
        "why": "ברירת המחדל, דלי מלא, היא הנחה ולא מדידה (JL-011). הסימולציה מראה כמה התוכנית תלויה בה, והיא לא המלצה שנבדקה בשדה.",
        "at": [ENGINE, "plan_days", "for day in forecast:"],
        "code": [ENGINE, "previous_end = taw * initial_fraction"],
        "show": ["initial_fraction", "taw", "previous_end"],
        "test": [TEST_PLAN, "def test_starting_half_full_reproduces_b7("],
        "badges": [["project", "JL-011"]],
    },
    "respond": {
        "title": "עיגול לתשובה, ושליחה", "lane": "router", "to": "fastapi", "kind": "ok",
        "goal": "להחזיר תוכנית שקל לקרוא, בלי לפגוע בחישוב.",
        "what": "רק כאן מעגלים, עם <code>round_half_up</code>: ליטרים ודקות למספר שלם, Kc ומפלס הדלי ל-3 ספרות. "
                "<code>et0_mm</code> נשאר כמו ש-weather שלח, ו-<code>stale</code> של התחזית מועתק לכל יום. "
                "FastAPI בודק את התוצאה מול <code>response_model=Plan</code> ושולח JSON.",
        "why": "העיגול קורה רק בסוף, כדי שהחישוב עצמו יישאר מדויק (JL-018).",
        "at": [ROUTER, "get_plan", "return Plan("],
        "response": True,
        "test": [TEST_PLAN, "def test_plan_reproduces_case_3_end_to_end("],
        "badges": [["p2", "FR-2.10"], ["project", "JL-018"]],
    },
    "stale_mark": {
        "title": "התחזית stale: התוכנית נבנית, ומסומנת", "lane": "router", "kind": "ok",
        "goal": "לתת תוכנית גם כש-Open-Meteo נפל, ולהגיד את זה בבירור.",
        "what": "weather ענה בתחזית שמורה עם <code>stale: true</code>, כי Open-Meteo לא ענה. ה-planner לא משנה אף מספר: "
                "הוא מחשב כרגיל, ומסמן כל יום <code>stale: true</code>.",
        "why": "המגדל מקבל תוכנית, ויודע שהיא מבוססת על תחזית ישנה (FR-2.13). Next.js מציג סימון stale ליד המספרים (FR-2.17).",
        "at": [ROUTER, "get_plan", "return Plan("],
        "code": [ROUTER, "stale=forecast.stale,"],
        "show": ["forecast"],
        "response": True,
        "test": [TEST_PLAN, "def test_stale_forecast_still_plans_with_every_day_stale("],
        "badges": [["p2", "FR-2.13"], ["p2", "FR-2.17"]],
    },
    "front_ok": {
        "title": "Next.js מציג את ההמלצה להיום", "lane": "next", "to": "browser", "kind": "ok",
        "goal": "שהמגדל יראה בשנייה: להשקות היום או לא, וכמה דקות.",
        "what": "<code>getPlan</code> מקבל תשובה תקינה ומחזיר <code>{ok: true, plan}</code>. הדף מציג קודם את היום הראשון בגדול, "
                "\"Water for N minutes\" או \"No irrigation today\", ואחריו את כל הימים.",
        "why": "ההמלצה להיום היא מה שהמגדל צריך בשדה, גם בטלפון (FR-2.16, NFR-2.8).",
        "code": [FRONTEND + "components/today-panel.tsx", "No irrigation today"],
        "unobserved": "לא נמדד: ה-frontend לא רץ בבניית הדף. הנתונים שהוא היה מקבל הם התשובה שנמדדה:",
        "response": True,
        "badges": [["p2", "FR-2.16"]],
    },
    "front_err": {
        "title": "Next.js מציג למשתמש מה קרה", "lane": "next", "to": "browser", "kind": "error",
        "goal": "שהמשתמש יבין מה קרה, בלי דף ריק ובלי stack trace.",
        "what": "<code>getPlan</code> רואה תשובה לא תקינה עם <code>code</code> ו-<code>detail</code>, ומחזיר "
                "<code>{ok: false, status, code, detail}</code>. <code>PlanError</code> בוחר כותרת וטקסט לפי ה-<code>code</code>. "
                "ב-503 ה-<code>detail</code> של ה-planner אומר איזה שירות לא זמין.",
        "why": "FR-2.18: המשתמש רואה מה קרה. אם ה-planner עצמו לא עונה, <code>getPlan</code> מחזיר <code>PLANNER_UNREACHABLE</code>.",
        "code": [FRONTEND + "components/plan-error.tsx", "function describe("],
        "unobserved": "לא נמדד: ה-frontend לא רץ בבניית הדף. התשובה שהוא היה מקבל היא זו שנמדדה:",
        "response": True,
        "badges": [["p2", "FR-2.18"]],
    },
}

_OK_PATH = ["intro", "fastapi", "settings", "plot", "plot_ok", "early", "catalog", "forecast", "engine"]
WALKTHROUGH = {
    "plan": _OK_PATH + ["respond", "front_ok"],
    "stale": _OK_PATH + ["stale_mark", "front_ok"],
    "simulation": _OK_PATH + ["simulation_start", "respond", "front_ok"],
    "validation": ["intro", "validation_fail", "front_err"],
    "not-found": ["intro", "fastapi", "settings", "plot_404", "handler_404", "front_err"],
    "out-of-season": ["intro", "fastapi", "settings", "plot", "plot_ok", "early_409", "front_err"],
    "registry-down": ["intro", "fastapi", "settings", "plot_connect", "handler_503", "front_err"],
    "weather-down": ["intro", "fastapi", "settings", "plot", "plot_ok", "early", "catalog", "forecast_connect", "handler_503", "front_err"],
    "weather-bad-field": ["intro", "fastapi", "settings", "plot", "plot_ok", "early", "catalog", "forecast_bad", "handler_503", "front_err"],
}

