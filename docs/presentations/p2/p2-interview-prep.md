# AgroPilot P2 — מסמך הכנה לסקירה

<div dir="rtl">

**איך לקרוא את המסמך:** `file.py:42` פירושו שורה 42 בקובץ הזה. כל הנתיבים יחסיים לשורש הריפו. בכל תשובה יש תווית:

- **MEASURED** — הורץ או נמדד. כתוב איך.
- **READ IN CODE** — נקרא בקוד או בתיעוד הרשמי, לא הורץ.
- **REASONED** — נובע מהקוד, אבל שום דבר לא מראה את זה ישירות.

המצגת שמלווה את המסמך: `docs/presentations/p2/p2-slides.pptx`. הטבלה של השקפים בסוף המסמך.

## 1. המערכת בפסקה אחת

P2 הוא שכבה מעל P1. ב-P1 בנינו את `registry-service`: API של חוות, חלקות וקטלוגים (גידולים, קרקעות, טפטפות) על SQLite. ב-P2 ה-registry עבר ל-PostgreSQL ב-production (SQLite נשאר למחשב של המפתח ולטסטים), ונוספו שלושה רכיבים: `weather-service`, שמביא תחזית ET0 וגשם מ-Open-Meteo ושומר אותה בזיכרון לפי תא רשת; `planner-service`, שמחשב את תוכנית ההשקיה ל-7 ימים, והוא המקום היחיד שבו מחושב מספר; ו-`frontend` ב-Next.js, שמציג את החוות, החלקות והתוכנית. הדפדפן מדבר רק עם שרת ה-frontend. השירותים מדברים רק ב-HTTP ואין ביניהם קוד משותף.

</div>

```text
                         HTTP (pages)
 ┌─────────┐  ───────────────────────────►  ┌──────────────────────┐
 │ Browser │                                │ frontend :3000       │  Next.js server (P2)
 └─────────┘  ◄─────────────────────────── │ server components    │
               HTML, streamed in parts      └──────────────────────┘
                                              │ farms, plots, plot      │ plan              │ GET /health (all three, 2 s)
                                              ▼ (5 s)                   ▼ (25 s)
                                   ┌───────────────────┐       ┌───────────────────┐
                                   │ registry :8000    │ ◄──── │ planner :8002     │  (P2)
                                   │ (P1)              │ plot, │ engine.py: the    │
                                   └───────────────────┘ soil, │ only calculation  │
                                     │ SQL               emitter└───────────────────┘
                                     ▼                   (3 s each)  │ forecast (12 s)
                           ┌────────────────────┐                    ▼
                           │ SQLite (P1, dev)   │          ┌───────────────────┐   cache miss only    ┌────────────┐
                           │ PostgreSQL (P2,    │          │ weather :8001     │ ───────────────────► │ Open-Meteo │
                           │ Docker :5436)      │          │ (P2) cache per    │  3 tries, 3 s each   │ (HTTPS)    │
                           └────────────────────┘          │ 0.1° cell         │                      └────────────┘
                                                           └───────────────────┘
```

<div dir="rtl">

כל החצים הם HTTP/JSON בתוך המחשב (127.0.0.1), חוץ מהחץ ל-Open-Meteo שיוצא לאינטרנט, והחץ ל-DB שהוא SQL. המספרים בסוגריים הם ה-timeouts.

## 2. שאלות הסקירה

השאלות מתוך סעיף "Review questions" בסוף `tasks/p2.md`, מילה במילה.

### Q1. Which sensitive data exists and how do you protect it?

- **תשובה קצרה:** יש שלושה סודות ומידע רגיש אחד. הסיסמה של PostgreSQL ב-`.env` של ה-registry, מפתח ה-API של Open-Meteo (ריק היום) ב-`.env` של ה-weather, ומפתח ה-SSH של שרת ה-EC2 ב-GitHub Actions secrets. המידע הרגיש הוא נתוני החקלאים, ובמיוחד המיקום המדויק של השדות. אף אחד מהם לא נכנס ל-git, ללוגים או לדפדפן.
- **הסבר:**
  - `.env` ו-`.env.*` ב-`.gitignore` (`.gitignore:12-14`), ורק `.env.example` עם ערכים לדוגמה נכנס ל-git.
  - כשה-registry מדפיס את כתובת ה-DB ללוג, הסיסמה מוחלפת ב-`***` (`services/registry-service/db.py:44-47`, `services/registry-service/main.py:20`).
  - כל engine של SQLAlchemy עם `hide_parameters=True` (`services/registry-service/db.py:72-73,100,109`): כששאילתה נכשלת, הלוג לא מראה את הערכים (שמות חוות וחלקות). כל ה-SQL עם bound parameters, כלומר הערכים עוברים בנפרד מהטקסט של השאילתה.
  - המפתח של Open-Meteo הוא `SecretStr` (`services/weather-service/config.py:18`), טיפוס שמדפיס כוכביות. המפתח עובר ב-URL כ-query parameter, ויש שגיאות של httpx שמצטטות את ה-URL, ולכן בכשל נרשם רק סוג השגיאה (`services/weather-service/provider.py:52-54`). גם הודעת שגיאת הקונפיגורציה לא מדפיסה ערכים (`services/weather-service/config.py:31-43`).
  - בדפדפן: כל קובץ ב-`src/lib` מתחיל ב-`import "server-only"` (`services/frontend/src/lib/config.ts:1`), כך שאם קוד של הדפדפן מייבא אותו, ה-build נכשל. אין משתני `NEXT_PUBLIC_`, ולכן הכתובות של השירותים לא מגיעות לדפדפן.
  - Open-Meteo מקבל רק את מרכז תא הרשת, לא את המיקום המדויק של השדה (`services/weather-service/cache.py:29-32`, `services/weather-service/routers/forecast.py:43-44`).
  - שירותי Python מאזינים רק ל-`127.0.0.1` (פקודות ההרצה ב-README של כל שירות), וה-PostgreSQL ב-Docker פתוח רק ל-`127.0.0.1:5436` (`services/registry-service/README.md:119`).
- **מה עוד לא מוגן:** אין authentication (זיהוי משתמש) ואין TLS (הצפנת התעבורה). משתמש ה-DB הוא `postgres`, superuser. אין secrets manager. `next dev` מאזין כברירת מחדל ל-`0.0.0.0`, כלומר לכל הרשת המקומית (`services/frontend/node_modules/next/dist/docs/01-app/03-api-reference/06-cli/next.md:71`). חוק ה-deny של Claude על `.env` (`.claude/settings.json`) מונע קריאה בטעות של ה-agent, ואינו גבול אבטחה.
- **ראיות:** הקבצים למעלה. `gh secret list` מציג `EC2_HOST` ו-`EC2_SSH_KEY`. ה-workflow שמשתמש בהם, `deploy-registry.yaml`, נמצא ב-`main` ולא בענף `p2`.
- **תווית:** READ IN CODE. ה-secrets ב-GitHub: MEASURED (`gh secret list`).
- **שקף:** 8.

### Q2. Explain the user flow from the browser to the services and back

