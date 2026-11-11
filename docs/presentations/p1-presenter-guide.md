# AgroPilot P1 — מדריך הצגה ל־Zoom (10 דקות)

**תכלית:** מדריך פרטי למציג, לא למסך המשותף. כל הטקסט המוצג בשקופיות הוא באנגלית בלבד; הערות הדובר בתוך המצגת ומדריך זה הם בעברית, ותוכנם זהה. יש להציג ב־Zoom רק את השקופיות, ולא את ההערות הפרטיות.

## מבנה ההצגה

<div dir="rtl">

| שקופית | נושא | זמן |
|---|---|---|
| 1 | פתיחה | 00:00–00:45 |
| 2 | מבנה הנתונים | 00:45–02:00 |
| 3 | ארכיטקטורה | 02:00–03:30 |
| 4 | Live Demo | 03:30–07:00 |
| 5 | Testing &amp; Performance | 07:00–08:30 |
| 6 | Bonus — Load Test | **אופציונלי**, מחוץ ל־10 הדקות |
| 7 | Questions &amp; Code Walkthrough | 08:30–10:00 |

ההצגה עצמה היא 10 דקות. את שקופית 6 מציגים רק אם נשאר זמן או אם המרצה שואל על עומס. כדי לדלג עליה בזמן ההצגה: מקלידים <code dir="ltr">7</code> ולוחצים Enter, ו־PowerPoint קופץ ישר לשקופית 7.

</div>

## לפני ההצגה — 5 דקות הכנה

- פתח VS Code בתיקיית `services/registry-service` של גרסת P1 היציבה. אם אתה עדיין עובד על Branch של PostgreSQL, ודא שאתה מדגים את גרסת SQLite שכבר נבדקה, בלי לדרוס שינויים פעילים.
- פתח שני Terminals (אחד לשרת, אחד ל־curl) ודפדפן על `http://127.0.0.1:8000/docs`.
- בדוק שהסביבה מוכנה; `uv sync` אם צריך. **אל תריץ `bash seed_registry.sh` באופן אוטומטי**: הוא מוחק את `registry.db` הקיים ומשחזר נתוני Seed. להריץ רק מראש אם באמת רוצים לאפס את סביבת ההדגמה.
- ב־Zoom שתף את חלון המצגת או חלון ההדגמה בלבד, לא את המסך כולו אם ההערות פרטיות. אם יש רק מסך אחד, פתח את הדף הזה בטלפון.
- אם השרת כבר עובד על פורט 8000, אל תפעיל מופע נוסף על אותו פורט.

## שקופית 1 — פתיחה (00:00–00:45)

**מה לומר:**
"ב־P1 בניתי Registry Service עבור AgroPilot.
זה שירות Backend שמנהל מידע על חוות חקלאיות והחלקות שלהן, וגם קטלוגים של גידולים, סוגי קרקע וטפטפות.
הרעיון הוא לרכז את המידע במקום אחד ולאפשר למערכות אחרות לגשת אליו דרך API מסודר, במקום שכל מערכת תצטרך לנהל עותק משלה של הנתונים או לעבוד מול קבצים שמעבירים ידנית.
השירות מאפשר לשלוף מידע, להוסיף חוות וחלקות, לעדכן ולמחוק אותן."

**מעבר לשקף הבא:** "נתחיל ממבנה הנתונים ונראה איך הם קשורים אחד לשני."

## שקופית 2 — מבנה הנתונים (00:45–02:00)

**מה לומר:**
"ה־API שבניתי מחולק לשלושה תחומים עיקריים.
הראשון הוא Farms — ניהול חוות חקלאיות. השני הוא Plots — ניהול החלקות ששייכות ל-farms.
בשניהם יש מימוש של פעולות CRUD, כלומר אפשר ליצור, לשלוף, לעדכן ולמחוק רשומות.
התחום השלישי הוא הקטלוגים: גידולים, סוגי קרקע וטפטפות. כאן אפשר לבצע פעולות קריאה בלבד."

**מעבר לשקף הבא:** "עכשיו אראה איך בניתי את השירות ואיך בקשה עוברת בין השכבות שלו."

## שקופית 3 — ארכיטקטורה (02:00–03:30)

**מה לומר:**
בקצרה איך המערכת בנויה ואיך בקשה עוברת בין השכבות.
ניקח לדוגמה בקשת GET בשביל לקבל את רשימת הטפטפות.
יש לקוח שמבצע בקשה, אצלנו נראה את זה עוד מעט דרך curl או Swagger UI.
הבקשה מגיעה ל־FastAPI, שמנתב אותה ל־Router המתאים. ה־Router מפעיל פונקציה ב־Repository, שאחראית לשלוף את המידע מה־Database.
ה־Repository משתמש בחיבור שמספק db.py, ומריץ שאילתת SQL מול SQLite.
התוצאות חוזרות ל־Router, ו־FastAPI מחזיר ללקוח תשובה בפורמט JSON, עם סטטוס 200 כשהבקשה הצליחה.
בסיום הבקשה, החיבור ל־Database נסגר."

**הערה למקרה ששואלים על הפרדת השכבות:** "ההפרדה בין ה־Routers ל־Repositories עוזרת לשמור על קוד מסודר, שקל יותר לשנות ולתחזק."

