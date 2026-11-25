---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
---

Compute the AgroPilot 7-day plan starting 2026-11-20 for a tomato plot planted 2026-11-15: area 1000 m2, a soil with available_water_mm_per_m 60, rows 1.5 m apart, emitters every 0.4 m at 1.0 L/h. ET0 is 7.0 mm every day and there is no rain. Write answer.json as a list of 7 objects with keys date, kc, litres, run_minutes, bucket_level_mm, and explain in answer.md which day irrigates and why.