- **תשובה קצרה:** הדפדפן מדבר רק עם שרת ה-Next.js בפורט 3000. השרת הוא שקורא לשירותים, בונה HTML ושולח אותו לדפדפן בחלקים. בדף הראשי הוא קורא במקביל לשורת הסטטוס ולרשימת החוות. בדף חלקה הוא קורא במקביל ל-registry (שם החלקה) ול-planner (התוכנית).
- **הסבר:**
  1. החקלאי פותח את `/`. ה-root layout מריץ את `StatusLine` בתוך `Suspense` (`services/frontend/src/app/layout.tsx:32-34`), והדף מריץ את `FarmList` בתוך `Suspense` משלו (`services/frontend/src/app/page.tsx:12-14`). שני החלקים רצים במקביל, והדפדפן מקבל קודם שלד של הדף עם טקסט זמני ("Checking services…", "Loading farms…"), וכל חלק מתמלא כשהוא מוכן.
  2. `StatusLine` קורא ל-`GET /health` של שלושת השירותים במקביל, עם timeout של 2 שניות ובלי cache (`services/frontend/src/lib/health.ts:4,10-23`).
  3. `FarmList` קורא במקביל ל-`/v1/farms` ול-`/v1/plots` ומחבר אותם לפי `farm_id` (`services/frontend/src/lib/registry.ts:21-31`).
  4. לחיצה על חלקה: `/plots/{id}`. השרת מריץ `Promise.all` של `getPlot` ו-`getPlan`, כלומר שתי הקריאות במקביל (`services/frontend/src/app/plots/[id]/page.tsx:35-38`). ההמלצה של היום מוצגת ראשונה (`TodayPanel`), ואחריה 7 הימים (`PlanDays`).
  5. תחזית stale: תג "Stale forecast" ליד כל יום מושפע (`services/frontend/src/components/plan-days.tsx:37,87`, `services/frontend/src/components/today-panel.tsx:27`) והודעה עם זמן התחזית (`services/frontend/src/components/stale-notice.tsx:5-14`).
  6. סימולציה, אופציונלי: טופס HTML רגיל שרק מוסיף `?soil=40` לכתובת (`services/frontend/src/components/simulation-form.tsx`). ה-planner מחזיר את הערך שבו השתמש, ואם הוא לא תואם, הדף לא מציג מספרים (`services/frontend/src/app/plots/[id]/page.tsx:72-76`).
  7. ה-frontend לא מחשב שום מספר של ההשקיה. הוא מציג.
- **ראיות:** הקבצים למעלה. כתובות השירותים נקראות מ-`process.env` רק אחרי `connection()`, בזמן בקשה ולא בזמן build (`services/frontend/src/lib/config.ts:13-21`).
- **תווית:** READ IN CODE. לא נבדק בדפדפן בהכנה הזו.
- **שקף:** 3.

### Q3. Explain the system flow from the frontend to the services and back. Not only the happy-path, explain what happens and how when an error occurs.

- **תשובה קצרה (happy path):** ה-frontend מבקש תוכנית מה-planner. ה-planner בודק את הבקשה, מבקש מה-registry את החלקה, בודק אם היא בעונה, מבקש קרקע וטפטפת, ואז את התחזית מה-weather. כל תשובה נבדקת לפני שהמנוע רואה אותה. המנוע מחשב בשברים מדויקים, ורק התשובה מעוגלת.
- **תשובה קצרה (שגיאות):** כל כשל של שירות שה-planner תלוי בו הופך ל-`503 UPSTREAM_UNAVAILABLE` עם שם השירות. הסיבה הטכנית נרשמת בלוג של ה-planner, והחקלאי רואה משפט: "No plan right now… Try again in a minute." אף פעם לא תוכנית של אפסים.
- **הסבר:** ראו סעיף 4, "זרימות", שלב אחר שלב.
- **תווית:** READ IN CODE. הסדר והשגיאות: MEASURED בטסטים (174 טסטים של ה-planner עברו, 100% branch coverage, `uv run pytest --cov` בתיקיית השירות).
- **שקפים:** 4 (happy path), 5 (שגיאות).

### Q4. Why do we need the weather service? Why not talking with Open-Meteo directly from the frontend? How did you test this service?

- **תשובה קצרה (למה):** החישוב קורה ב-planner, בשרת, ולכן התחזית צריכה להגיע לשרת בכל מקרה. אם הדפדפן היה מביא אותה, ה-planner היה צריך לסמוך על ET0 שהגיע מהדפדפן, וכל אחד יכול לשלוח מזג אוויר מומצא. בנוסף: cache אחד לכולם לפי תא רשת במקום cache לכל דפדפן, retries ו-stale כתובים ונבדקים במקום אחד, וההחלפה של הספק משנה קובץ אחד (`provider.py`).
- **תשובה קצרה (טסטים):** 135 טסטים, 100% branch coverage, בלי רשת. Open-Meteo מוחלף ב-fake שמחובר מתחת ל-HTTP client (`MockTransport`), והשעון מוחלף בשעון שהטסט מזיז. כך בודקים 3 שעות ו-24 שעות בלי לחכות.
- **הסבר:**
  - השמות של Open-Meteo (`et0_fao_evapotranspiration`, `precipitation_sum`) מופיעים רק ב-`services/weather-service/provider.py:17-18`.
  - הבדיקה הקפדנית של כל תשובה: יחידות `mm`, בדיוק 7 ימים, תאריכים רצופים מהיום המקומי, כל ערך מספר סופי ≥ 0 (`services/weather-service/provider.py:64-111`). ערך חסר הוא כשל, לא 0 (FR-2.8).
  - ה-fake: `FakeProvider` עם `httpx2.MockTransport` (`services/weather-service/tests/conftest.py:52-77`). השעון: `Clock` ו-`dependency_overrides[utc_now]` (`tests/conftest.py:78-104`, `routers/forecast.py:17-19`). ה-`.env` לא נקרא בטסטים (`tests/conftest.py:28-33`).
  - טסטים מרכזיים: שתי נקודות באותו תא חולקות קריאה אחת (`tests/test_forecast.py:112`), אחרי 2:59 עדיין קריאה אחת (`:129`), אחרי 3 שעות קריאה שנייה (`:140`), stale עד 24 שעות (`:191`), 24 שעות ושנייה נותנות 503 (`:231`), ערך חסר נותן 503 ולא אפסים (`:247`), 32 סוגי כשל, כל אחד 3 ניסיונות (`tests/test_provider.py:126`), המפתח לא מופיע בלוג (`tests/test_provider.py:147`).
- **תווית:** READ IN CODE. הטסטים: MEASURED (135 עברו, `uv run pytest --cov`).
- **שקפים:** 6 (למה), 7 (טסטים).

### Q5. Edge cases: What happens if the registry service is down? What happends if it changes the response format, e.g. `latitude` instead of `lat`?