**מעבר לשקף הבא:** "עכשיו נעבור להדגמה חיה ונראה את השירות עובד בפועל."

## שקופית 4 — Live Demo (03:30–07:00)

**פתיחה:** "עכשיו נעבור להדגמה קצרה של ה־API. נראה איך מפעילים את השירות, שולפים נתונים, יוצרים חווה חדשה ואיך המערכת מטפלת בשגיאות."

**1. הפעלת השרת** — מתוך `services/registry-service`:

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

מה לומר: "אני מפעיל את השירות באמצעות Uvicorn, שמריץ את אפליקציית FastAPI שלנו בפורט 8000."
להשאיר את השרת פועל ולפתוח Terminal נוסף.

**2. Health Check**

```bash
curl -i http://127.0.0.1:8000/health
```

מה לומר: "קודם נבדוק שהשירות פועל ומגיב לבקשות. אני שולח בקשת GET ל־Health Endpoint."
תוצאה צפויה: `200 OK` ו־`{"status":"ok"}`.

**3. שליפת קטלוג הטפטפות**

```bash
curl -i http://127.0.0.1:8000/v1/emitters
```

מה לומר: "עכשיו אני שולף את רשימת הטפטפות מהמערכת. בתשובה אנחנו מקבלים JSON עם המזהה, השם והספיקה של כל טפטפת."
תוצאה צפויה: `200 OK` ורשימה של ארבע טפטפות.

**4. יצירת חווה חדשה**

```bash
curl -i -X POST http://127.0.0.1:8000/v1/farms -H 'Content-Type: application/json' -d '{"name":"Presentation Demo Farm"}'
```

מה לומר: "עד עכשיו שלפנו נתונים. עכשיו אני שולח בקשת POST כדי ליצור חווה חדשה. בגוף הבקשה אני מעביר JSON שמכיל את שם החווה."
תוצאה צפויה: `201 Created`, יחד עם שם החווה ו־UUID חדש.
"אנחנו רואים שהחווה נוצרה וקיבלה מזהה ייחודי."

**5. טיפול בשגיאות**

```bash
curl -i http://127.0.0.1:8000/v1/crops/unknown
```

מה לומר: "לסיום, אני מבקש גידול עם מזהה שלא קיים במערכת, כדי להראות איך ה־API מטפל בבקשה כזאת."
תוצאה צפויה: `404 Not Found` ו־`{"detail":"Crop not found"}`.

**מעבר לשקף הבא:** "ראינו כמה פעולות בסיסיות של ה־API. עכשיו נעבור לבדיקות שביצעתי ולמדידת הביצועים."

### דף עזר — אם מבקשים הדגמה נוספת

Swagger UI: `http://127.0.0.1:8000/docs`

| מה | פקודה |
|---|---|
| רשימת חוות | `curl -i http://127.0.0.1:8000/v1/farms` |
| טפטפת לפי ID | `curl -i http://127.0.0.1:8000/v1/emitters/dripnet-pc-1.0` |
| גידול לפי ID | `curl -i http://127.0.0.1:8000/v1/crops/tomato` |
| סוג קרקע לפי ID | `curl -i http://127.0.0.1:8000/v1/soils/loam` |
| רשימת חלקות | `curl -i http://127.0.0.1:8000/v1/plots` |
| חלקות של חווה מסוימת | `curl -i "http://127.0.0.1:8000/v1/plots?farm_id=b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001"` |

**בדיקת Validation — שם חווה ריק:**

```bash
curl -i -X POST http://127.0.0.1:8000/v1/farms -H 'Content-Type: application/json' -d '{"name":""}'
```

תוצאה צפויה: `422 Unprocessable Entity`.

**IDs מוכנים ל־Swagger:**

| Resource | ID |
|---|---|
| Farm | `b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001` |
| Plot | `c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002` |
| Crop | `tomato` |
| Soil | `loam` |
| Emitter | `dripnet-pc-1.0` |

המזהים האלה מגיעים מנתוני ה־Seed, בהנחה שהרשומות עדיין קיימות.

## Command Reference — Understanding the Live Demo

<div dir="rtl">

כל פקודה מההדגמה: מה היא עושה, ממה היא מורכבת, מה קורה מאחורי הקלעים, ותשובה קצרה אם שואלים. כל הפקודות רצות מתוך <code dir="ltr">services/registry-service</code>.

### 1. הפעלת השרת

<div dir="ltr">

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

</div>

**מה זה עושה:** מפעיל שרת HTTP שמריץ את אפליקציית ה־FastAPI שלנו ומחכה לבקשות בכתובת <code dir="ltr">http://127.0.0.1:8000</code>.

**פירוק:**

