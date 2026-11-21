---
name: irrigation-calc-reference
description: The exact irrigation formulas, crop values, units, and rounding rules for the AgroPilot planner-service (FAO-56 single Kc, soil bucket, drip run time). Use whenever you write, change, test, review, or explain any number in the irrigation plan (GET /v1/plots/{id}/plan), including Kc, growth stage, days since planting, ET0 to ETc, rain, the soil bucket (TAW, threshold, bucket level), irrigation depth, litres, emitter count, flow, or run_minutes. Use it even when the request only says "the irrigation engine", "the planner calculation", or "why does the plan say N minutes".
---

# Irrigation calculation reference

FR-2.11 requires every number in the plan to be calculated **as written here**. Do not add, change, or "improve" a formula or value on your own. Nobody can check an engine that differs from its reference. If a case is not covered, stop and ask.

Each rule is tagged with its source:
- **[FAO]**: FAO-56, see the research notes in [fao56.md](../../../services/planner-service/docs/research/fao56.md).
- **[P2]**: the assignment spec.
- **[Project]**: a decision we made.
- **[Units]**: unit arithmetic.

Three cases calculated by hand, plus boundary cases for rounding and the threshold, are in [references/worked-examples.md](references/worked-examples.md). Engine tests must reproduce all of them exactly.

## Inputs and units

| Input | Unit | From |
|---|---|---|
| `area_m2`, `row_spacing_m`, `emitter_spacing_m` | m², m, m | registry plot |
| `crop_id` (`tomato`, `bell-pepper`), `planting_date` | text, ISO date | registry plot |
| `available_water_mm_per_m` = 1000 × (θFC − θWP) | mm of water per m of soil | registry soil |
| `flow_lph` | L/h per emitter | registry emitter |
| `et0_mm`, `rain_mm` per date | mm/day | weather-service |

## Crop values [FAO], single Kc, no climate adjustment [Project]

| Crop | Stage lengths ini/dev/mid/late (days) | Season | Kc ini / mid / end | Root depth Zr |
|---|---|---|---|---|
| tomato | 35 / 45 / 70 / 30 | 180 | 0.60 / 1.15 / 0.80 | 0.7 m |
| bell-pepper | 30 / 40 / 110 / 30 | 210 | 0.60 / 1.05 / 0.90 | 0.5 m |

These are fixed P2 simplifications [Project], taken from the FAO-56 reference values. They are not claimed to be correct for every location or planting season.
- **Stage lengths:** Table 11, "Arid Region" rows (tomato Oct/Nov, pepper October). These rows are used for every plot, whatever its planting month.
- **Kc:** Table 12, not staked. Tomato Kc end is 0.80, chosen inside FAO's 0.70–0.90 range.
- **Root depth:** Table 22, the smaller end of the range (tomato 0.7–1.5 m, pepper 0.5–1.0 m). Footnote 1 says to use the smaller values for scheduling. Zr stays fixed for the whole season, so young plants get a bigger bucket than their real roots reach.
- **Why single Kc:** weather-service gives only ET0 and rain (FR-2.3). Dual Kc and the Eq. 62/65 climate adjustments need wind speed and humidity. FAO recommends dual Kc for drip (Table 10); we rejected it for P2.

## Kc on a given day [FAO Ch. 6, Eq. 66]

```
i = (date − planting_date).days + 1        # the planting day is day 1  [Project]
```

| Stage | Days (tomato / pepper) | Kc |
|---|---|---|
| Initial | 1–35 / 1–30 | Kc ini |
| Development | 36–80 / 31–70 | Kc ini + (i − L_ini) / L_dev × (Kc mid − Kc ini) |
| Mid-season | 81–150 / 71–180 | Kc mid |
| Late season | 151–180 / 181–210 | Kc mid + (i − L_ini − L_dev − L_mid) / L_late × (Kc end − Kc mid) |

**Outside the season (i > 180 for tomato, i > 210 for pepper): OPEN DECISION.** Do not hold Kc end, do not return 0, and do not extend the curve. The behaviour has not been decided yet. Ask before implementing anything for this case.

## One day of the soil bucket

The bucket is the water the root zone holds, in mm averaged over the whole plot [FAO Ch. 8].

```
TAW       = available_water_mm_per_m × Zr        # bucket size, mm        [FAO Eq. 82]
threshold = TAW / 2                              # "below half → irrigate" [P2]
```

For each plan day, in this order (today is day 1):