- **תשובה קצרה:** בשני המקרים אותה תוצאה: `503 UPSTREAM_UNAVAILABLE` עם "registry-service is unavailable or did not answer in time.", וה-planner לא קורא בכלל ל-weather, כי בלי החלקה אין קואורדינטות. בלוג של ה-planner כתובה הסיבה המדויקת, למשל `ConnectError` או `KeyError('lat')`.
- **הסבר:**
  - "down" זה שלושה מצבים: התהליך לא רץ (`ConnectError`), התהליך איטי מ-3 שניות (`ReadTimeout`), או שהתהליך רץ וה-DB שלו לא זמין, ואז הוא עצמו מחזיר `503 Database unavailable` (`services/registry-service/main.py:30-38`). שני הראשונים נתפסים ב-`send` (`services/planner-service/upstream.py:126-130`), השלישי ב-`json_body`, שהופך כל status שאינו 200 לכשל (`upstream.py:133-135`).
  - `latitude` במקום `lat`: `body["lat"]` זורק `KeyError` (`upstream.py:71`). ה-`except` תופס `KeyError`, `TypeError` ו-`ValueError` ומרים `UpstreamUnavailable` עם הסיבה (`upstream.py:74-75`). ה-handler רושם אותה ומחזיר 503 (`services/planner-service/main.py:64-71`).
  - למה לא ברירת מחדל: קואורדינטה (0, 0) היא באוקיינוס האטלנטי, במפרץ גינאה. ה-weather היה מחזיר תחזית אמיתית לשם, והתוכנית הייתה נראית רגילה לגמרי ושגויה לגמרי.
  - כשה-registry חוזר, הכול עובד בלי restart: ל-planner אין state, וב-PostgreSQL `pool_pre_ping` מחליף חיבורים מתים (`services/registry-service/db.py:106-111`).
  - אם ה-registry שבור לגמרי, גם הדף הראשי לא מציג חוות: "Can't load the farms" (`services/frontend/src/app/page.tsx:21-27`).
- **ראיות:** 23 מקרים של כשל registry בטסט אחד עם parametrize, כולל ConnectError, ReadTimeout, 503, גוף שאינו JSON, `lat=None` ושדה חסר (`services/planner-service/tests/test_plan.py:249-283`). בכולם הטסט בודק גם שה-weather לא נקרא.
- **פער כנה:** אין טסט שמשנה בדיוק את `lat` ל-`latitude`. אותו מסלול (`KeyError` על שדה חסר) נבדק עם `soil_id` חסר. ההודעה למשתמש אומרת "unavailable" גם כשבפועל ה-contract נשבר; הלוג מדויק. ה-frontend קורא את ה-registry בלי בדיקה בזמן ריצה (`(await response.json()) as T`, `services/frontend/src/lib/registry.ts:17`), כך ששם שדה שגוי יציג שדה ריק בכותרת, לא שגיאה.
- **תווית:** READ IN CODE + MEASURED בטסטים. מסלול ה-`latitude` המדויק: REASONED (אותו `except`).
- **שקף:** 5.

### Q6. How did you test the planner service, which depends on the weather and the registry service? Explain the approach.

- **תשובה קצרה:** מפרידים בין מה שמחשבים לבין מי שקוראים לו. המנוע (`engine.py`) הוא פונקציות טהורות בלי HTTP, ונבדק מול מקרים שחושבו ביד. הממירים נבדקים לבד (0.4 הופך בדיוק ל-2/5, ו-null, true/false, NaN ואינסוף נדחים). ה-endpoint נבדק עם האפליקציה האמיתית, וה-registry וה-weather מוחלפים ב-fakes מתחת ל-HTTP client. הטסטים בודקים גם אילו קריאות לא נעשו.
- **הסבר:**
  - `tests/test_engine.py`: מקרים שחושבו ביד לפני שהמנוע נכתב (ב-skill `irrigation-calc-reference`), כולל הדוגמה של המשימה: 6,900 ליטר ו-248 דקות (`tests/test_engine.py:51-67`).
  - `tests/test_upstream.py`: הממירים.
  - `tests/test_plan.py`: `TestClient` מריץ את ה-FastAPI האמיתי. `FakeService` עם `MockTransport` עונה במקום ה-registry וה-weather (`tests/conftest.py:73-138`), ו-`utc_today` מוחלף בתאריך קבוע.
  - דוגמאות ל-"מה לא נקרא": 422 בלי שום קריאה (`tests/test_plan.py:145`), 404 בלי קריאה ל-weather (`:166`), 409 בלי קרקע, טפטפת ו-weather (`:179`). הסדר המדויק של הקריאות (`:54`). Case 3 מקצה לקצה (`:27`).
- **מה coverage לא אומר:** שה-assertions נכונים, שה-fakes תואמים לשירותים האמיתיים, או שהמערכת עומדת בעומס. timeout מזויף נזרק מיד; אף טסט לא מחכה 3 שניות. אין טסט שמריץ את השירותים האמיתיים יחד.
- **תווית:** MEASURED (174 עברו, 100% branch coverage).
- **שקף:** 7.

### Q7. In terms of performance, is there a bottleneck in the system? How do you know?

- **תשובה קצרה:** בעומס שה-spec מגדיר, 10 בקשות לשנייה, אין צוואר בקבוק: כל hop רחוק מאוד מ-100 ms. כשהעלינו את הקצב, עד 200 בקשות לשנייה ה-p95 של תוכנית נשאר מתחת ל-30 ms. כשביקשנו 400, המערכת הספיקה בערך 320 תוכניות לשנייה וה-p95 קפץ לבערך 4 שניות: בקשות חיכו בתור. איזה hop נרווה ראשון לא בודדנו.
- **המספרים (p95 ב-10 בקשות לשנייה):** registry על PostgreSQL ‏14.51 ms (NFR-2.2), weather מה-cache ‏8.73 ms (NFR-2.3), תוכנית שלמה ‏26.60 ms, דף חלקה ב-frontend ‏42.47 ms. registry על SQLite ‏10.95 ms (NFR-1.1), אם שואלים.
- **איך נמדד:** registry ו-weather עם הסקריפטים הרשמיים (`scripts/measure_p95.py` בכל שירות: 1,200 בקשות, 10 לשנייה, 120 שניות, PASS רק אם כל route מתחת ל-100 ms). planner ו-frontend עם oha (600 בקשות), כי אין להם יעד ב-P2. הכול על הלפטופ דרך loopback: זה זמן תגובה, לא קיבולת של production. מספרים מכלים שונים לא משווים אחד לאחד.
- **החשודים (REASONED):** 4 קריאות HTTP בזו אחר זו לכל תוכנית (`services/planner-service/routers/plan.py:35-45`), ו-endpoints רגילים (`def`) שרצים ב-thread pool של 40 threads לכל תהליך (ברירת המחדל של AnyIO, `CapacityLimiter(40)`).
- **למה דף החלקה 42 ms כשתוכנית 27 ms (REASONED):** לא בגלל קריאות בזו אחר זו. ה-frontend קורא ל-planner ול-registry במקביל (`services/frontend/src/app/plots/[id]/page.tsx:35-38`), ובנוסף שורת הסטטוס קוראת לשלושה `/health` באותה טעינה. ההפרש הוא כנראה הקריאה הארוכה מבין המקבילות, הבנייה של ה-HTML וה-hop הנוסף. לא נמדד לפי חלקים.
- **ראיות:** מדריך ההצגה הקודם ("המספרים, למקרה שישאלו") והערות שקף 12 במצגת P2 הקודמת. שניהם הוסרו מהתיקייה ונשארו בהיסטוריה של Git (commit `3ab63c5`).
- **תווית:** MEASURED (המספרים, מהמסמכים; לא הורצו מחדש בהכנה הזו). החשודים: REASONED.
- **שקף:** 9.

