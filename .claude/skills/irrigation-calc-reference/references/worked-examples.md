# Worked examples: three cases calculated by hand

Calculated by hand during P2 and re-checked on 2026-11-20. The formulas are in [../SKILL.md](../SKILL.md); FAO citations are in [fao56.md](../../../../services/planner-service/docs/research/fao56.md). Intermediate values are unrounded. Values marked "API" are rounded with the SKILL.md rules. Engine tests must reproduce every API value.

## Case 1: tomato, mid-season, one day of water use (the spec's example)

This checks ETc, emitter flow and run time. It is **not** a bucket decision: it shows how long it takes to replace one day's ETc.

**Inputs:** tomato at mid-season (Kc 1.15), ET0 6.0 mm, no rain, area 1,000 m², rows 1.5 m apart, emitters every 0.4 m, 1.0 L/h per emitter.

```
ETc       = 1.15 × 6.0                    = 6.9 mm
litres    = 6.9 mm × 1,000 m²             = 6,900 L
emitters  = 1,000 / (1.5 × 0.4) = 1,000 / 0.6 = 1,666.666… (density estimate)
flow      = 1,666.666… × 1.0              = 1,666.666… L/h
run time  = 6,900 / 1,666.666… = 4.14 h   = 248.4 min
```

**API:** kc 1.150, litres 6900, run_minutes 248. These match the spec's example table.

## Case 2: bell pepper, development stage (Kc interpolation)

**Inputs:** planting date 2026-10-01, date 2026-11-19, ET0 3.0 mm. Pepper stages 30/40/110/30, Kc ini 0.60, Kc mid 1.05.

```
i     = (2026-11-19 − 2026-10-01).days + 1 = 49 + 1 = 50
stage : initial 1–30, development 31–70 → day 50 is in development
Kc    = 0.60 + (50 − 30) / 40 × (1.05 − 0.60) = 0.60 + 0.5 × 0.45 = 0.825
ETc   = 0.825 × 3.0 = 2.475 mm
```

**API:** kc 0.825. No litres or minutes, because the case gives no area, emitters or bucket state.

## Case 3: tomato on sand, seven days of the bucket, with rain and the 24 h cap

**Inputs:** tomato at mid-season (Kc 1.15, constant over the 7 days), sand at 83 mm/m, Zr 0.7 m, area 1,500 m², rows 1.5 m apart, emitters every 0.4 m, 0.6 L/h per emitter. The bucket is full on the morning of day 1. (These are the seed plot "West block" values.)

| Day | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| ET0 (mm) | 6.0 | 6.0 | 5.0 | 6.0 | 6.0 | 5.5 | 6.0 |
| Rain (mm) | 0 | 0 | 5 | 0 | 0 | 0 | 0 |

**Set-up:**

```
TAW        = 83 × 0.7              = 58.1 mm
threshold  = 0.5 × 58.1            = 29.05 mm
emitters   = 1,500 / (1.5 × 0.4)   = 2,500
flow       = 2,500 × 0.6           = 1,500 L/h   (= 1 mm/h over this plot)
daily cap  = 1,500 L/h × 24 h      = 36,000 L    = 24 mm = 1,440 min
```

**Days 1–5: no irrigation**, because start − ETc stays at or above 29.05 every day.

```
day 1: start = 58.1                         ETc 6.9   58.1 − 6.9   = 51.2   → end 51.2
day 2: start = min(51.2 + 0, 58.1) = 51.2   ETc 6.9   51.2 − 6.9   = 44.3   → end 44.3
day 3: start = min(44.3 + 5, 58.1) = 49.3   ETc 5.75  49.3 − 5.75  = 43.55  → end 43.55
day 4: start = 43.55                        ETc 6.9   43.55 − 6.9  = 36.65  → end 36.65
day 5: start = 36.65                        ETc 6.9   36.65 − 6.9  = 29.75  → end 29.75 (0.70 above threshold)
```

**Day 6: irrigation, capped.**

```
start      = 29.75        ETc = 1.15 × 5.5 = 6.325
check      : 29.75 − 6.325 = 23.425 < 29.05 → irrigate
desired    = 58.1 − 29.75 = 28.35 mm = 42,525 L = 28.35 h = 1,701 min   (over the cap)
applied_l  = min(42,525, 36,000) = 36,000 L → applied_mm = 24 mm, run_minutes = 1,440
end        = 29.75 + 24 − 6.325 = 47.425
```

