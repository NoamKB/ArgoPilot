# Writing the speaker notes

The notes are the user's script and study sheet. The user reads them before the review and glances at them while presenting; afterwards the reviewers ask follow-ups. A sentence the user can't explain in their own words is worse than no sentence. Write for a learner who knows Python well, knows the system at a high level, and is still building fluency in infrastructure terms.

## Headings, in this order (Hebrew, bold)

Include a heading only when it has real content. Never write a heading just to say it doesn't apply.

- **מאיפה באנו:** slide 1 only — the overview described below.
- **על מה השקף:** one line — what this slide is about. Example: "תיאור הארכיטקטורה: אילו רכיבים יש ומי מדבר עם מי."
- **שאלה:** the review question(s) this slide answers, quoted in English. Leave out when the slide answers none (the title slide).
- **מה אומרים:** what to say out loud, 3–6 short spoken sentences. Weave in the review question's answer in words a reviewer would recognise.
- **מה רואים בשקף:** what each part of the visual means, in reading order ("משמאל הדפדפן; החץ הראשון הוא..."). About content only.
- **מה קורה ברכיב:** the mechanism behind the slide, step by step, in plain words.
- **עומס:** what happens to this part under heavy load or with several copies running. Only where it matters.
- **מילון:** every term from this slide and its notes that a learner might not know, a few words each.
- **הדגמה:** where a live demo fits this slide, what to click and what the reviewers will see.
- **אם שואלים:** two or three likely follow-ups, each with a short answer and a label: (נמדד), (נקרא בקוד) or (משוער).
- **איפה בקוד:** file and function names, last, for the user to look up. No line numbers.

## Slide 1 opens with the system overview

Before anything about the title slide, two or three sentences that place this assignment in the course. Example for P2: "P2 הוא הרחבה של P1. ב-P1 בנינו את התשתית ואת השירות הראשון, ה-registry, עם ה-API של חוות, חלקות וקטלוגים. ב-P2 הרחבנו את הארכיטקטורה: הוספנו שני שירותי Python, ה-weather וה-planner, העברנו את ה-registry ל-PostgreSQL, ובנינו frontend ב-Next.js." Check the facts against the code and the spec before writing them; the example is the shape, not the content for every assignment.

## Rules, with examples from the P2 dry run

**Explain content, not formatting.**
- Bad: "כותרת ... באפור." — The user doesn't need to be told what's grey.
- Good: say what the element means: "בצד ימין השירותים שנוספו ב-P2."

**Every term gets a few words the first time.** If a term is worth mentioning, it's worth one clause.
- Bad: "הדף עטוף ב-Suspense."
- Good: "הדף עטוף ב-Suspense — רכיב של React שמציג טקסט זמני ('Checking services…') עד שהחלק האיטי מוכן, ואז מחליף אותו."

**Every number says what it means and what happens when it's exceeded.**
- Bad: "REGISTRY_TIMEOUT_SECONDS=3, WEATHER_TIMEOUT_SECONDS=12."
- Good: "ה-planner מחכה לתשובה מה-registry עד 3 שניות. אם אין תשובה, הוא מוותר ומחזיר 503 שאומר ש-registry-service לא זמין. ל-weather הוא מחכה עד 12 שניות, כי ה-weather עצמו יכול לחכות עד כ-9 שניות ל-Open-Meteo (3 ניסיונות של 3 שניות)."

**One meaningful number, not a pile of them.** A number earns its place only if it answers a question the reviewer cares about and the user can explain what it means and how it was obtained. Pick the one that tells the story; leave the rest out of the slide and the notes.
- Bad: "p50 9 ms, p75 10 ms, p90 11 ms, p95 12 ms, p99 15 ms" — a list of percentiles shows effort, not understanding.
- Good: "p95 of the weather call from the cache: 8.73 ms — 95 of 100 requests answered faster than that, less than a tenth of the 100 ms target." One number, its meaning, and why it matters.
- Good: the p95 of each hop side by side (registry, weather, planner, frontend), because together they answer "where is the time spent?".
- No dates: don't write when something was measured or checked.

**No raw identifiers in the spoken text.** Test function names, `path:line`, and environment-variable line numbers confuse more than they prove.
- Bad: "(נמדד: test_clearly_out_of_season_plot_is_409_without_soil_emitter_or_weather_calls)"
- Good: "(נמדד: יש טסט שבודק שחלקה מחוץ לעונה מקבלת 409, וה-planner לא פונה בכלל לאדמה, לטפטפת או למזג האוויר.)" — and put the file under **איפה בקוד**.
- Bad: "(services/weather-service/.env.example:9,11)" — the user couldn't tell that 9,11 are line numbers.
- Good: "ההגדרות ב-`.env.example` של ה-weather."

**Name a function only with what it does.**
- Bad: "utc_today הוא dependency, והטסט מחליף אותו."
- Good: "`utc_today` היא פונקציה קטנה שמחזירה את התאריך של היום. FastAPI מקבל אותה כ-dependency (תלות שהוא קורא לה לפני ה-endpoint), ולכן טסט יכול להחליף אותה בתאריך קבוע, וכך התוצאה לא תלויה ביום שבו מריצים."

**Sentences the user must be able to unpack.** Before keeping a sentence, ask: could the user answer "what do you mean?" about it?
- Bad: "כל הקריאות לשירותים רצות בשרת בקבצים ב-src/lib."
- Good: "הדפדפן לא פונה לשירותים בעצמו. הקוד שפונה ל-registry, ל-planner ול-weather נמצא בשלושה קבצים בתיקייה `src/lib` של ה-frontend, והוא רץ רק על שרת ה-Next.js. הדפדפן מקבל HTML מוכן."

**Headlines must be clear when read aloud.** A clever phrase that needs explaining is a bad headline.
- Bad: "The browser talks to one server and never learns a service exists"
- Good: "The browser talks only to the frontend server; the services stay behind it"

**Infrastructure terms: one plain sentence each, no lecture.** Only write about what the user can explain.
- Process: "תוכנה אחת שרצה במחשב. כל שירות שלנו הוא תהליך uvicorn אחד" — not a Linux service (systemd).
- Instance (מופע/עותק): "עוד עותק של אותו שירות שרץ במקביל."
- Load balancer: "שער אחד מקדימה שמחלק בקשות בין כמה עותקים. אצלנו אין, כי יש עותק אחד מכל שירות."
- Timeout: "כמה זמן מחכים לתשובה לפני שמוותרים."

## The review questions run through the notes

The reviewers ask the review questions and variations of them. In **מה אומרים**, answer the slide's question in a sentence that reuses the question's words, so the link is obvious. In **אם שואלים**, include the variations: for each question, the "what if it fails", "how do you know" and "what with many servers" versions.