### Q8. How did you deal with API rate limit of Open-Meteo?

- **תשובה קצרה:** בתכנון ולא באכיפה. רק שירות אחד מדבר עם Open-Meteo, הוא שומר תחזית אחת של 7 ימים לכל תא של 0.1° למשך 3 שעות, ולכן בשימוש רגיל יש בערך 8 קריאות לתא ביום, לא משנה כמה בקשות יש. ב-benchmark: 1,200 בקשות, קריאה אחת לספק (החימום).
- **הסבר:**
  - החשבון: 24 שעות חלקי 3 שעות = 8 קריאות לתא ביום, ועוד אחת אחרי חצות מקומית כשלתחזית השמורה חסר יום (`services/weather-service/routers/forecast.py:36-40`). REASONED.
  - תמיד מבקשים 7 ימים (`services/weather-service/provider.py:16`), כך שבקשה של יום אחד ובקשה של 7 ימים חולקות קריאה.
  - המגבלה של ה-free tier, לפי מדריך ההצגה (שציטט את האתר של Open-Meteo): פחות מ-10,000 קריאות ביום, 5,000 בשעה, 600 בדקה, לשימוש לא מסחרי. לא נבדק מחדש בהכנה הזו.
  - מה לא מטופל: 429 (Too Many Requests) הוא סתם עוד status שאינו 200, כלומר 3 ניסיונות מיד ואז stale או 503 (`provider.py:55-56`). אין backoff (המתנה שגדלה בין ניסיונות). אין negative caching (זיכרון של כשל), ולכן בזמן תקלה, בקצב של 10 בקשות לשנייה, כל בקשה מנסה 3 פעמים: 30 קריאות לשנייה, ועוברים 600 בדקה תוך בערך 20 שניות (REASONED). ואין הגנה על cache miss במקביל (סעיף 5).
- **תווית:** READ IN CODE, החשבון REASONED, ה-1,200→1: MEASURED (ה-benchmark נכשל אם יש קריאה לספק מעבר לחימום, `services/weather-service/README.md:219-222`).
- **שקף:** 6.

### Q9. How did you validate the FR and NFR of the system? How did you check that you built the system right?

- **תשובה קצרה:** כל דרישה מקושרת לבדיקה. weather ו-planner: טסטים עם 100% branch coverage, והמנוע משחזר בדיוק מקרים שחושבו ביד. ה-registry: אותם טסטים רצים על SQLite ועל PostgreSQL, ב-CI. ה-NFRs של זמן תגובה: סקריפטי benchmark עם כלל PASS/FAIL, שגם הוא נבדק בטסט. הפער: דרישות ה-frontend נבדקו רק ידנית בדפדפן. וזו verification (בנינו לפי ה-spec), לא validation: התוכנית לא הושוותה אף פעם לנתוני שדה.
- **הסבר:**
  - השרשרת: spec → מחקר FAO-56 עם ציטוטים (`services/planner-service/docs/research/fao56.md`) → skill `irrigation-calc-reference` עם הנוסחאות, היחידות, העיגול ומקרים שחושבו ביד → טסטים שמשחזרים אותם → judgment log (`docs/judgment-log.md`, JL-011 עד JL-021) עם כל החלטה, החלופות והמחיר.
  - FR-2.1/FR-2.2/NFR-2.1: הטסטים של ה-registry רצים על שני ה-DBs, כולל `tests/test_setup_postgres.py` לפקודת ההקמה. CI: `.github/workflows/registry-service.yaml` מריץ SQLite ואז PostgreSQL ודורש 100% על שתי ההרצות יחד, ועוד `uv audit`.
  - FR-2.3 עד FR-2.8: טסטי ה-weather (Q4). FR-2.8 בטסט שערך חסר נותן 503 ולא אפסים.
  - FR-2.9 עד FR-2.14: טסטי ה-planner (Q6). FR-2.14 ב-23 + 17 מקרי כשל.
  - NFR-1.1/NFR-2.2/NFR-2.3: הסקריפטים `scripts/measure_p95.py`.
  - FR-2.15 עד FR-2.19 ו-NFR-2.8: רק `npm run build`, `npm run lint` ובדיקה ידנית בדפדפן ב-375 px. אין טסטים אוטומטיים ל-frontend.
  - CI יש רק ל-registry. ל-weather, planner ו-frontend אין.
- **תווית:** טסטים: MEASURED (planner 174, weather 135, registry 272 עברו ו-6 דולגו על SQLite). ה-coverage של ה-registry על SQLite לבד אינו 100%; ה-100% נמדד ב-CI על שתי ההרצות יחד, ולא הרצתי PostgreSQL בהכנה הזו. frontend: לא נבדק בהכנה הזו.
- **שקף:** 10.

## 3. שאלות המשך צפויות

### מתי זה רץ

- **"בדיקת ה-health ב-frontend: מתי היא רצה? פעם אחת בעליית השרת?"** — לא. היא ב-root layout (`services/frontend/src/app/layout.tsx:32-34`), ולכן רצה בכל טעינה מלאה של דף, בשרת של Next.js (לא בדפדפן). בניווט בלחיצה על `<Link>` ה-layout לא מתרנדר מחדש (תיעוד Next.js: `node_modules/next/dist/docs/01-app/04-glossary.md:119`), ולכן הסטטוס לא מתעדכן עד reload. שום דבר לא עושה polling. **READ IN CODE**.
- **"מה רץ פעם אחת בעלייה?"** — ב-weather וב-planner, `lifespan` קורא את ה-settings פעם אחת ועוצר את השירות אם חסר משתנה, ופותח HTTP client אחד עם ה-timeout (`services/planner-service/main.py:18-36`, `services/weather-service/main.py:20-35`). ה-cache של ה-weather נוצר ריק בעלייה (`services/weather-service/main.py:32`). ה-registry קורא את `DATABASE_URL` בכל קריאה (`config.py`), ורק רושם בעלייה לאיזה DB הוא מחובר, בלי להתחבר (`services/registry-service/main.py:16-21`). ה-frontend קורא את כתובות השירותים בכל בקשה (`services/frontend/src/lib/config.ts:13-21`). **READ IN CODE**.
- **"משהו נשמר ב-cache ב-frontend?"** — לא. כל `fetch` עם `cache: "no-store"` (`health.ts:15`, `registry.ts:11`, `planner.ts:21`). כל רענון עובר את כל השרשרת. ה-cache היחיד במערכת הוא של ה-weather. **READ IN CODE**.

### מה בדיקה באמת בודקת