The uncapped result (end 51.775) is **not** the plan; it would claim water the system can't deliver.

**Day 7: no irrigation.** Nothing carries over from the day 6 shortfall.

```
start = 47.425    ETc 6.9    47.425 − 6.9 = 40.525 ≥ 29.05 → end 40.525
```

**API values:**

| Day | kc | litres | run_minutes | bucket_level_mm |
|---|---|---|---|---|
| 1 | 1.150 | 0 | 0 | 51.200 |
| 2 | 1.150 | 0 | 0 | 44.300 |
| 3 | 1.150 | 0 | 0 | 43.550 |
| 4 | 1.150 | 0 | 0 | 36.650 |
| 5 | 1.150 | 0 | 0 | 29.750 |
| 6 | 1.150 | 36000 | 1440 | 47.425 |
| 7 | 1.150 | 0 | 0 | 40.525 |

# Boundary cases for engine tests

Computed with exact fractions on 2026-11-21, not by hand. Each case targets a spot where float arithmetic gives a wrong answer. Engine tests must reproduce every API value.

## B1: a day that ends at exactly half (no irrigation)

**Inputs:** tomato planted 2026-11-01, plan from 2026-11-20 (days 20–26, initial stage, Kc 0.6), soil 90 mm/m, area 1,000 m², rows 1.5 m, emitters 0.4 m, 1.0 L/h, ET0 7.5 mm every day, no rain.

```
TAW = 90 × 0.7 = 63 mm, threshold = 31.5 mm, ETc = 0.6 × 7.5 = 4.5 mm/day
day 7: start 36.0 − 4.5 = 31.5 → not below 31.5 → no irrigation, end 31.5
```

**API:** no irrigation on any day; bucket_level_mm 58.500, 54.000, 49.500, 45.000, 40.500, 36.000, 31.500.

A float engine without a tolerance gets 31.499999… on day 7 and irrigates (27,000 L, 972 min).

## B2: the same plot, ET0 7.501 (just below half, day 7 irrigates)

ETc = 4.5006 mm/day. Day 7: start 35.9964 − 4.5006 = 31.4958 < 31.5 → irrigate, desired 27.0036 mm.

**API, day 7:** litres 27004 (27,003.6), run_minutes 972 (972.1296), bucket_level_mm 58.499. Days 1–6 do not irrigate.

## B3: Kc tie

Bell pepper planted 2026-10-01, date 2026-11-01 → i = 32 (development).
Kc = 0.60 + (32 − 30) / 40 × (1.05 − 0.60) = 0.6225 exactly → **API kc 0.623**. A float gives 0.6224999… → 0.622. This is the only Kc tie in either crop curve that floats round wrong.

## B4: litres and minutes ties

**Inputs:** bell pepper planted 2026-08-01, plan from 2026-11-20 (days 112–118, mid-season, Kc 1.05), sand 83 mm/m, area 500 m², rows 1.5 m, emitters 0.4 m, 1.0 L/h, ET0 3.5 mm every day, no rain.

```
TAW = 83 × 0.5 = 41.5, threshold 20.75, ETc = 1.05 × 3.5 = 3.675 mm/day
emitters 833.333…, flow 833.333… L/h, daily cap 20,000 L (not reached)
day 6: start 23.125 − 3.675 = 19.45 < 20.75 → desired 18.375 mm
       litres  = 18.375 × 500 = 9,187.5 → 9188
       minutes = 9,187.5 / 833.333… × 60 = 661.5 → 662
       end     = 23.125 + 18.375 − 3.675 = 37.825
```

**API:**

| Day | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| litres | 0 | 0 | 0 | 0 | 0 | 9188 | 0 |
| run_minutes | 0 | 0 | 0 | 0 | 0 | 662 | 0 |
| bucket_level_mm | 37.825 | 34.150 | 30.475 | 26.800 | 23.125 | 37.825 | 34.150 |

A float engine gives 9187 L and 661 min.

## B5: the rounding helper on its own

| Value | Places | Result |
|---|---|---|
| `Fraction("0.6225")` | 3 | 0.623 |
| `Fraction("0.62249")` | 3 | 0.622 |
| `Fraction("9187.5")` | 0 | 9188 |
| `Fraction("9187.4999")` | 0 | 9187 |
| `Fraction("661.5")` | 0 | 662 |
| `Fraction("86.8775")` | 3 | 86.878 |
| `Fraction("86.8774")` | 3 | 86.877 |
