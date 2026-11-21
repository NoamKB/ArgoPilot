---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
---

Compute the AgroPilot 7-day plan starting 2026-11-20 for a tomato plot planted 2026-08-23: area 1500 m2, sand (available_water_mm_per_m 83), rows 1.5 m apart, emitters every 0.4 m at 1.0 L/h. ET0 is 4.5 mm every day; the only rain is 0.5 mm on 2026-11-21. Write answer.json as a list of 7 objects with keys date, kc, litres, run_minutes, bucket_level_mm, and explain in answer.md which day irrigates and how you got its litres and run_minutes.