- **"מה `/health` מוכיח?"** — רק שהתהליך עונה ל-HTTP (liveness). הוא מחזיר קבוע ולא בודק תלות: ה-registry מחזיר 200 גם כשה-DB למטה (`services/registry-service/main.py:41-43`), וה-weather מחזיר 200 גם כש-Open-Meteo למטה. בדיקת readiness (האם התלויות עובדות) לא קיימת. לכן שורת הסטטוס יכולה להראות weather up בזמן שאין תחזית. **READ IN CODE**.
- **"איפה בודקים את הקלט, ולמה פעמיים?"** — ב-frontend רק את `?soil=` (`services/frontend/src/lib/simulation.ts:7-16`), כדי לא לשלוח בקשה שבטוח תיכשל. ב-planner ה-FastAPI בודק `plot_id` כ-UUID, `days` בין 1 ל-7 ו-`initial_soil_water_pct` בין 0 ל-100 (`routers/plan.py:24-28`), ומחזיר 422 VALIDATION (`main.py:43-47`). ה-planner הוא הגבול האמיתי; ה-frontend רק חוסך קריאה. **READ IN CODE**.
- **"למה בדיקת עונה פעמיים?"** — הבדיקה המוקדמת (`routers/plan.py:39-40`) חוסכת קריאות לחלקה שבטוח מחוץ לעונה. ה-planner עוד לא יודע מה התאריך המקומי בשדה, רק את תאריך ה-UTC, ולכן הוא דוחה רק אם התוכנית מחוץ לעונה ביום לפני, באותו יום וביום אחרי. הבדיקה הסופית היא במנוע, לפי תאריכי התחזית, שהם התאריכים המקומיים בשדה (JL-020). **READ IN CODE + MEASURED בטסטים**.

### State

- **"איפה יש state?"** — ב-DB של ה-registry (חוות, חלקות, קטלוגים), וב-dict בזיכרון של תהליך ה-weather (`services/weather-service/cache.py:58-72`). ה-planner וה-frontend בלי state. **READ IN CODE**.
- **"מה הולך לאיבוד ב-restart?"** — ה-cache של ה-weather. הבקשה הבאה לכל תא פונה שוב ל-Open-Meteo, ואם הוא למטה באותו רגע, אין stale להגיש ומקבלים 503. המשימה אומרת במפורש שזה בסדר. **READ IN CODE**.
- **"משהו גדל בלי גבול?"** — ה-cache שומר רשומה אחת לכל תא שאי פעם נשאל, בלי מחיקה. בפועל המספר קטן (כמה תאים לחוות), אבל אין eviction. **REASONED**.

### כשלים

- **"מה קורה כשה-weather למטה?"** — ה-planner מקבל `ConnectError`, מחזיר 503 עם weather-service, ה-frontend מציג "No plan right now. weather-service is unavailable or did not answer in time. Try again in a minute." (`services/frontend/src/components/plan-error.tsx:26-28`). שורת הסטטוס מראה weather down. 17 מקרים בטסטים (`services/planner-service/tests/test_plan.py:299-327`). **READ IN CODE + MEASURED בטסטים**.
- **"מה קורה כשה-planner למטה?"** — `fetch` נכשל, ו-`getPlan` מחזיר `PLANNER_UNREACHABLE` (`services/frontend/src/lib/planner.ts:24-26`), שמוצג כ-"No plan right now. planner-service is unavailable." **READ IN CODE**.
- **"גידול שה-planner לא מכיר?"** — 500 בכוונה (`services/planner-service/tests/test_plan.py:354`). זה באג (ה-planner וה-registry לא מסכימים על הקטלוג), לא מצב שמסתירים עם Kc מומצא. **MEASURED בטסט**.
- **"קרקע או טפטפת שמחזירות 404, למה 503 ולא 404?"** — בגלל ה-foreign keys, ה-registry לא יכול להחזיק חלקה שמפנה לקרקע שלא קיימת. אם הוא אומר שהיא חסרה, ה-registry שבור, לא הבקשה (`upstream.py:79`). **READ IN CODE**.
- **"איפה הלוגים?"** — כל שירות כותב לטרמינל שבו הוא רץ (stdout/stderr של uvicorn או של Next.js). אין קובץ לוג ואין שמירה. **READ IN CODE**.
- **"סולם ה-timeouts"** — ה-weather מחכה 3 שניות לכל ניסיון מול Open-Meteo, 3 ניסיונות, כלומר בערך 9 שניות במקרה הגרוע לפני stale או 503. ה-planner מחכה ל-weather עד 12 שניות (`services/planner-service/.env.example:12`), יותר מ-9, כדי לא לוותר רגע לפני שמגיעה תשובת stale טובה. ל-registry 3 שניות לכל קריאה (`.env.example:9`). ה-frontend מחכה ל-planner עד 25 שניות (`services/frontend/src/lib/planner.ts:6`), יותר מ-3 × 3 + 12 = 21. הסתייגות: ב-httpx ה-timeout חל על כל שלב בנפרד (חיבור, קריאה), ולכן אלה הערכות למקרה הגרוע ולא הבטחה. **READ IN CODE + REASONED**.

### עומס וכמה מופעים

- **"מה קורה בעומס מקסימלי?"** — ראו Q7 וסעיף 5. בקיצור: קודם איטי (תור), ואז שגיאות מפורשות (503), אף פעם לא מספר שגוי. **MEASURED (התקרה) + REASONED (מה אחריה)**.
- **"אם נריץ כמה מופעים, מה יקרה ואיך הבקשות יתחלקו?"** — ראו סעיף 5.
- **"ה-cache של ה-weather תחת עומס?"** — hit זול: lock קצר על dict. miss: ה-lock שומר רק על ה-dict, לא על הפנייה לספק (`services/weather-service/cache.py:66-72`, `routers/forecast.py:33-53`). לכן כמה בקשות במקביל לאותו תא ריק יפנו כולן ל-Open-Meteo (cache stampede). זה כתוב ב-`services/weather-service/README.md:148-149`. פתרון: lock לכל תא סביב הפנייה (רק בקשה אחת מביאה, השאר מחכות לה), או stale-while-revalidate (מגישים את הישן ומרעננים ברקע). **READ IN CODE**.

### אבטחה

- **"ה-deny rule של Claude על .env הוא בקרת אבטחה?"** — לא. כל תהליך של אותו משתמש יכול לקרוא את הקובץ, וה-agent מריץ פקודות shell. ההגנה האמיתית: סוד של production לא נמצא על מכונה שבה agent מריץ פקודות. גם המשימה אומרת את זה.
- **"הסיסמה של DB הבדיקות כתובה ב-README?"** — בכוונה: זה container זמני שנמחק בסוף, פתוח רק ל-`127.0.0.1:5435` (`services/registry-service/README.md:228`).

### טסטים

- **"ה-fake כתוב על ידך. מה אם הפורמט האמיתי שונה?"** — זו המגבלה של fakes: הם בודקים את ההבנה שלנו את הספק. ה-fake של Open-Meteo נבנה מתשובה אמיתית ונבדק מול ה-API החי פעם אחת (`services/weather-service/tests/conftest.py:37`). וה-provider קפדני: פורמט אחר יחזיר 503, לא נתונים שגויים. אין בדיקת contract מתוזמנת. **READ IN CODE**.

## 4. זרימות

### צד הלקוח: דפדפן ↔ שרת ה-frontend

