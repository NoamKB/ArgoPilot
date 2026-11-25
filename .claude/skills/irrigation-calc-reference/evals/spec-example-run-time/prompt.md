---
tags: [skill-creator]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
---

For AgroPilot's planner: a 1000 m2 tomato plot is at mid-season, ET0 today is 6.0 mm, no rain. Rows are 1.5 m apart and emitters are every 0.4 m at 1.0 L/h. How much water does the crop use today (mm and litres), how many emitters does the plot have, and how many minutes would the drip system need to run to deliver that day's crop water use? Write the numbers to answer.json with keys etc_mm, litres, emitters, run_minutes, and explain the steps in answer.md.