- <code dir="ltr">uv</code> — כלי שמנהל את הפרויקט ב־Python: גרסת Python, התלויות (<code dir="ltr">pyproject.toml</code> ו־<code dir="ltr">uv.lock</code>) וה־virtual environment.
- <code dir="ltr">uv run</code> — מריץ פקודה בתוך ה־virtual environment של הפרויקט, התיקייה <code dir="ltr">.venv</code>. לפני ההרצה הוא מוודא שה־<code dir="ltr">.venv</code> תואם ל־<code dir="ltr">uv.lock</code>. כך <code dir="ltr">uvicorn</code> ו־<code dir="ltr">fastapi</code> נטענים מהגרסאות הנעולות של הפרויקט, ולא ממה שמותקן במחשב באופן כללי.
- <code dir="ltr">uvicorn</code> — שרת ASGI. FastAPI לא מאזין לרשת בעצמו; הוא רק "יודע מה לענות". Uvicorn פותח את החיבור לרשת, קורא את בקשת ה־HTTP, מעביר אותה ל־FastAPI ושולח בחזרה את התשובה. ASGI הוא הסטנדרט שמגדיר איך שרת ואפליקציה ב־Python מדברים זה עם זה.
- <code dir="ltr">main:app</code> — "איפה האפליקציה". <code dir="ltr">main</code> הוא המודול <code dir="ltr">main.py</code> (בלי <code dir="ltr">.py</code>), ו־<code dir="ltr">app</code> הוא האובייקט שנוצר בו: <code dir="ltr">app = FastAPI(...)</code>. הנקודתיים מפרידות בין שם המודול לבין שם המשתנה שבתוכו, כי נקודה כבר משמשת לנתיב מודולים (למשל <code dir="ltr">package.module:app</code>). זה עובד רק כשמריצים מתוך <code dir="ltr">services/registry-service</code>, כי השירות לא מותקן כ־package.
- <code dir="ltr">--host 127.0.0.1</code> — כתובת ה־IP שהשרת מאזין עליה. <code dir="ltr">127.0.0.1</code> היא כתובת ה־loopback, שנקראת גם localhost: כתובת שתמיד מצביעה על המחשב עצמו, והתעבורה לא יוצאת ממנו. לכן רק תוכנות במחשב שלי יכולות לפנות לשרת.
- <code dir="ltr">--port 8000</code> — מספר הפורט. ה־IP מזהה את המחשב, והפורט מזהה איזו תוכנה במחשב מקבלת את התעבורה. כמו כתובת בניין ומספר דירה.

**"השרת מאזין על IP ופורט"** — השרת תופס את הצירוף <code dir="ltr">127.0.0.1:8000</code> ומחכה לחיבורים. כל חיבור שמגיע לכתובת הזאת עובר אליו. לכן אי אפשר להפעיל שני שרתים על אותו פורט.

**מה קורה כשמגיעה בקשה:**

1. Uvicorn מקבל את החיבור וקורא את בקשת ה־HTTP: method, path, headers ו־body.
2. הוא מעביר אותה ל־FastAPI, שמוצא את ה־route המתאים לפי ה־method וה־path.
3. FastAPI מריץ את ה־dependencies (למשל <code dir="ltr">get_db</code> שפותח חיבור ל־SQLite) ואז את הפונקציה של ה־route.
4. התוצאה הופכת ל־JSON, ו־Uvicorn שולח אותה בחזרה ללקוח.
5. בטרמינל של השרת מופיעה שורה לכל בקשה, למשל:

<div dir="ltr">

```text
INFO:     127.0.0.1:64540 - "POST /v1/farms HTTP/1.1" 201 Created
```

</div>

אם מופיעה הודעת <code dir="ltr">warning: VIRTUAL_ENV=... does not match the project environment path .venv</code> — זה לא מזיק. ב־Terminal פעיל virtual environment של פרויקט אחר, ו־<code dir="ltr">uv</code> מתעלם ממנו ומשתמש ב־<code dir="ltr">.venv</code> של השירות.

**אם שואלים:** "Uvicorn הוא השרת שמקבל את בקשות ה־HTTP מהרשת ומעביר אותן לאפליקציית FastAPI. <code dir="ltr">main:app</code> אומר לו לטעון את האובייקט <code dir="ltr">app</code> מהקובץ <code dir="ltr">main.py</code>. הוא מאזין על localhost בפורט 8000, כך שרק המחשב שלי יכול לגשת אליו."

### 2. בקשות HTTP עם curl