1. הדפדפן: `GET http://localhost:3000/`. מבחינתו יש שרת אחד.
2. שרת Next.js: ה-root layout (`services/frontend/src/app/layout.tsx:22-41`) והדף (`services/frontend/src/app/page.tsx:7-17`) הם server components: הם רצים רק בשרת.
3. שני גבולות `Suspense` (`layout.tsx:32`, `page.tsx:12`): השרת שולח מיד שלד עם טקסט זמני, וממשיך לחכות לנתונים.
4. במקביל: `getServiceStatus` (`services/frontend/src/lib/health.ts:10-23`) ו-`getFarmsWithPlots` (`services/frontend/src/lib/registry.ts:21-36`).
5. כל חלק שמוכן נשלח לדפדפן בהמשך אותה תשובה (streaming) ומחליף את הטקסט הזמני.
6. לחיצה על חלקה: `<Link href="/plots/{id}">` (`page.tsx:46-47`). זה ניווט בצד הלקוח: הדפדפן מבקש מהשרת רק את התוכן של הדף החדש. ה-layout, ובו שורת הסטטוס, לא מתרנדר מחדש.
7. `PlotContent` (`services/frontend/src/app/plots/[id]/page.tsx:31-58`): `Promise.all` של `getPlot` ו-`getPlan` (שורות 35-38).
8. התשובה: `TodayPanel`, אחר כך `PlanDays`, ותג stale איפה שצריך. בשגיאה: `PlanError` (`services/frontend/src/components/plan-error.tsx`).
9. מה הדפדפן לא רואה: את הכתובות של השירותים, את ה-JSON של ה-planner כמו שהוא (הוא מקבל HTML ו-payload של React), ואף סוד. רק קומפוננטות ה-UI של `popover` ו-`table` ודף השגיאה הם client components (`"use client"`), ואף אחד מהם לא קורא לשירות.

**שגיאות בצד הלקוח:**

- registry למטה בדף הראשי: `FarmList` מציג "Can't load the farms" (`page.tsx:21-27`), והשגיאה נרשמת בטרמינל של Next.js (`registry.ts:33`).
- registry למטה בדף חלקה: `getPlot` מחזיר `null` (`registry.ts:39-46`) והכותרת היא "Plot"; התשובה של ה-planner מסבירה מה קרה.
- planner מחזיר שגיאה: `getPlan` מעביר את `code` ו-`detail` (`planner.ts:32-34`), ו-`PlanError` מתרגם: `UPSTREAM_UNAVAILABLE` → "No plan right now", `PLOT_OUT_OF_SEASON` → "No plan for this plot", `NOT_FOUND` → "Plot not found", `VALIDATION` → "This isn't a valid plot address" (`plan-error.tsx:24-47`).
- planner לא עונה: `PLANNER_UNREACHABLE` (`planner.ts:24-26`). תשובה בפורמט לא צפוי: `UNEXPECTED` (`planner.ts:35-40`).
- כל שגיאה אחרת בזמן רינדור: `error.tsx` מציג "Something went wrong" וכפתור "Try again", בלי stack trace (`services/frontend/src/app/error.tsx`).

### צד השרת: frontend → planner → registry, weather → Open-Meteo

1. `GET /v1/plots/{id}/plan?days=7` (`services/frontend/src/lib/planner.ts:20`), timeout 25 שניות.
2. FastAPI בודק את הקלט (`services/planner-service/routers/plan.py:24-28`). שגיאה → 422 VALIDATION, בלי שום קריאה.
3. `get_plot` → `GET /v1/plots/{id}` (`services/planner-service/upstream.py:57-75`). 404 → `PlotNotFound` → 404 NOT_FOUND. כל שדה נבדק; מספרים מומרים פעם אחת ל-`Fraction(str(v))`.
4. `crop_profile` ובדיקת עונה מוקדמת (`routers/plan.py:36-40`). מחוץ לעונה בוודאות → 409 PLOT_OUT_OF_SEASON, בלי קריאות נוספות.
5. `GET /v1/soils/{id}` ו-`GET /v1/emitters/{id}` (`routers/plan.py:43-44`, `upstream.py:78-93`).
6. `GET /v1/forecast?lat&lon&days` (`routers/plan.py:45`, `upstream.py:99-120`), timeout 12 שניות. בודק `stale` בוליאני, בדיוק `days` ימים, ברצף.
7. ב-weather (`services/weather-service/routers/forecast.py:22-55`): תא רשת → תחזית טרייה (פחות מ-3 שעות) שמכסה את הימים? תשובה מה-cache. אחרת `fetch_forecast` (`services/weather-service/provider.py:25-36`): עד 3 ניסיונות למרכז התא, 3 שניות כל אחד, בלי המתנה ביניהם. הצליח → נשמר ב-cache ומוחזר. נכשל → תחזית שמורה עד 24 שעות שמכסה את הימים → 200 עם `stale: true`; אחרת → 503 UNAVAILABLE עם `Retry-After: 60` (`services/weather-service/main.py:49-56`).
8. ה-planner: `engine.plan_days` (`routers/plan.py:48-60`), כולל בדיקת העונה הסופית לפי תאריכי התחזית. עיגול half-up רק בתשובה (`routers/plan.py:63-84`).
9. 200 חוזר ל-frontend.

**שגיאות בצד השרת:**

| מה קרה | מי מבחין | מה עולה למעלה | מה החקלאי רואה | איפה הפרט |
|---|---|---|---|---|
| days=8, UUID לא תקין | FastAPI ב-planner | 422 VALIDATION | "This isn't a valid plot address" (רק UUID; `days` קבוע ב-frontend) | גוף התשובה |
| חלקה לא קיימת | `get_plot` | 404 NOT_FOUND | "Plot not found" | — |
| חלקה מחוץ לעונה | `definitely_out_of_season` או המנוע | 409 PLOT_OUT_OF_SEASON | "No plan for this plot" | — |
| registry למטה, איטי מ-3 שניות, status אחר, JSON לא תקין, שדה חסר או שגוי | `send` / `json_body` / `get_plot` | 503 UPSTREAM_UNAVAILABLE, registry-service | "No plan right now… Try again in a minute." | לוג ה-planner: `Upstream failure: registry-service: …` |
| Open-Meteo למטה ואין תחזית שמורה עד 24 שעות | weather | weather: 503 UNAVAILABLE; planner: 503 UPSTREAM_UNAVAILABLE, weather-service | "No plan right now" | לוג ה-weather (3 ניסיונות) ולוג ה-planner (`status 503`) |
| Open-Meteo למטה ויש תחזית עד 24 שעות | weather | 200, `stale: true` בכל יום | תג "Stale forecast" והודעה עם זמן התחזית | לוג ה-weather |
| גידול לא מוכר | `crop_profile` | 500 | "No plan right now… unexpected error (HTTP 500)" | traceback בלוג ה-planner |

## 5. תחת עומס