```
1. start = min(prev_end + rain_mm, TAW)          # day 1: prev_end = TAW, bucket full this morning [Project]
                                                 # rain arrives at the start of the day, before ETc [Project]
                                                 # rain above TAW is lost (deep percolation)  [FAO Eq. 86, 88]
2. etc   = kc × et0_mm                           # [FAO Eq. 56]
3. if start − etc < threshold:                   # strictly below; ending exactly at half is fine [P2]
       desired_mm = TAW − start                  # refill to full at the start of the day [Project, after Annex 8]
   else:
       desired_mm = 0
4. emitters  = area_m2 / (row_spacing_m × emitter_spacing_m)    # density estimate, not rounded [Units]
   flow_lph  = emitters × flow_lph_per_emitter
   desired_l = desired_mm × area_m2                             # 1 mm over 1 m² = 1 L [Units]
   applied_l = min(desired_l, flow_lph × 24)                    # 24 h daily cap = 1440 min [Project]
   applied_mm  = applied_l / area_m2
   run_minutes = applied_l / flow_lph × 60
5. end = max(start + applied_mm − etc, 0)        # bucket level at end of day [FAO Eq. 86: 0 ≤ Dr ≤ TAW]
```

Why each rule exists:
- **Rain at the start of the day (step 1):** a project simplification. The model is daily, not hourly, so rain that really falls in the evening is still counted in the morning.
- **Exact comparison (step 3):** the engine calculates with exact fractions (see "Exact arithmetic"), so a day that should end at exactly half really ends at exactly half. No tolerance is needed. With floats it doesn't: in boundary case B1 a float engine irrigates on a day that ends at exactly half.
- **Same-day look-ahead (step 3):** we irrigate before the bucket falls below half. Annex 8 instead decides from the previous day's end; the look-ahead is our choice.
- **Daily cap (step 4):** a drip system can't run more than 24 hours in a day. If the cap is hit, the bucket is refilled only partly, and the next day starts from what was actually delivered. Nothing carries over automatically. Never report the uncapped volume or a full bucket when the cap was hit.
- **Clamp at 0 (step 5):** the clamp only applies when even capped irrigation can't keep up. The crop is then under water stress (FAO Ks < 1). Do not present those numbers as safe.
- **The threshold is P2's 50 %, not FAO's p** (Table 22: 0.40 for tomato, 0.30 for pepper). So by FAO, stress can begin slightly before the P2 threshold.
- **No efficiency factor:** the applied depth is used as net depth, as in the spec's example [P2].

## Invalid inputs

A missing, negative, or non-numeric ET0 or rain, or a non-positive area, spacing or flow, is an error and is never treated as 0. A plan of zeros reads as "no water needed", which is the worst bug in this system (FR-2.8, FR-2.14).

## Exact arithmetic [Project]

Floats can't store most decimals exactly. Kc 0.6225 comes out as 0.62249999…, so half-up rounding gives 0.622 instead of 0.623, and a day that should end at exactly half can end a hair below it. So the engine calculates with `fractions.Fraction`, which stores a number exactly as numerator / denominator (0.6225 is 249/400). Every step above is +, −, ×, ÷, `min` or `max`, so exact inputs give exact results.

- **Convert every input once, before any arithmetic:** `Fraction(str(value))` for each number from registry-service and weather-service. `str()` gives back the decimal that was stored: `str(0.4)` is `"0.4"`, so the result is exactly 2/5. Never convert a float that came out of a calculation, because it already carries the error. NaN and infinity raise `ValueError`; treat that as an invalid input.
- **Write constants as exact values:** `Fraction("1.15")`, not `1.15`.
- **Never mix in a float.** `Fraction * float` silently returns a float. Write `taw / 2`, not `0.5 * taw`. An engine test should check that the calculated values are `Fraction`s.

## Rounding (API output only) [Project]

- Calculate everything at full precision. Never feed a rounded value back into a calculation; the bucket balance uses unrounded values only.
- Apply the daily cap before rounding.
- Round every field below half-up (.5 rounds up), the `ROUND_HALF_UP` rule, with this helper. Python's `round()` rounds .5 to even, so don't use it.

```python
import math
from fractions import Fraction

def round_half_up(value: Fraction, places: int) -> Fraction:
    """Round an exact value that is >= 0, with .5 rounding up."""
    scale = 10 ** places
    return Fraction(math.floor(value * scale + Fraction(1, 2)), scale)
```

For values ≥ 0 this is exactly `ROUND_HALF_UP`, and every rounded field is ≥ 0. Then use `int(...)` for `litres` and `run_minutes`, and `float(...)` for `kc` and `bucket_level_mm` (`float(Fraction(623, 1000))` prints as 0.623).

| Field | Output |
|---|---|
| `run_minutes` | whole minutes |
| `litres` | whole litres (from `applied_l`) |
| `kc` | 3 decimals |
| `bucket_level_mm` (`end`) | 3 decimals |
| `et0_mm` | as received from weather-service, unchanged |