<div dir="ltr">

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/v1/emitters
```

</div>

**מה זה עושה:** שולח בקשת HTTP לשרת ומדפיס את התשובה.

**פירוק:**

- <code dir="ltr">curl</code> — לקוח HTTP בשורת הפקודה. כמו דפדפן בלי ממשק: שולח בקשה ומציג את מה שחזר.
- <code dir="ltr">-i</code> — מציג גם את שורת הסטטוס וה־headers של התשובה, ולא רק את ה־body.

**ממה מורכבות בקשה ותשובה:**

| בקשה (Request) | תשובה (Response) |
|---|---|
| Method — <code dir="ltr">GET</code>, <code dir="ltr">POST</code>, <code dir="ltr">PATCH</code>, <code dir="ltr">DELETE</code> | Status line — <code dir="ltr">HTTP/1.1 200 OK</code> |
| Path — <code dir="ltr">/v1/emitters</code> | Headers — מידע על התשובה |
| Headers — מידע על הבקשה | Body — הנתונים עצמם, אצלנו JSON |
| Body — רק כשיש מה לשלוח, למשל ב־POST | |

**Method, Path, Route ו־Endpoint:**

- **Method** — הפעולה: <code dir="ltr">GET</code> קורא, <code dir="ltr">POST</code> יוצר, <code dir="ltr">PATCH</code> מעדכן, <code dir="ltr">DELETE</code> מוחק.
- **Path** — הכתובת בתוך השרת: <code dir="ltr">/v1/emitters</code>.
- **Route** — הכלל בקוד שמחבר method ותבנית path לפונקציה, למשל <code dir="ltr">@router.get("/emitters/{emitter_id}")</code> ב־<code dir="ltr">routers/catalogues.py</code>.
- **Endpoint** — מה שהלקוח יכול לקרוא לו: method ביחד עם path, למשל <code dir="ltr">GET /v1/emitters</code>. בפועל משתמשים ב־route וב־endpoint כמעט באותה משמעות: route הוא הצד של הקוד, endpoint הוא הצד של ה־API.

**פירוק ה־URL** <code dir="ltr">http://127.0.0.1:8000/v1/emitters</code>:

| חלק | ערך | משמעות |
|---|---|---|
| Protocol | <code dir="ltr">http</code> | שפת התקשורת |
| Host | <code dir="ltr">127.0.0.1</code> | המחשב — localhost |
| Port | <code dir="ltr">8000</code> | הפורט ש־Uvicorn מאזין עליו |
| Path | <code dir="ltr">/v1/emitters</code> | המשאב המבוקש. <code dir="ltr">v1</code> היא גרסת ה־API |

**<code dir="ltr">GET /health</code>** — מוגדר ישירות ב־<code dir="ltr">main.py</code> ומחזיר <code dir="ltr">{"status":"ok"}</code>. הוא לא נוגע ב־Database, אז הוא מוכיח רק שהשרת חי. פלט אמיתי עם <code dir="ltr">-i</code>:

<div dir="ltr">

```text
HTTP/1.1 200 OK
date: Tue, 10 Nov 2026 23:14:40 GMT
server: uvicorn
content-length: 15
content-type: application/json

{"status":"ok"}
```

</div>

**<code dir="ltr">GET /v1/emitters</code>** — מחזיר את כל הטפטפות. ה־Repository מריץ <code dir="ltr">SELECT id, name, flow_lph FROM emitters</code> ומחזיר רשימה.

**<code dir="ltr">GET /v1/emitters</code> לעומת <code dir="ltr">GET /v1/emitters/{id}</code>:**

- <code dir="ltr">/v1/emitters</code> — רשימה של כל הטפטפות (JSON array).
- <code dir="ltr">/v1/emitters/dripnet-pc-1.0</code> — טפטפת אחת לפי ID (JSON object). <code dir="ltr">{emitter_id}</code> הוא path parameter: FastAPI לוקח את החלק הזה מה־URL ומעביר אותו לפונקציה. אם אין טפטפת כזאת, ה־Repository מחזיר <code dir="ltr">None</code> וה־Router מחזיר <code dir="ltr">404</code> עם <code dir="ltr">{"detail":"Emitter not found"}</code>.

<div dir="ltr">

```text
{"id":"dripnet-pc-1.0","name":"DripNet PC","flow_lph":1.0}
```

</div>

**מה קורה בדרך — <code dir="ltr">GET /v1/emitters</code>:**

1. <code dir="ltr">curl</code> פותח חיבור ל־<code dir="ltr">127.0.0.1:8000</code> ושולח <code dir="ltr">GET /v1/emitters</code>.
2. Uvicorn מקבל את הבקשה ומעביר אותה ל־FastAPI.
3. FastAPI מוצא את <code dir="ltr">list_emitters</code> ב־<code dir="ltr">routers/catalogues.py</code> (ה־prefix של ה־Router הוא <code dir="ltr">/v1</code>).
4. לפני הפונקציה, <code dir="ltr">get_db</code> ב־<code dir="ltr">db.py</code> פותח חיבור ל־SQLite (<code dir="ltr">mode=rw</code>, <code dir="ltr">PRAGMA foreign_keys = ON</code>).
5. ה־Router קורא ל־<code dir="ltr">catalogue_repository.list_emitters(conn)</code>, שמריץ את ה־SELECT ומחזיר רשימת dict.
6. FastAPI בודק את התוצאה מול <code dir="ltr">response_model=list[Emitter]</code>, הופך אותה ל־JSON ומחזיר <code dir="ltr">200</code>.
7. בסיום הבקשה, ה־<code dir="ltr">finally</code> ב־<code dir="ltr">get_db</code> סוגר את החיבור.
8. Uvicorn שולח את התשובה, ו־<code dir="ltr">curl</code> מדפיס אותה.

**אם שואלים:** "curl שולח בקשת HTTP כמו דפדפן, ו־<code dir="ltr">-i</code> מראה גם את ה־headers. הבקשה עוברת מ־Uvicorn ל־FastAPI, ל־Router, ל־Repository שמריץ SQL על SQLite, והתוצאה חוזרת כ־JSON עם סטטוס 200."

### 3. יצירת חווה עם POST

<div dir="ltr">

```bash
curl -i -X POST http://127.0.0.1:8000/v1/farms -H 'Content-Type: application/json' -d '{"name":"Presentation Demo Farm"}'
```

</div>

**פירוק:**

- <code dir="ltr">-X POST</code> — ה־method הוא <code dir="ltr">POST</code>, כלומר יצירה. (כשיש <code dir="ltr">-d</code>, curl שולח <code dir="ltr">POST</code> גם בלי זה; <code dir="ltr">-X POST</code> רק הופך את זה למפורש.)
- <code dir="ltr">-H 'Content-Type: application/json'</code> — header שאומר לשרת שה־body הוא JSON. בלי ה־header הזה ה־API מחזיר <code dir="ltr">422</code>, כי FastAPI לא מפרש את ה־body כ־JSON.
- <code dir="ltr">-d '{"name":"Presentation Demo Farm"}'</code> — ה־request body: הנתונים שנשלחים. הגרשיים הבודדים שומרים על המרכאות הכפולות של ה־JSON, כדי שה־shell לא יפרש אותן.

**מה קורה בצד השרת:**

1. FastAPI בודק את ה־body מול <code dir="ltr">FarmCreate</code> ב־<code dir="ltr">schemas.py</code>: <code dir="ltr">name</code> חובה, לפחות תו אחד, ואסור לשלוח שדות נוספים (<code dir="ltr">extra="forbid"</code>). אם הבדיקה נכשלת — <code dir="ltr">422</code>.
2. ה־Router <code dir="ltr">create_farm</code> ב־<code dir="ltr">routers/farms.py</code> קורא ל־<code dir="ltr">farm_repository.create_farm(conn, body.name)</code>.
3. ה־Repository מייצר את ה־ID בעצמו: <code dir="ltr">str(uuid4())</code>. הלקוח לא שולח ID.
4. <code dir="ltr">INSERT INTO farms</code> רץ בתוך <code dir="ltr">with conn:</code>, כך שהשינוי נשמר (commit) רק אם ההכנסה הצליחה.
5. ה־Repository מחזיר <code dir="ltr">{"id": ..., "name": ...}</code>, ו־FastAPI מחזיר אותו כ־JSON לפי <code dir="ltr">response_model=Farm</code>.

**למה <code dir="ltr">201 Created</code>?** ה־route מוגדר כ־<code dir="ltr">@router.post("", status_code=201, response_model=Farm)</code>. ‏201 אומר "נוצר משאב חדש", ולא סתם "הצליח" כמו 200.

<div dir="ltr">

```text
HTTP/1.1 201 Created
content-type: application/json