- **מה נמדד (MEASURED, מהמסמכים):** p95 ב-10 בקשות לשנייה: registry PostgreSQL ‏14.51 ms, registry SQLite ‏10.95 ms, weather מה-cache ‏8.73 ms (סקריפטים רשמיים); planner ‏26.60 ms, דף חלקה 42.47 ms (oha). התקרה (oha על ה-planner): עד 200 בקשות לשנייה p95 מתחת ל-30 ms; ב-400 שביקשנו, בערך 320 לשנייה ו-p95 של בערך 4 שניות.
- **מה לא נמדד:** איזה hop נרווה ראשון; זמנים לפי חלק בדף החלקה; מסלול הכשל של הספק תחת עומס; registry ב-EC2.
- **מגבלות המקביליות (READ IN CODE):** כל שירות Python הוא תהליך uvicorn אחד (בלי `--workers`). ה-endpoints הם `def` רגיל, ולכן FastAPI מריץ אותם ב-thread pool של AnyIO, 40 threads לתהליך. כל תוכנית תופסת thread ב-planner לכל אורך 4 הקריאות. ה-pool של PostgreSQL ב-registry הוא ברירת המחדל של SQLAlchemy: 5 חיבורים ועוד 10 זמניים, המתנה עד 30 שניות (`services/registry-service/db.py:106-111` לא משנה אותם). SQLite: חיבור חדש לכל בקשה (JL-002).
- **בעומס יתר (REASONED):** בקשות מחכות בתור ל-thread פנוי. כשקריאה ל-registry מחכה יותר מ-3 שניות, ה-planner מחזיר 503 UPSTREAM_UNAVAILABLE. כלומר: קודם איטי, ואז שגיאה מפורשת. אין rate limiting על ה-API שלנו.
- **כמה מופעים מאחורי load balancer (REASONED):** היום יש מופע אחד מכל שירות ואין load balancer (שער אחד מקדימה שמחלק בקשות בין עותקים). עם load balancer (round robin, או least connections, ועם `/health` כדי להוציא מופע מת):
  - planner ו-frontend: בלי state, מתרחבים בלי בעיה.
  - registry על PostgreSQL: מתרחב, אבל כל מופע פותח pool משלו (עד 15 חיבורים), ולכן צריך לשים לב ל-`max_connections` של PostgreSQL, אולי PgBouncer. SQLite אי אפשר לשתף בין מכונות.
  - weather: עובד, אבל ה-cache נהיה נפרד לכל מופע. כל מופע שומר עותק משלו (בזבוז זיכרון), פונה בעצמו ל-Open-Meteo (יותר קריאות), ויכול לענות אחרת (מופע אחד stale, אחר 503).
  - **התשובה שהסוקרים חיפשו:** להוציא את ה-cache מהמופעים ל-cache חיצוני משותף שמנוהל במערכת משלו (למשל Redis), עם מפתח לפי תא רשת. כל המופעים קוראים וכותבים לאותו מקום. חלופה: ניתוב לפי תא, כך שכל תא תמיד מגיע לאותו מופע.
- **cache stampede (READ IN CODE):** ה-lock סביב ה-dict בלבד (`services/weather-service/cache.py:66-72`). כמה בקשות במקביל לתא ריק פונות כולן ל-Open-Meteo. מתועד ב-`services/weather-service/README.md:148-149`.
- **בזמן תקלה של הספק (REASONED):** אין negative caching, אז כל בקשה ל-cache לא טרי מנסה 3 פעמים, עד כ-9 שניות, ותופסת thread כל הזמן הזה, גם ב-weather וגם ב-planner.

## 6. מילון

