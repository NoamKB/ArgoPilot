---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
---

Today is 2026-11-22. For each AgroPilot plan request below, say what `GET /v1/plots/{id}/plan?days=N` should return: the HTTP status and, for an error, the JSON body. (a) Seed plot North block, tomato planted 2026-03-01, days=7. (b) Seed plot Greenhouse, bell pepper planted 2026-05-01, days=7. (c) The same Greenhouse plot, days=5. (d) A tomato plot planted 2026-11-25, days=7. (e) A tomato plot planted 2026-11-22, days=7. Write answer.json with keys a to e, each an object with "status" and, for an error, "code" and "detail"; for a normal plan give only "status". Explain each answer in answer.md, including the day numbers that decide it.