{"id":"b4fa93a4-dcad-4002-a1c8-092557564b28","name":"Presentation Demo Farm"}
```

</div>

כל הרצה יוצרת חווה חדשה עם UUID אחר ב־<code dir="ltr">registry.db</code>.

**אם שואלים:** "זו בקשת POST עם body ב־JSON. ה־header <code dir="ltr">Content-Type</code> אומר לשרת לפרש אותו כ־JSON. Pydantic בודק את הקלט, ה־Repository מייצר UUID ושומר את החווה, והשרת מחזיר 201 עם החווה החדשה."

### 4. תשובות ושגיאות

| Status | מתי אצלנו |
|---|---|
| <code dir="ltr">200 OK</code> | בקשה הצליחה, למשל <code dir="ltr">GET /v1/emitters</code> |
| <code dir="ltr">201 Created</code> | נוצר משאב חדש — <code dir="ltr">POST /v1/farms</code> |
| <code dir="ltr">404 Not Found</code> | ה־Repository החזיר <code dir="ltr">None</code>, וה־Router זרק <code dir="ltr">HTTPException</code>, למשל <code dir="ltr">{"detail":"Crop not found"}</code> |
| <code dir="ltr">422 Unprocessable Entity</code> | הקלט לא תקין: Pydantic דחה את ה־body (למשל שם ריק), או שה־Router דחה ערך, כמו crop לא קיים ביצירת plot |

ב־422 של Pydantic ה־<code dir="ltr">detail</code> הוא רשימה שמסבירה מה נכשל ואיפה, למשל <code dir="ltr">"loc":["body","name"]</code> ו־<code dir="ltr">"msg":"String should have at least 1 character"</code>.

**Headers לעומת Body:**

- **Headers** — מידע על התשובה: <code dir="ltr">content-type: application/json</code> (סוג הנתונים), <code dir="ltr">content-length</code> (גודל), <code dir="ltr">date</code>, <code dir="ltr">server: uvicorn</code>.
- **Body** — הנתונים עצמם, ה־JSON. בלי <code dir="ltr">-i</code>, curl מציג רק את ה־body.

**למה Swagger UI ו־curl קוראים לאותו API?** FastAPI מייצר מתוך ה־routes ומודלי ה־Pydantic תיאור של ה־API (OpenAPI, בכתובת <code dir="ltr">/openapi.json</code>). Swagger UI ב־<code dir="ltr">/docs</code> קורא את התיאור הזה ובונה ממנו טפסים. כשלוחצים "Execute", הדפדפן שולח בקשת HTTP אמיתית לאותו שרת, לאותם endpoints ולאותו קוד — בדיוק כמו curl.

**אם שואלים:** "200 הצלחה, 201 נוצר משאב, 404 המשאב לא קיים, 422 הקלט לא תקין. Swagger ו־curl הם שני לקוחות שונים לאותו API."

### 5. פקודות נוספות

<div dir="ltr">

```bash
uv sync
```

</div>

מתקין ל־<code dir="ltr">.venv</code> בדיוק את הגרסאות שב־<code dir="ltr">uv.lock</code>, כולל קבוצת ה־dev (<code dir="ltr">pytest</code>, <code dir="ltr">httpx2</code>). מריצים פעם אחת, או אחרי שינוי בתלויות.

<div dir="ltr">

```bash
bash seed_registry.sh
```

</div>

יוצר את <code dir="ltr">registry.db</code> מחדש: מוחק את הקובץ הקיים (<code dir="ltr">rm -f</code>), יוצר את הטבלאות ומכניס 2 חוות, 4 חלקות והקטלוגים. צריך את כלי ה־<code dir="ltr">sqlite3</code>. **מוחק את כל מה שנוצר קודם**, כולל חוות מההדגמה.

<div dir="ltr">

```bash
uv run pytest -q
```

</div>

מריץ את 171 הבדיקות. <code dir="ltr">-q</code> מקצר את הפלט. כל בדיקה מקבלת קובץ SQLite זמני משלה דרך <code dir="ltr">REGISTRY_DB_PATH</code>, כך ש־<code dir="ltr">registry.db</code> לא נפגע. רוב הבדיקות משתמשות ב־<code dir="ltr">TestClient</code>, שקורא לאפליקציה ישירות בלי רשת. חלקן מפעילות תהליך Uvicorn אמיתי כדי לבדוק בקשות במקביל.

<div dir="ltr">

```bash
uv run python scripts/measure_p95.py
```

</div>

מדידת ביצועים לפי NFR-1.1. הסקריפט יוצר DB זמני, מפעיל Uvicorn משלו, שולח 1,200 בקשות GET בקצב קבוע של 10 בשנייה במשך 120 שניות על 11 נתיבים, ומדפיס p50, p95 ו־max לכל נתיב ובסך הכול, ובסוף <code dir="ltr">PASS</code> או <code dir="ltr">FAIL</code>. הוא לא צריך את השרת מההדגמה ולא נוגע ב־<code dir="ltr">registry.db</code>. ‏<code dir="ltr">--duration 10</code> מאפשר בדיקה מהירה.

**טסטים לעומת מדידת ביצועים:**

- **<code dir="ltr">pytest</code>** בודק **נכונות**: האם התשובות, הסטטוסים והנתונים הם מה שמצפים.
- **<code dir="ltr">measure_p95.py</code>** בודק **מהירות**: כמה זמן לוקחות תשובות GET תחת עומס מוגדר.
- אחד לא מחליף את השני: קוד יכול להיות נכון ואיטי, או מהיר ושגוי.

**אם שואלים:** "pytest מוודא שה־API מתנהג נכון, והסקריפט מודד זמני תגובה תחת עומס קבוע. שניהם עובדים על Database זמני, כך שהם לא משפיעים על נתוני הפיתוח."

</div>

## שקופית 5 — Testing & Performance (07:00–08:30)

**מה לומר:**
"מעבר להדגמה שראינו, כתבתי בדיקות אוטומטיות באמצעות Pytest.
בסך הכול יש לי 171 בדיקות שעוברות, שמכסות את הפעולות המרכזיות ב־API: יצירה, שליפה, עדכון ומחיקה של נתונים, בדיקות Validation, טיפול בשגיאות וגם איך המערכת מתנהגת כשמגיעות כמה בקשות במקביל.
אפשר להריץ את הבדיקות ולראות את התוצאה."

פקודה להרצה (כמה שניות):

```bash
uv run pytest -q
```

תוצאה צפויה: `171 passed`.

**המשך — בדיקות ביצועים:**
"בבדיקת זמני התגובה של בקשות GET, הייתה דרישה לעמוד ב־p95 של עד 100 מילישניות, בקצב של 10 בקשות בשנייה.
(שזה אומר ש־95% מהבקשות נענו בזמן שלא עולה על 10ms.)
בבדיקה של 1,200 בקשות קיבלתי p95 כולל של 9.76 מילישניות. גם בנתיב שבו נמדד ה־p95 הגבוה ביותר, התוצאה הייתה 9.97 מילישניות.
כל הבקשות הצליחו, והתוצאות היו נמוכות משמעותית מהסף שנדרש."

### הערות למקרה שעולות שאלות

| שאלה | תשובה |
|---|---|
| איך הבדיקות עובדות? | הבדיקות שולחות בקשות ל־API ובודקות שהתשובות תואמות למה שאנחנו מצפים לקבל. למשל, שבקשת GET מחזירה את הנתונים הנכונים, או שקלט לא תקין מחזיר 422. |
| איך מבודדים את הבדיקות? | לכל בדיקת API נוצר קובץ SQLite זמני עם נתוני בדיקה. כך כל בדיקה מתחילה מסביבה מוכרת, ואפשר ליצור ולמחוק רשומות בלי להשפיע על הבדיקות האחרות או על נתוני הפיתוח. |
| בדיקת NFR | Non-Functional Requirement — (דרישה שמתארת איכות של המערכת, למשל מהירות תגובה, בניגוד פעולה שהמשתמש מבצע). |
| איך בוצעה מדידת הביצועים? | הסקריפט שלח 1,200 בקשות GET לאורך 120 שניות, בקצב של 10 בקשות בשנייה בסך הכול, על פני 11 נתיבי GET שנבדקו. |
| דגש | זה לא מוכיח שהמערכת מוכנה ל־Production. זו מדידה מקומית של בקשות GET בלבד, בקצב של 10 בקשות בשנייה בסך הכול. לא מדדתי עומס של כתיבות במקביל. |

פקודת ה־Benchmark — סקריפט לבדיקת ביצועים ששולח בקשות ל־API בקצב קבוע ומודד את זמני התגובה. **לא להריץ בהצגה** — היא אורכת 120 שניות:

```bash
uv run python scripts/measure_p95.py
```

## שקופית 6 — Bonus: Load Test (אופציונלי)

<div dir="rtl">

**מתי להציג:** רק אם נשאר זמן, או אם המרצה שואל איך השרת מתנהג תחת עומס. השקופית לא חלק מ־10 הדקות. אם מדלגים — עוברים משקופית 5 ישר לשקופית 7.

### הפקודה

<div dir="ltr">

```bash
oha -z 30s -c 50 --no-tui http://127.0.0.1:8000/v1/plots
```

</div>

הבדיקה רצה מול שרת שכבר פועל, כלומר השרת מההדגמה (<code dir="ltr">uv run uvicorn ...</code>) צריך לעבוד בזמן ההרצה.

**פירוק:**

- <code dir="ltr">oha</code> — כלי לבדיקות עומס על HTTP. שולח הרבה בקשות ומסכם זמני תגובה וקודי סטטוס.
- <code dir="ltr">-z 30s</code> — משך הבדיקה: 30 שניות.
- <code dir="ltr">-c 50</code> — concurrency: עד 50 בקשות פתוחות במקביל. כשבקשה חוזרת, נשלחת חדשה במקומה.
- <code dir="ltr">--no-tui</code> — מדפיס סיכום בטרמינל, בלי לפתוח את הממשק האינטראקטיבי.
- <code dir="ltr">http://127.0.0.1:8000/v1/plots</code> — ה־GET endpoint שנבדק: רשימת החלקות.

### התוצאות

| מדד | ערך |
|---|---|
| Throughput | <code dir="ltr">1,576.83</code> בקשות בשנייה |
| Average response time | <code dir="ltr">31.72 ms</code> |
| p95 | <code dir="ltr">39.27 ms</code> |
| p99 | <code dir="ltr">43.64 ms</code> |
| תגובות שהתקבלו | <code dir="ltr">47,264</code>, כולן <code dir="ltr">200 OK</code> |
| בקשות שבוטלו בסיום הבדיקה | <code dir="ltr">50</code> |

### מה לומר

"מעבר לבדיקת הביצועים שהוגדרה במשימה, רציתי לבדוק גם איך השרת מתנהג תחת עומס גבוה יותר.

השתמשתי בכלי בשם oha, לבדיקת עומס על HTTP. שלחתי בקשות GET במשך 30 שניות, עם 50 בקשות במקביל.

הגעתי לקצב של כ־1,577 בקשות בשנייה, כאשר זמן התגובה הממוצע היה כ־32 מילישניות, וה־p95 היה כ־39 מילישניות.

כל 47 אלף התגובות שהתקבלו החזירו סטטוס 200. בנוסף, 50 בקשות בוטלו כשהבדיקה הסתיימה.

בבדיקה הזאת קצב הבקשות היה גבוה משמעותית, וגם זמני התגובה היו גבוהים יותר. זה יכול להיות קשור לעומס ולמקביליות, אבל כדי לבודד את הסיבה המדויקת צריך לבצע בדיקות מבוקרות נוספות."

### המושגים

- **Throughput** — כמה בקשות השרת מסיים בשנייה. כאן כ־1,577.
- **Concurrency** — כמה בקשות "באוויר" באותו רגע. כאן 50.
- **Average response time** — הממוצע של כל זמני התגובה: <code dir="ltr">31.72 ms</code>. ממוצע יכול להסתיר בקשות איטיות בודדות, ולכן מסתכלים גם על אחוזונים.
- **p95** — ‏95% מהבקשות הסתיימו תוך <code dir="ltr">39.27 ms</code> או פחות.
- **p99** — ‏99% מהבקשות הסתיימו תוך <code dir="ltr">43.64 ms</code> או פחות. מראה את "הזנב" — האיטיות שרק מעט בקשות חוות.

**בדיקת עקביות (Little's Law):** כשתמיד יש 50 בקשות במקביל, ה־throughput שווה בערך ל־50 חלקי זמן התגובה הממוצע: 50 ÷ 0.03172 שניות ≈ 1,576 בקשות בשנייה — כמעט בדיוק מה שנמדד. זה מראה שהמספרים מתיישבים זה עם זה, אבל לא מסביר למה זמן התגובה עלה.

### ההבדל מהבדיקה הרשמית של P1

| | הבדיקה הרשמית | בדיקת oha |
|---|---|---|
| קצב | 10 בקשות בשנייה בסך הכול, בקצב קבוע | כ־1,577 בקשות בשנייה, כמה שהשרת מספיק |
| מקביליות | בקשה חדשה לפי לוח זמנים קבוע | עד 50 בקשות במקביל כל הזמן |
| נתיבים | 11 נתיבי GET | endpoint אחד: <code dir="ltr">/v1/plots</code> |
| משך | 120 שניות | 30 שניות |
| p95 | <code dir="ltr">9.76 ms</code> | <code dir="ltr">39.27 ms</code> |

אלה עומסים שונים, ולכן זו לא השוואה מבוקרת אחד מול אחד. הבדיקה הרשמית עונה על דרישת המשימה; oha מראה מה קורה כשלוחצים על השרת חזק יותר.

### שאלות צפויות

| שאלה | תשובה |
|---|---|
| למה זמן התגובה גבוה יותר מבבדיקה הרשמית? | העומס שונה: 50 בקשות במקביל מול 10 בקשות בשנייה. סביר שבקשות ממתינות זו לזו, אבל לא בודדתי את הסיבה המדויקת. |
| מה זה 50 הבקשות שבוטלו? | בקשות שהיו באמצע כשהזמן נגמר, ו־oha עצר אותן. זה בדיוק מספר הבקשות שהיו במקביל, והן לא שגיאות של השרת. |
| אז כל הבקשות הצליחו? | כל 47,264 התגובות שהתקבלו היו <code dir="ltr">200 OK</code>. ה־100% מתייחס לתגובות שהושלמו; בנוסף 50 בוטלו בסיום. |
| זה מוכיח שהמערכת מוכנה ל־Production? | לא. בדיקה מקומית, endpoint אחד, קריאות בלבד, 30 שניות. לא מדדתי כתיבות. |
| איך היית ממשיך? | בדיקות מבוקרות: אותו endpoint עם 1, 10 ו־50 בקשות במקביל כדי לראות איך זמן התגובה משתנה, ובדיקה של כתיבות, כי ב־SQLite יכול לכתוב רק תהליך אחד בכל רגע. |

</div>

## שקופית 7 — Questions & Code Walkthrough (08:30–10:00)

**מה לומר:**
"זה מה שרציתי להציג. אשמח לשאלות.
אם תרצו, אפשר גם לפתוח יחד כל חלק בקוד, להריץ את הבדיקות או לשלוח בקשה נוספת ל־API."

**אם מבקשים לראות קוד — מאיפה להתחיל:**

- `main.py` — יצירת האפליקציה, חיבור ה־Routers וטיפול ב־Database לא זמין (503).
- `routers/` — הנתיבים, הקלט וה־Status Codes.
- `repositories/` — שאילתות ה־SQL.
- `db.py` — חיבור SQLite לכל בקשה, שנסגר בסוף הבקשה.
- `schemas.py` — מודלי Pydantic וה־Validation.
- `tests/` — הבדיקות האוטומטיות.

**תשובות קצרות לשאלות צפויות:**

| שאלה | תשובה |
|---|---|
| למה API ולא Excel? | מקור נתונים מרכזי, חוזה קבוע, Validation וגישה ממערכות אחרות דרך HTTP. |
| למה Router ו־Repository? | הפרדה בין לוגיקת ה־HTTP לבין ה־SQL. |
| למה חיבור חדש לכל בקשה? | פשוט וזול יחסית ב־SQLite; Pool לא פותר את מגבלת הכותב היחיד. |
| האם `/health` בודק את ה־Database? | לא, רק שהשרת מגיב. `/v1/emitters` כבר עובר דרך ה־Database. |
| 404, 409 או 422? | 404 — פריט לא קיים; 409 — התנגשות עם מצב קיים; 422 — קלט לא תקין. |
| למה אין Problem Details לפי RFC 9457? | המרצה אישר שתגובות ברירת המחדל של FastAPI מספיקות. |
| האם p95 מוכיח מוכנות ל־Production? | לא, רק תחת העומס שנמדד: GET, 10 בקשות בשנייה בסך הכול, על מחשב מקומי. |
| PostgreSQL? | בשלב תכנון; P1 שהוצג רץ על SQLite. |

## תוכנית גיבוי אם משהו נכשל בהדגמה

- אם `uvicorn` טוען שהפורט תפוס: כנראה יש שרת קיים. נסה `curl -i http://127.0.0.1:8000/health`; אל תשנה פורט אקראית באמצע ההצגה.
- אם GET ל־Catalogue מחזיר `503`: קובץ SQLite אולי חסר/לא זמין. עבור להצגת קוד ו־README והסבר מה אמור לקרות. אל תאפס DB בלי לוודא שאין בו נתונים חשובים.
- אם יש בעיה טכנית בהדגמה: אל תיתקע יותר מדקה. המשך לבדיקות ולשקף הסיום באמצעות הפרויקט והתוצאות המתועדות.
- אם שואלים על שינויי PostgreSQL שטרם הושלמו: להפריד בין P1 הגמור לבין התכנון לעתיד.