- **API** — הדרך שבה תוכנה אחת מבקשת משהו מתוכנה אחרת. אצלנו: כתובות HTTP שמחזירות JSON.
- **endpoint** — כתובת אחת ב-API, למשל `GET /v1/forecast`.
- **HTTP status** — מספר בתשובה שאומר מה קרה: 200 הצליח, 404 לא נמצא, 409 התנגשות עם מצב הנתונים, 422 קלט לא תקין, 500 באג בשרת, 503 "לא יכול לענות עכשיו בגלל תלות".
- **port** — מספר שדרכו תהליך מקבל חיבורים. 3000 frontend, 8000 registry, 8001 weather, 8002 planner, 5436 PostgreSQL.
- **process (תהליך)** — תוכנה אחת שרצה במחשב. כל שירות שלנו הוא תהליך uvicorn אחד.
- **instance (מופע/עותק)** — עוד עותק של אותו שירות שרץ במקביל.
- **load balancer** — שער אחד מקדימה שמחלק בקשות בין כמה עותקים. אצלנו אין.
- **timeout** — כמה זמן מחכים לתשובה לפני שמוותרים.
- **retry** — ניסיון חוזר אחרי כשל.
- **backoff** — המתנה שגדלה בין ניסיונות חוזרים.
- **cache** — זיכרון של תשובות קודמות, כדי לא לשאול שוב.
- **fresh / stale** — תחזית טרייה: פחות מ-3 שעות. stale: ישנה, מוגשת רק כשהספק נכשל, עד 24 שעות.
- **grid cell (תא רשת)** — ריבוע של 0.1° על 0.1°, בערך 11 על 9.5 ק"מ בישראל. כל הנקודות בו חולקות תחזית אחת.
- **cache stampede** — הרבה בקשות במקביל ל-cache ריק, וכולן פונות לספק.
- **negative caching** — לזכור שהספק נכשל, כדי לא לנסות שוב מיד.
- **rate limit** — מגבלה של הספק על מספר הקריאות בזמן נתון.
- **429 Too Many Requests** — התשובה של ספק כשעוברים את המגבלה.
- **liveness / readiness** — liveness: התהליך חי ועונה. readiness: הוא גם מוכן לעבוד, כלומר התלויות שלו עובדות.
- **p95** — 95 מכל 100 בקשות הסתיימו בזמן הזה או מהר יותר.
- **hop** — מעבר אחד של בקשה בין שני רכיבים.
- **saturation (רוויה)** — רכיב לא מספיק לטפל בכל הבקשות, והן נכנסות לתור.
- **bottleneck (צוואר בקבוק)** — הרכיב הראשון שנרווה.
- **thread pool** — קבוצה קבועה של threads שמריצה endpoints רגילים (`def`). ב-FastAPI: 40.
- **connection pool** — חיבורים פתוחים ל-DB שנשמרים ומשמשים שוב, כדי לא לפתוח חיבור חדש בכל בקשה.
- **oha** — כלי שורת פקודה ששולח עומס HTTP ומודד זמני תגובה.
- **loopback** — תקשורת בתוך אותו מחשב (127.0.0.1), בלי רשת אמיתית.
- **server component** — קומפוננטת React שרצה רק בשרת. הדפדפן מקבל את התוצאה, לא את הקוד.
- **client component** — קומפוננטה שרצה גם בדפדפן (`"use client"`).
- **layout** — מסגרת משותפת לכמה דפים ב-Next.js. לא מתרנדרת מחדש בניווט בין הדפים.
- **Suspense** — רכיב של React שמציג טקסט זמני עד שהחלק האיטי מוכן, ואז מחליף אותו.
- **streaming** — השרת שולח את הדף בחלקים, לפי הסדר שבו הם מוכנים.
- **Promise.all** — ב-JavaScript: מריץ כמה פעולות במקביל ומחכה שכולן יסתיימו.
- **`server-only`** — חבילה שגורמת ל-build להיכשל אם קוד של השרת מגיע לדפדפן.
- **`.env`** — קובץ הגדרות מקומי עם סודות. לא נכנס ל-git.
- **SecretStr** — טיפוס של pydantic שמדפיס כוכביות במקום הערך.
- **bound parameters** — הערכים נשלחים ל-DB בנפרד מטקסט ה-SQL. מונע SQL injection.
- **`hide_parameters`** — הגדרה של SQLAlchemy: שגיאת DB לא מדפיסה את הערכים.
- **TLS** — הצפנה של התעבורה (מה שהופך http ל-https).
- **authentication** — זיהוי מי שולח את הבקשה (התחברות).
- **superuser** — משתמש DB עם כל ההרשאות.
- **secrets manager** — שירות ששומר סודות ומחלק אותם לשירותים, במקום קבצי `.env`.
- **dependency (ב-FastAPI)** — פונקציה ש-FastAPI קורא לה לפני ה-endpoint ומעביר לו את התוצאה. טסט יכול להחליף אותה.
- **TestClient** — מריץ את אפליקציית FastAPI בתוך הטסט, בלי שרת ובלי רשת.
- **fake** — מימוש פשוט ומזויף של שירות, שעונה כמו המקורי.
- **MockTransport** — מחליף את השכבה התחתונה של ה-HTTP client בפונקציה שלנו שמחזירה תשובה.
- **branch coverage** — אחוז הענפים (כל צד של כל `if`) שהטסטים עברו בהם.
- **contract test** — טסט שבודק שהספק והלקוח מסכימים על פורמט התשובה.
- **end-to-end test** — טסט שמריץ את כל השירותים האמיתיים יחד.
- **CI** — הרצה אוטומטית של בדיקות על כל pull request.
- **verification / validation** — verification: בנינו נכון, לפי ה-spec. validation: בנינו את הדבר הנכון לבעיה האמיתית.
- **ET0** — כמה מים (מ"מ) מאבד משטח דשא סטנדרטי ביום.
- **Kc** — מקדם הגידול: מכפיל את ET0 לפי הגידול והשלב שלו.
- **TAW / הדלי** — כמה מים הקרקע מחזיקה באזור השורשים. כשהרמה הייתה יורדת מתחת לחצי, משקים.
- **Fraction** — מספר רציונלי מדויק ב-Python (למשל 2/5), בלי שגיאות עיגול של float.
- **round half-up** — עיגול שבו .5 תמיד עולה. `round()` של Python מעגל לזוגי, ולכן יש פונקציה משלנו.

## 7. פערים ידועים, בכנות

- אין טסט end-to-end שמריץ את השירותים האמיתיים יחד, ואין contract tests.
- CI יש רק ל-registry. ל-weather, planner ו-frontend אין.
- ל-frontend אין טסטים אוטומטיים. FR-2.15 עד FR-2.19 ו-NFR-2.8 נבדקו ידנית בלבד.
- אין טסט שמשנה בדיוק `lat` ל-`latitude` (המסלול נבדק עם שדה חסר אחר).
- ה-frontend קורא את ה-registry בלי בדיקה בזמן ריצה (`registry.ts:17`).
- `/health` הוא liveness בלבד; אין readiness.
- ה-weather: אין טיפול ב-429, אין backoff, אין negative caching, אין הגנה מ-cache stampede, אין eviction.
- איזה hop נרווה ראשון לא נמדד. כל המדידות על לפטופ דרך loopback.
- אין authentication, אין TLS, משתמש DB superuser, אין secrets manager, `next dev` מאזין ל-`0.0.0.0`.
- התוכנית מתחילה מדלי מלא (JL-011), כי אין חיישן לחות. אם הקרקע יבשה, התוכנית יכולה לומר "No irrigation today" כשצריך מים. התוכנית לא הושוותה לנתוני שדה.
- רק ה-registry נפרס ל-EC2, מ-`main`. weather, planner ו-frontend רצים מקומית. ה-PR של P2 עוד לא נפתח, אז ה-CI עוד לא רץ על שינויי `p2`.
- **טעות בהערות של המצגת הקודמת:** בהערות של שקף 12 ב-`P2-slides.pptx` כתוב שה-frontend קורא ל-planner ואחר כך ל-registry, בזה אחר זה, ושזה מסביר את 42 ms. זה לא נכון: הקוד מריץ את שתי הקריאות במקביל עם `Promise.all` (`services/frontend/src/app/plots/[id]/page.tsx:35-38`). במצגת החדשה זה מתוקן.
- **טעות קטנה בשקף 9 של המצגת הקודמת:** כתוב "One test advances time and checks every cache boundary". בפועל אלה כמה טסטים נפרדים (2:59, 3:00, 24 שעות, 24 שעות ושנייה).

## 8. מבנה המצגת (outline)

| שקף | שאלת סקירה | כותרת | הוויזואל | מה צריך לדעת להסביר |
|---|---|---|---|---|
| 1 | — | Should I water this plot today, and for how many minutes? | שתי שורות: מה היה ב-P1, מה נוסף ב-P2 | איפה P2 בקורס; מה כל רכיב חדש עושה |
| 2 | רקע ל-Q2, Q3, Q5 | Four services talk over HTTP; only the planner calculates | ארכיטקטורה: רכיבים, פורטים, חצים; P2 מודגש, P1 באפור | מי קורא למי ולמה; מה כל שירות בכוונה לא יודע |
| 3 | Q2 | The browser talks only to the frontend server, not to the services | שלוש עמודות: דפדפן, שרת frontend, שירותים; שלוש שורות | מה רץ בשרת ומה בדפדפן; Suspense; Promise.all; מתי שורת הסטטוס רצה |
| 4 | Q3 | A plan takes four calls in a fixed order; each answer is checked | דיאגרמת רצף ממוספרת 1–8 | הסדר; בדיקת העונה הכפולה; למה Fraction ועיגול רק בסוף |
| 5 | Q3 (שגיאות), Q5 | When a service fails, the grower gets a clear error, never zeros | טבלה: מה נכשל, מה ה-planner מחזיר, מה החקלאי רואה | 503 עם שם השירות; KeyError('lat'); למה לא (0,0); 409 מחוץ לעונה; סולם ה-timeouts |
| 6 | Q4 (למה), Q8 | One service calls Open-Meteo; its cache keeps the calls low | תרשים החלטות של ה-cache | למה לא מהדפדפן; ~8 קריאות לתא ביום; מה לא מטופל (429, backoff, stampede) |
| 7 | Q4 (טסטים), Q6 | Tests replace only the network; the real app runs above the fakes | ערימת שכבות: טסט, אפליקציה אמיתית, HTTP client, fake | MockTransport; שעון מוזרק; בדיקה של קריאות שלא נעשו; מה coverage לא אומר |
| 8 | Q1 | Three secrets and the growers' data, kept out of git and logs | טבלה של 4 שורות | איפה כל סוד, איך הוא מוגן, מה עוד חסר |
| 9 | Q7 | Every hop is far under 100 ms; the ceiling is about 320 plans/s | ארבעה פסים של p95 מול יעד של 100 ms; שורה על עומס יתר ושורה על כמה עותקים | מה נמדד ואיך; מה קורה מעל התקרה; מה קורה עם כמה מופעים ו-cache משותף |
| 10 | Q9 | Every requirement is checked; the frontend's only by hand | טבלה: קבוצת דרישות והבדיקה שלה; צעדים הבאים; Questions | verification מול validation; מה הייתי עושה קודם |

</div>
