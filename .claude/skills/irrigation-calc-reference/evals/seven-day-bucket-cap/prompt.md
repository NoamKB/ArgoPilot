---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
---

Calculate the 7-day irrigation plan the AgroPilot planner should return for this plot, starting 2026-11-20. Plot: tomato, planted 2026-08-23, area 1500 m2, soil sand (available_water_mm_per_m 83), rows 1.5 m apart, emitters every 0.4 m, emitter flow 0.6 L/h. Forecast ET0 (mm) for the 7 days: 6.0, 6.0, 5.0, 6.0, 6.0, 5.5, 6.0. Rain (mm): 0, 0, 5, 0, 0, 0, 0. Write answer.json as a list of 7 objects with keys date, kc, litres, run_minutes, bucket_level_mm, and explain each day in answer.md.
