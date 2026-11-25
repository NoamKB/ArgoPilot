# FAO-56 for a daily drip-irrigation planner

Research notes for the AgroPilot planner. Source: Allen, R. G., Pereira, L. S., Raes, D., Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop water requirements*. FAO Irrigation and Drainage Paper 56 ("FAO-56").

**Question (from the assignment):** "I'm building a daily drip-irrigation planner. Use FAO-56, chapters 5, 6, 8 and Annex 8. Explain how to get from ET0 and Kc to the crop's water need, the Kc values and growth stages for tomato and bell pepper, how the soil bucket works, and how Annex 8 schedules irrigation day by day. Cite the chapter or table for every claim."

**How to read the citations:** "Ch. 6, Eq. 62" means FAO-56 chapter 6, equation 62. "Table 12" and "Example 26" are FAO-56's own numbering. Annex 8 uses "Figure 8.1", "Box 8.1", "Eq. 8-1". All pages were fetched on 2026-11-18 from fao.org. The links below use `https://www.fao.org/3/...` as given in the assignment; fao.org redirects them to `https://www.fao.org/4/...` with the same content.

| Part | Page |
|---|---|
| Table of contents | https://www.fao.org/3/x0490E/x0490e00.htm |
| Ch. 5, Introduction to crop evapotranspiration (ETc) | https://www.fao.org/3/x0490E/x0490e0a.htm |
| Ch. 6, ETc: single crop coefficient (Kc). Tables 9-16 | https://www.fao.org/3/x0490E/x0490e0b.htm |
| Ch. 7, ETc: dual crop coefficient (Kc = Kcb + Ke). Tables 17-21 | https://www.fao.org/3/x0490E/x0490e0c.htm |
| Ch. 8, ETc under soil water stress conditions. Table 22 | https://www.fao.org/3/x0490E/x0490e0e.htm |
| Annex 8, Calculation example for applying the dual Kc procedure in irrigation scheduling | https://www.fao.org/3/x0490E/x0490e0p.htm |

Chapter 7 is not on the assignment's list, but it is needed for two reasons. Annex 8 is built entirely on the Chapter 7 "dual Kc" method (Annex 8, first paragraph). Table 19 (soil water properties) is also printed in Chapter 7, and Chapter 8 refers to it (Ch. 8, "Total available water"). Only the parts of Chapter 7 that these uses need are covered here.

---

## 1. From ETo and Kc to the crop's water need

### 1.1 Terms

- **Evapotranspiration (ET):** water that leaves a field as vapour. It is the sum of *evaporation* from the soil surface and *transpiration* through the plants' leaves. It is expressed as a depth of water per day, **mm/day** (Ch. 5, Eq. 56 units). By unit arithmetic (not an FAO citation), 1 mm of water over 1 m² is 1 litre.
- **ETo, reference crop evapotranspiration [mm/day]:** the ET of a well-watered hypothetical grass surface with fixed height, albedo and surface resistance. It is computed from weather data with the FAO Penman-Monteith equation (Ch. 5, "Direct calculation"). ETo is "an index of climatic demand": it measures how strongly the weather pulls water out of a field (Ch. 5, "Crop coefficient approach"). (The assignment writes "ET0". FAO-56 writes ETo. They are the same thing.)
- **Kc, crop coefficient [dimensionless]:** the ratio ETc / ETo for a particular crop at a particular growth stage (Ch. 5, "Crop coefficient approach").
- **ETc, crop evapotranspiration under standard conditions [mm/day]:** the ET of a disease-free, well-fertilised crop in a large field with optimal soil water, achieving full production (Ch. 5, intro; Ch. 6, intro).
- **ETc adj, adjusted crop evapotranspiration [mm/day]:** ETc corrected for non-standard conditions, such as water stress (Ch. 5, "Crop coefficient approach"; Ch. 8, Eq. 80-81).

### 1.2 The core equation

```
ETc = Kc × ETo                                   (Ch. 5, Eq. 56; repeated as Ch. 6, Eq. 58)

ETc  crop evapotranspiration            [mm d-1]
Kc   crop coefficient                   [-]
ETo  reference crop evapotranspiration  [mm d-1]
```

- Weather effects go into ETo, and crop characteristics go into Kc. This is why Kc values can be transferred between locations and climates (Ch. 5, "Crop coefficient approach").
- Kc combines four differences between the crop and the reference grass: crop height, albedo (reflectance) of the crop-soil surface, canopy resistance to vapour transfer, and evaporation from the soil, especially exposed soil (Ch. 5, "Crop coefficient approach").
- ETc from Eq. 56 is the *upper envelope* of crop ET. It assumes no limits from water shortage, crop density, disease, weeds, insects or salinity (Ch. 5, "Crop coefficient approach").

### 1.3 Single vs dual crop coefficient, and why it matters for drip

FAO-56 offers two ways to build Kc (Ch. 5, "Single and dual crop coefficient approaches"; Table 10):

- **Single Kc (Ch. 6):** one time-averaged coefficient that mixes transpiration and soil evaporation together. Table 10 lists it for irrigation planning and design, irrigation management, basic irrigation schedules, and "real time irrigation scheduling for non-frequent water applications (surface and sprinkler irrigation)". Time step: daily, 10-day or monthly.
- **Dual Kc (Ch. 7):** splits Kc into two parts:

  ```
  Kc = Kcb + Ke                                  (Ch. 5, Eq. 57)
  ETc = (Kcb + Ke) × ETo                         (Ch. 7, Eq. 69)

  Kcb  basal crop coefficient: ETc/ETo when the soil surface is dry but the root zone
       has enough water for full transpiration (mostly transpiration)   [-]
  Ke   soil evaporation coefficient (evaporation from wet soil surface)  [-]
  ```

  Table 10 lists the dual approach for research, real time irrigation scheduling, "irrigation scheduling for high frequency water application (microirrigation and automated sprinkler irrigation)", supplemental irrigation, and detailed soil and hydrologic water balance studies. Time step: daily only. Solution method: computer.

- Ch. 5 says the dual procedure "is best for real time irrigation scheduling … This is the case for high frequency irrigation with microirrigation systems" (Ch. 5, "Dual crop coefficient approach"). **Drip is a form of microirrigation.** So FAO-56 favours the dual method for a daily drip scheduler. It accepts the single method for planning and for typical irrigation management (Ch. 5, "Single crop coefficient approach"; Ch. 6, intro).
- Kcb is always below Kc. The gap is largest in the initial stage, when most ET is soil evaporation. In mid-season Kcb may be only 0.05-0.10 below Kc (Ch. 5, "Crop coefficient curve", Figure 26).

### 1.4 When the soil runs short of water: Ks

```
ETc adj = (Ks × Kcb + Ke) × ETo     dual Kc     (Ch. 8, Eq. 80)
ETc adj = Ks × Kc × ETo             single Kc   (Ch. 8, Eq. 81)

Ks  water stress coefficient [0-1]; Ks = 1 means no stress
```

Ks reduces only transpiration, so Eq. 80 is "generally more valid" than Eq. 81. Eq. 81 gives reasonable results when soil evaporation is not a large part of ETc (Ch. 8, intro). Section 4.4 shows how Ks is computed.

### 1.5 What "the crop's water need" means in FAO-56 terms

- **ETc (or ETc adj) is the daily water consumption** of the crop in mm/day (Ch. 5, Eq. 56; Ch. 8, Eq. 80-81).
- **The irrigation need comes from a daily soil water balance.** The balance tracks how much of the root zone's storage has been used (Ch. 8, Eq. 85). Irrigation is required "when rainfall is insufficient to compensate for the water lost by evapotranspiration". You irrigate before or when the readily available water is used up, and you apply no more than the current depletion (Ch. 8, "Forecasting or allocating irrigations"). See Section 4.
- **The irrigation depth Ii in the balance is a *net* depth:** the depth that infiltrates the soil, expressed as the mean depth over the whole field (Ch. 8, Eq. 85 variable list; Ch. 8, "Precipitation (P), runoff (RO) and irrigation (I)").
- Rain below about 0.2 × ETo on a day is normally all evaporated and can usually be ignored in the water balance (Ch. 8, "Precipitation (P), runoff (RO) and irrigation (I)"; Ch. 7, "Daily calculation of Ke").

---

## 2. Growth stages and the Kc curve

### 2.1 The four growth stages (Ch. 5, "Crop growth stages"; Figure 23)

| Stage | Starts | Ends | What happens to Kc |
|---|---|---|---|
| **Initial** (L_ini) | planting date | about **10 % ground cover** | Leaves are small and ET is mostly soil evaporation. Kc ini is high when the soil surface is wet and low when it is dry. |
| **Crop development** (L_dev) | 10 % ground cover | **effective full cover**: often the start of flowering; for row crops, when leaves of adjacent rows begin to intermingle; or when LAI (leaf area index) reaches about 3 | Kc rises as the crop shades more ground. |
| **Mid-season** (L_mid) | effective full cover | **start of maturity**: ageing, yellowing or senescence of leaves, leaf drop, or browning of fruit | Kc reaches its maximum, Kc mid, which is "relatively constant". |
| **Late season** (L_late) | start of maturity | harvest or full senescence | Kc falls to Kc end. Kc end is high if the crop is irrigated frequently until harvested fresh, and low if the crop dries in the field. |

*Ground cover (fc)* is the fraction of the soil surface covered or shaded by vegetation (Ch. 7, "1 - fc: exposed soil fraction"). *LAI* is the one-sided leaf area per unit ground area (Ch. 5, "Crop development stage").

### 2.2 Building the Kc curve (Ch. 6, "Construction of the Kc curve", Figure 34)

Only three Kc values are needed: Kc ini, Kc mid and Kc end (Ch. 6, "Crop coefficients"). The curve is built in three steps (Ch. 6, "Annual crops"):

1. Divide the season into the four stages, find their lengths (Table 11) and pick Kc ini, Kc mid and Kc end (Table 12).
2. Adjust these Kc values for wetting frequency and climate (Section 2.3).
3. Join straight-line segments: a **horizontal** line at Kc ini through the initial stage, a **diagonal** from Kc ini to Kc mid through development, a **horizontal** line at Kc mid through mid-season, and a **diagonal** from Kc mid to Kc end through the late season.

**Daily Kc by linear interpolation:**

```
Kc,i = Kc,prev + [ (i − Σ(L_prev)) / L_stage ] × (Kc,next − Kc,prev)        (Ch. 6, Eq. 66)

i          day number within the growing season [1 … season length]
Kc,i       crop coefficient on day i [-]
L_stage    length of the stage under consideration [days]
Σ(L_prev)  sum of the lengths of all previous stages [days]
Kc,prev    Kc at the end of the previous stage
Kc,next    Kc at the beginning of the next stage (Kc end for the late season)
```

- Eq. 66 "applies to all four stages". In the initial and mid-season stages Kc,prev = Kc,next, so Kc stays constant (Ch. 6, "Numerical determination of Kc").
- FAO's check (Ch. 6, Example 28; dry bean, stages 25/25/30/20 days, Kc 0.15/1.19/0.35): on day 40 (development), Kc = 0.15 + [(40 − 25)/25] × (1.19 − 0.15) = **0.77**.
- The same interpolation is used for Kcb in the dual method (Ch. 7, Example 30). Annex 8 does the same in a spreadsheet (Annex 8, Box 8.1, footnote 2: "Linear interpolation is applied when the day is within the development and late season growing periods").

### 2.3 Adjusting the three Kc values

**Kc ini (initial stage).** Table 12 values for Kc ini "are only approximations and should only be used for … preliminary or planning studies" (Ch. 6, "Crop coefficient for the initial stage"). Kc ini depends on three things: the time between wettings, the evaporating power of the atmosphere (ETo), and the size of each wetting event. It can range from 0.1 to 1.15 (Ch. 6, same section). Approximate values are in Table 9 (Ch. 5). More accurate values come from Figures 29 and 30 or from Annex 7, Eq. 7-3 (Table 12, footnote 1). To interpolate between light (~10 mm) and heavy (~40 mm) wetting events:

```
Kc ini = Kc ini(Fig 29) + [(I − 10)/(40 − 10)] × [Kc ini(Fig 30) − Kc ini(Fig 29)]      (Ch. 6, Eq. 59)
I = average infiltration depth per wetting event [mm]
```

**Partial wetting (drip):** see Section 5. Ch. 6 multiplies Kc ini by fw, the fraction of the surface wetted (Ch. 6, Eq. 60-61).

**Kc mid (mid-season).** Table 12 values assume a sub-humid climate: average daily minimum relative humidity RHmin ≈ 45 % and wind speed u2 ≈ 2 m/s (Table 12 title; Ch. 5, "Climate"). For other climates:

```
Kc mid = Kc mid(Tab) + [0.04 (u2 − 2) − 0.004 (RHmin − 45)] × (h/3)^0.3              (Ch. 6, Eq. 62)

Kc mid(Tab)  value from Table 12
u2     mean daily wind speed at 2 m over grass during mid-season [m s-1], valid 1 ≤ u2 ≤ 6
RHmin  mean daily minimum relative humidity during mid-season [%], valid 20 ≤ RHmin ≤ 80
h      mean plant height during mid-season [m], valid 0.1 < h < 10
```

- u2 and RHmin should be averages for the stage (Ch. 6, text after Figure 32).
- RHmin can be estimated from dew-point temperature, or from Tmin when no humidity data exist (Ch. 6, Eq. 63-64). In arid and semi-arid climates, subtract 2 °C from Tmin before using it (Ch. 6, Eq. 64 footnote, citing Annex 6, Eq. 6-6):

  ```
  RHmin = 100 × e°(Tdew) / e°(Tmax)        (Ch. 6, Eq. 63)
  RHmin = 100 × e°(Tmin) / e°(Tmax)        (Ch. 6, Eq. 64, when Tdew is unavailable)
  e°(T) = 0.6108 × exp(17.27 T / (T + 237.3))   saturation vapour pressure [kPa], T in °C
                                           (formula as used in Annex 8, Box 8.1, cells I14/J14, citing Eq. 11)
  ```

- When no wind or humidity data exist, use Table 15 (e.g. "light to moderate wind" 2.0 m/s; "general global conditions" 2 m/s) and Table 16 (RHmin: arid 20 %, semi-arid 30 %, sub-humid 45 %, humid 70 %, very humid 80 %) (Ch. 6).
- Wetting frequency: if irrigation is more frequent than every 3 days *and* the Table 12 Kc mid is below 1.0, Kc mid can be replaced by about 1.1-1.3 (Ch. 6, "Adjustment for frequency of wetting"). This does not apply to tomato (1.15) or bell pepper (1.05), because both are already ≥ 1.0 (my reading of the rule against Table 12).

**Kc end (end of late season).**

```
Kc end = Kc end(Tab) + [0.04 (u2 − 2) − 0.004 (RHmin − 45)] × (h/3)^0.3             (Ch. 6, Eq. 65)
```

Same variables and limits as Eq. 62, but averaged over the late season. Apply Eq. 65 **only when Kc end(Tab) > 0.45**. Below that, use the table value unchanged (Ch. 6, text after Eq. 65). For tomato (0.70-0.90) and bell pepper (0.90) the adjustment applies.

---

## 3. Tomato and bell pepper: stages, Kc, Kcb, rooting depth, p

All values below are copied as printed. FAO-56 groups both crops under "b. Vegetables - Solanum Family (Solanaceae)". (Table 22 misprints this as "Solarium".)

### 3.1 Stage lengths, Table 11 (Ch. 6), in days

| Crop | Init. (L_ini) | Dev. (L_dev) | Mid (L_mid) | Late (L_late) | Total | Plant date | Region |
|---|---|---|---|---|---|---|---|
| Sweet peppers (bell) | 25/30 | 35 | 40 | 20 | 125 | April/June | Europe and Medit. |
| Sweet peppers (bell) | 30 | 40 | 110 | 30 | 210 | October | Arid Region |
| Tomato | 30 | 40 | 40 | 25 | 135 | January | Arid Region |
| Tomato | 35 | 40 | 50 | 30 | 155 | Apr/May | Calif., USA |
| Tomato | 25 | 40 | 60 | 30 | 155 | Jan | Calif. Desert, USA |
| Tomato | 35 | 45 | 70 | 30 | 180 | Oct/Nov | Arid Region |
| Tomato | 30 | 40 | 45 | 30 | 145 | April/May | Mediterranean |

Notes:
- Table 11 footnote (*): stage lengths "are indicative of general conditions, but may vary substantially from region to region, with climate and cropping conditions, and with crop variety. The user is strongly encouraged to obtain appropriate local information." Primary source: FAO-24 (Doorenbos and Pruitt, 1977), Table 22.
- Ch. 6 says the Table 11 values "are useful only as a general guide" and that local observations should be used wherever possible ("Length of growth stages", text after Table 11). Box 15 shows why: the Table 11 mid-season length for dry beans (40 days) overestimated the locally observed 30 days.
- **Pepper "25/30":** FAO gives two initial-stage lengths without explaining them. The listed total of 125 days matches 30 + 35 + 40 + 20, not 25 + 35 + 40 + 20 = 120 (my arithmetic). Treat it as a range of 25-30 days.
- Every other row adds up to its listed total (my arithmetic check).

### 3.2 Single crop coefficients, Table 12 (Ch. 6)

| Crop | Kc ini (1) | Kc mid | Kc end | Max. crop height h (m) |
|---|---|---|---|---|
| *b. Solanum family (group row)* | **0.6** | 1.15 | 0.80 | – |
| Sweet Peppers (bell) | (0.6 from group row) | **1.05** (2) | **0.90** | **0.7** |
| Tomato | (0.6 from group row) | **1.15** (2) | **0.70-0.90** | **0.6** |

- The Kc ini cell is blank for both crops. The group row gives 0.6. Ch. 6 explains: "For several group types only one value for Kc ini is listed and it is considered to be representative of the whole group" ("Crop coefficient for the initial stage").
- **Footnote 1 (Kc ini):** "These are general values for Kc ini under typical irrigation management and soil wetting. For frequent wettings such as with high frequency sprinkle irrigation or daily rainfall, these values may increase substantially and may approach 1.0 to 1.2. Kc ini is a function of wetting interval and potential evaporation rate … and is more accurately estimated using Figures 29 and 30, or Equation 7-3 in Annex 7, or using the dual Kcb ini + Ke."
- **Footnote 2 (Kc mid, staked crops):** "Beans, Peas, Legumes, Tomatoes, Peppers and Cucumbers are sometimes grown on stalks reaching 1.5 to 2 meters in height. In such cases, increased Kc values need to be taken. For green beans, peppers and cucumbers, 1.15 can be taken, and for tomatoes, dry beans and peas, 1.20. Under these conditions h should be increased also." So for staked/trellised plants: **pepper Kc mid = 1.15, tomato Kc mid = 1.20**, with a larger h.
- Table 12 values are for RHmin ≈ 45 % and u2 ≈ 2 m/s. Adjust Kc mid with Eq. 62 and Kc end with Eq. 65 (both apply because both Kc end values exceed 0.45) (Table 12 title; Ch. 6, text after Table 12).
- **Tomato Kc end is a range (0.70-0.90)** and FAO gives no tomato-specific footnote for choosing within it. The only general guidance is in Ch. 6, "Crop coefficient for the end of the late season stage": if the crop is irrigated frequently until harvested fresh, "the topsoil remains wet and the Kc end value will be relatively high". Crops allowed to senesce and dry out in the field before harvest get less or no irrigation in the late season, and their Kc end "will be relatively small". Using the upper end for fresh-market tomatoes irrigated until harvest is my interpretation, not an FAO rule.
- Table 12 values are for non-stressed crops with full stand density. Lower density, height or leaf area requires modifying Kc mid and Kc end (Part C, Chs. 8-10) (Ch. 6, text after Table 12).

### 3.3 Basal crop coefficients for the dual method, Table 17 (Ch. 7)

| Crop | Kcb ini (1) | Kcb mid | Kcb end |
|---|---|---|---|
| *b. Solanum family (group row)* | **0.15** | 1.10 | 0.70 |
| Sweet Peppers (bell) | (0.15 from group row) | **1.00** (2) | **0.80** |
| Tomato | (0.15 from group row) | **1.10** (2) | **0.60-0.80** |

- **Footnote 1:** Kcb values represent "a dry soil surface" and "are intended for use with the dual Kcb ini + Ke approach, only." For heights, use Table 12 (pepper 0.7 m, tomato 0.6 m).
- **Footnote 2 (staked crops):** "increased Kcb values need to be taken. For green beans, peppers and cucumbers, 1.10 can be taken, and for tomatoes, dry beans and peas, 1.15. Under these conditions h should be increased also."
- Kcb mid and Kcb end values of 0.45 or more are adjusted for climate with:

  ```
  Kcb = Kcb(Tab) + [0.04 (u2 − 2) − 0.004 (RHmin − 45)] × (h/3)^0.3                   (Ch. 7, Eq. 70)
  ```

  Variables and limits are as in Eq. 62 (Ch. 7, "Basal crop coefficient").
- Table 18 (Ch. 7) explains how Kcb was derived from Kc. Examples: initial stage of an annual crop on (nearly) bare soil, Kcb = 0.15. Mid-season with less than 80 % ground cover (vegetables), Kcb ≈ Kc mid − 0.10. End of season, frequently irrigated, Kcb ≈ Kc end − 0.1. Local Kcb values "should not be expected to deviate by more than 0.2" from Table 17 (Ch. 7, "Basal crop coefficient").

### 3.4 Rooting depth and depletion fraction, Table 22 (Ch. 8)

| Crop | Maximum root depth Zr (1) (m) | Depletion fraction p (2) (for ET ≈ 5 mm/day) |
|---|---|---|
| Sweet Peppers (bell) | **0.5-1.0** | **0.30** |
| Tomato | **0.7-1.5** | **0.40** |

- **Footnote 1 (Zr):** "The larger values for Zr are for soils having no significant layering or other characteristics that can restrict rooting depth. The smaller values for Zr may be used for irrigation scheduling and the larger values for modeling soil water stress or for rainfed conditions." For a scheduler, FAO-56 points to the **smaller end** of the range.
- **Footnote 2 (p):** p applies for ETc ≈ 5 mm/day and can be adjusted (see Section 4.3).
- FAO's own tomato examples use **Zr ≈ 0.8 m, p = 0.40** for a full-grown crop (Ch. 8, Examples 36 and 37).

### 3.5 Illustration (my arithmetic, not an FAO example)

Tomato, Mediterranean April/May row of Table 11 (30/40/45/30 days), with Kc ini 0.6, Kc mid 1.15 and Kc end 0.80 (a value inside the 0.70-0.90 range), all unadjusted. Eq. 66 gives:

- day 50: 0.6 + [(50 − 30)/40] × (1.15 − 0.6) = 0.875
- days 71-115: 1.15
- day 130: 1.15 + [(130 − 115)/30] × (0.80 − 1.15) = 0.975

With ETo = 6 mm/day on day 50, ETc = 0.875 × 6 ≈ 5.3 mm/day (Eq. 56).

---

## 4. The soil "bucket" (Ch. 8)

FAO-56 models the root zone as a container whose water content goes up and down (Ch. 8, "Soil water balance", Figure 43). It is easier to track how far the bucket is *below full* than how full it is. That quantity is called the **depletion**.

### 4.1 Field capacity, wilting point, total available water

- **Field capacity (θFC):** the water a well-drained soil holds against gravity after heavy rain or irrigation has drained (Ch. 8, "Total available water").
- **Wilting point (θWP):** the water content at which plants permanently wilt; roots cannot extract water below it (Ch. 8, same section).
- θ is volumetric water content in m³ of water per m³ of soil.

```
TAW = 1000 × (θFC − θWP) × Zr                               (Ch. 8, Eq. 82)

TAW  total available soil water in the root zone [mm]
θFC  water content at field capacity [m3 m-3]
θWP  water content at wilting point  [m3 m-3]
Zr   rooting depth [m]
1000 converts m of water to mm
```

Typical soil values from **Table 19** (Ch. 7), USA soil texture classes:

| Soil type | θFC (m³/m³) | θWP (m³/m³) | θFC − θWP (m³/m³) | REW (mm) | TEW (mm, Ze = 0.10 m) |
|---|---|---|---|---|---|
| Sand | 0.07-0.17 | 0.02-0.07 | 0.05-0.11 | 2-7 | 6-12 |
| Loamy sand | 0.11-0.19 | 0.03-0.10 | 0.06-0.12 | 4-8 | 9-14 |
| Sandy loam | 0.18-0.28 | 0.06-0.16 | 0.11-0.15 | 6-10 | 15-20 |
| Loam | 0.20-0.30 | 0.07-0.17 | 0.13-0.18 | 8-10 | 16-22 |
| Silt loam | 0.22-0.36 | 0.09-0.21 | 0.13-0.19 | 8-11 | 18-25 |
| Silt | 0.28-0.36 | 0.12-0.22 | 0.16-0.20 | 8-11 | 22-26 |
| Silt clay loam | 0.30-0.37 | 0.17-0.24 | 0.13-0.18 | 8-11 | 22-27 |
| Silty clay | 0.30-0.42 (printed "0-30 - 0.42") | 0.17-0.29 | 0.13-0.19 | 8-12 | 22-28 |
| Clay | 0.32-0.40 | 0.20-0.24 | 0.12-0.20 | 8-12 | 22-29 |

(REW and TEW belong to the surface evaporation layer. See Section 4.7.)

### 4.2 Readily available water and p

Crops start to suffer stress well before the wilting point. The fraction of TAW a crop can use without stress is p (Ch. 8, "Readily available water"):

```
RAW = p × TAW                                               (Ch. 8, Eq. 83)

RAW  readily available soil water in the root zone [mm]
p    average fraction of TAW that can be depleted before moisture stress
     (reduction in ET) occurs [0-1]  (Table 22)
```

### 4.3 Adjusting p

- **For the ET rate:** p normally ranges from 0.30 (shallow roots, ETc > 8 mm/day) to 0.70 (deep roots, ETc < 3 mm/day). 0.50 is common. In hot dry weather p is 10-25 % below Table 22, and at low ETc up to 20 % above (Ch. 8, "Readily available water"). The numerical approximation is:

  ```
  p = p(Table 22) + 0.04 × (5 − ETc)      limited to 0.1 ≤ p ≤ 0.8, ETc in mm/day
                                           (Ch. 8, text after Eq. 83; Table 22, footnote 2; Figure 41)
  ```

  "Often, a constant value is used for p for a specific growing period, rather than varying the value each day" (Ch. 8, same section).
- **For soil texture:** for fine (clay) soils, p can be reduced by 5-10 %. For coarse (sandy) soils, it can be increased by 5-10 % (Ch. 8, text after Example 36).
- **MAD (management allowed depletion):** RAW "is similar to" MAD. MAD also reflects management and economics: MAD < RAW when the grower is risk-averse, and MAD > RAW when stress is intended (Ch. 8, text after Example 36). Annex 8 schedules irrigation on MAD and assumes p = MAD (Annex 8, Box 8.1 footnote 11).

FAO's tomato RAW figures (Ch. 8, Example 36; Zr ≈ 0.8 m, p = 0.40):

| Soil | 1000(θFC − θWP) | TAW (mm) | RAW (mm) |
|---|---|---|---|
| Loamy sand | 90 mm/m | 72 | 29 |
| Silt | 170 mm/m | 136 | 54 |
| Silty clay | 120 mm/m | 96 | 38 |

### 4.4 Depletion and the water stress coefficient Ks

- **Root zone depletion Dr [mm]:** the water shortage relative to field capacity. Dr = 0 at field capacity. ET increases Dr. Stress starts when Dr exceeds RAW (Ch. 8, "Water stress coefficient (Ks)", Figure 42).

```
Ks = (TAW − Dr) / (TAW − RAW) = (TAW − Dr) / ((1 − p) × TAW)     when Dr > RAW     (Ch. 8, Eq. 84)
Ks = 1                                                          when Dr ≤ RAW     (Ch. 8, text after Eq. 84)
```

Ks falls linearly from 1 at Dr = RAW to 0 at Dr = TAW. FAO's tomato example (Ch. 8, Example 37): Zr = 0.8 m, p = 0.40, silty soil with θFC = 0.32 and θWP = 0.12, ETo = 5 mm/day, Kc = 1.2, no rain or irrigation. TAW = 160 mm, RAW = 64 mm, starting Dr = 55 mm. Ks stays 1.00 on days 1-2, then drops to 0.97, 0.91, … 0.62 by day 10, and ETc adj falls from 6.0 to 3.7 mm/day. "The example demonstrates that the estimate of Ks requires a daily water balance calculation."

### 4.5 Daily root zone water balance

```
Dr,i = Dr,i−1 − (P − RO)i − Ii − CRi + ETc,i + DPi          (Ch. 8, Eq. 85)

Dr,i    root zone depletion at the end of day i               [mm]
Dr,i−1  root zone depletion at the end of the previous day    [mm]
Pi      precipitation on day i                                [mm]
ROi     runoff from the soil surface on day i                 [mm]
Ii      net irrigation depth on day i that infiltrates        [mm]
CRi     capillary rise from the groundwater table on day i    [mm]
ETc,i   crop evapotranspiration on day i (ETc adj if stressed) [mm]
DPi     deep percolation out of the root zone on day i        [mm]
```

Rules (all Ch. 8, "Soil water balance"):

- **Limits:** `0 ≤ Dr,i ≤ TAW` (Eq. 86). Water above field capacity is assumed lost to deep percolation on the same day, after that day's ET.
- **Starting value:** `Dr,i−1 = 1000 × (θFC − θi−1) × Zr` from a measured water content (Eq. 87). Or assume Dr,i−1 ≈ 0 after heavy rain or irrigation.
- **Deep percolation after heavy rain or irrigation:** `DPi = (Pi − ROi) + Ii − ETc,i − Dr,i−1 ≥ 0` (Eq. 88). DPi = 0 while Dr,i > 0.
- **Capillary rise:** CR can normally be taken as zero when the water table is more than about 1 m below the bottom of the root zone.
- **Runoff:** can be predicted with standard hydrology procedures. Annex 8 assumes RO = 0 (Annex 8, text before Figure 8.1).
- **ET term:** ETc = Kc × ETo while Dr ≤ RAW. Once Dr exceeds RAW, use Eq. 80 or 81.

### 4.6 When and how much to irrigate (Ch. 8, "Forecasting or allocating irrigations")

- **When:** "To avoid crop water stress, irrigations should be applied before or at the moment when the readily available soil water is depleted (Dr,i ≤ RAW)."
- **How much:** "To avoid deep percolation losses that may leach relevant nutrients out of the root zone, the net irrigation depth should be smaller than or equal to the root zone depletion (Ii ≤ Dr,i)."
- Ch. 8, Example 38 applies these rules day by day with the dual Kc. Assumptions: irrigation when RAW is depleted, p = 0.6, irrigation and rain early in the day, root depth growing from 0.30 to 0.35 m. On day 10, a 27 mm net irrigation refills the root zone with DP = 0. Its table notes add the timing rule:
  - irrigation and rain early in the day: `Dr,i start = max(Dr,i−1 end − I − (P − RO), 0)`
  - irrigation and rain late in the day: `Dr,i start = Dr,i−1 end`
- **Growing root zone:** when Zr increases, the newly added soil layer adds its own deficit: `Dr,i = Dr,i−1 + 1000 × (θFC − θsub,i−1) × ΔZr,i`, where θsub is the subsoil water content. Example 38 assumes the subsoil is at field capacity, so this term is zero (Ch. 8, Example 38, note 5). Annex 8 grows Zr with Kcb (Section 6.5).

### 4.7 The second, small bucket: the evaporation layer (Ch. 7)

The dual method also keeps a daily balance for the top 0.10-0.15 m of soil. This layer controls how much wet-soil evaporation (Ke) occurs. Annex 8 uses it, so it is summarised here.

```
TEW = 1000 × (θFC − 0.5 θWP) × Ze                           (Ch. 7, Eq. 73)
TEW  total evaporable water: max depth that can evaporate from the fully wetted topsoil [mm]
Ze   depth of the surface layer that dries by evaporation [m]; use 0.10-0.15 m if unknown

REW  readily evaporable water: depth evaporated without restriction in "stage 1" [mm];
     normally 5-12 mm (Table 19 gives values by soil type)   (Ch. 7, "Stage 1: energy limiting stage")

Kr = (TEW − De,i−1) / (TEW − REW)   for De,i−1 > REW;  Kr = 1 when De,i−1 ≤ REW         (Ch. 7, Eq. 74)

Ke = min( Kr × (Kc max − Kcb),  few × Kc max )               (Ch. 7, Eq. 71)

Kc max = max( {1.2 + [0.04 (u2 − 2) − 0.004 (RHmin − 45)] × (h/3)^0.3},  {Kcb + 0.05} )   (Ch. 7, Eq. 72)

De,i = De,i−1 − (Pi − ROi) − Ii/fw + Ei/few + Tew,i + DPe,i  (Ch. 7, Eq. 77), with 0 ≤ De,i ≤ TEW (Eq. 78)
DPe,i = (Pi − ROi) + Ii/fw − De,i−1 ≥ 0                       (Ch. 7, Eq. 79)
Ei = Ke × ETo                                                (Ch. 7, Eq. 77 variable list)
```

- De is the cumulative evaporation (depletion) of the surface layer. Kr is the evaporation reduction coefficient (1 while the surface is wet, falling to 0 at TEW).
- Kc max is the ceiling on Kcb + Ke set by available energy. It ranges from about 1.05 to 1.30 (Ch. 7, "Upper limit Kc max").
- **Fraction of the soil that is both exposed and wetted (few):** see Section 5.
- **Transpiration from the evaporating layer (Tew)** can be taken as zero, except for shallow-rooted crops (maximum root depth < 0.5-0.6 m). For row crops, most root extraction is beneath the canopy (Ch. 7, "Daily calculation of Ke", "Transpiration").
- **Starting value:** De,i−1 = 0 after heavy wetting, or TEW after a long dry spell (Ch. 7, "Initial depletion").

---

## 5. Drip-specific points in FAO-56

- **Fraction of surface wetted, fw [0.01-1]:** Table 20 (Ch. 7) gives fw = **0.3-0.4 for trickle irrigation**, compared with 1.0 for precipitation, sprinkler, basin and border irrigation. Ch. 6 says "for a trickle irrigation system, the fraction of the surface wetted, fw, may be only 0.4" ("Adjustment for partial wetting by irrigation"). *Trickle irrigation* is FAO-56's term for drip.
- **Single Kc, initial stage:** multiply Kc ini by fw (Ch. 6, Eq. 60: `Kc ini = fw × Kc ini(Tab, Fig)`). When choosing between Figure 29 and Figure 30, use the infiltration depth on the wetted part, `Iw = I / fw` (Ch. 6, Eq. 61). FAO's trickle example: 12 mm every 2 days, fw = 0.4, ETo = 4 mm/day. Then Iw = 30 mm, Kc ini (wetted part) = 1.05, field Kc ini = 0.4 × 1.05 = **0.42**, and ETc = 1.7 mm/day (Ch. 6, Example 26).
- **Dual Kc: exposed and wetted fraction, few:**

  ```
  few = min(1 − fc, fw)                                      (Ch. 7, Eq. 75)
  fc = ((Kcb − Kc min) / (Kc max − Kc min))^(1 + 0.5 h)      (Ch. 7, Eq. 76; Kc min ≈ 0.15-0.20; fc ≤ 0.99)
  ```

  Eq. 75 assumes the wetted soil lies within the exposed (sunlit) soil, "except perhaps with drip irrigation". With drip, much of the wetted soil may be shaded under the canopy. FAO suggests reducing fw to about one-half to one-third of the Table 20 value, or as "a general approach", multiplying fw by **[1 − (2/3) fc]** (Ch. 7, text after Eq. 75; Figure 39). FAO's drip example: cotton, fc = 0.53, fw = 0.3, emitters beneath the canopy. Then few = min[(1 − 0.53), (1 − 0.67 × 0.53) × 0.3] = 0.19, Ke is limited to 0.19 × 1.30 = 0.25, and Kc = 0.9 + 0.25 = 1.15, which is lower than for sprinkler or furrow (Ch. 7, Example 34).
- **Irrigation depth on the wetted part:** in the evaporation-layer balance, irrigation enters as `Ii/fw` because the field-average depth is concentrated on the wetted fraction (Ch. 7, "Irrigation", Eq. 77). Annex 8 does the same (Box 8.1, footnote 4).
- **Kc max with frequent wetting:** the "1.2" in Eq. 72 represents wetting intervals of more than 3-4 days. With daily or two-day wetting it "can be reduced to about 1.1" (Ch. 7, "Upper limit Kc max"). This matters for drip, which often wets daily.
- **fw from day to day:** irrigation (with or without rain) sets fw to the irrigation system's value. Significant rain (> 3-4 mm) without irrigation sets fw = 1. With neither, fw keeps the previous day's value (Ch. 7, text after Table 20). Annex 8 implements this rule (Box 8.1, footnote 5).
- **Root zone balance:** Ii in Ch. 8, Eq. 85 is the depth averaged over the whole field (Ch. 8, "Precipitation (P), runoff (RO) and irrigation (I)"). FAO-56 does not give drip-specific Zr or p values. Table 22 is the only source for those in the chapters read.

---

## 6. How Annex 8 schedules irrigation day by day

### 6.1 What Annex 8 is

- A worked spreadsheet example (Figure 8.1, Excel formulas in Box 8.1, extra variable names in Table 8.1). It shows "the application of the various equations for calculating Kcb, Ke and ETc using the dual Kc approach of Chapter 7". The irrigation schedule is "determined using the daily soil-water balance procedure described in Chapter 8" (Annex 8, intro).
- Crop: dry edible beans, Kimberly, Idaho, 1974 (the same crop as Ch. 6, Box 15 and Ch. 7, Box 16). It is **not** a tomato or pepper example.
- **Timing rule:** "The timing of irrigations is based on the management allowed depletion (MAD) of the available water that can be stored in the root zone" (Annex 8, intro).
- The spreadsheet "can be used to verify other computer programs or spreadsheet calculations for Ke, Kc and ETc" (Annex 8, text before Figure 8.1).

**User inputs** (Figure 8.1 boxes; Box 8.1):

| Input | Value in the example |
|---|---|
| Stage lengths L_ini / L_dev / L_mid / L_late (Table 11) | 25 / 25 / 30 / 20 days |
| Kcb ini / Kcb mid / Kcb end (Table 17) | 0.15 / 1.10 / 0.25. The figure shows adjusted values 0.15 / 1.13 / 0.23. |
| Kc min | 0.15 |
| Maximum crop height | 0.4 m |
| Planting date | 22 May (J_plant = 142) |
| fw (irrigation) | 0.5 |
| REW / TEW / initial De / initial fw | 8 mm / 22 mm / 18 mm / 1 |
| Root_min (Zr min) / Root_max (Zr max) | 0.20 m / 0.80 m |
| Available water (θFC − θWP) | 160 mm/m |
| MAD during initial stage / after initial stage | 70 % / 45 % |
| Daily weather columns | Tmax, u2, Tdew, ETo, P − RO |

### 6.2 Assumptions stated in Annex 8 (text before Figure 8.1)

1. All irrigation and precipitation happen **early in the morning**.
2. Each day's irrigation decision is based on the root zone depletion **at the end of the previous day**. Needed irrigation "is presumed applied at beginning of next day" (Figure 8.1 header; Box 8.1, footnote 10).
3. All drainage from excess rain happens on the day of the rain.
4. Runoff is zero.
5. The net irrigation depth retained in the root zone **equals the previous day's depletion**. Each irrigation refills the root zone to field capacity. FAO notes this "presumes perfect knowledge of soil water depletion" and "can be changed by the user as needed."
6. No irrigation in the last half of the late season (Box 8.1, footnote 10). For the bean crop, the last irrigation is on day 225 (Annex 8, text after Eq. 8-3).
7. MAD can be larger during the initial stage, because roots can extract water at drier contents during germination with little stress. The example assumes p = MAD (Annex 8, text after Eq. 8-3; Box 8.1, footnote 11).

### 6.3 The daily calculation, in spreadsheet column order (Box 8.1)

Once per season:

- **Stage dates:** day of year for planting, development, mid-season, late season and harvest are computed from the planting date and the stage lengths (cells Q3-Q7).
- **Climate adjustment:** Kcb mid and Kcb end are adjusted with Eq. 70, using the **mid-season averages** of u2 and RHmin. These averages are taken from running totals in columns AO/AP (cells J5, J6, K8, K9; footnotes 1 and 12).

Each day i:

1. **RHmin** from Tmax and Tdew (Eq. 63, with e° from Eq. 11) (columns I, J, K).
2. **Kcb** for the day by stage and linear interpolation (Eq. 66). After harvest it returns to Kcb ini (column O; footnote 2).
3. **Crop height** = (Kcb / Kcb mid) × maximum height, never decreasing (column P; footnote 3).
4. **Kc max** from Eq. 72 (column Q).
5. **Irrigation at the start of the day** = yesterday's "net irrigation needed" ÷ fw, i.e. the depth over the wetted fraction only (column R; footnote 4). It is zero on the first day.
6. **fc** from Eq. 76, minimum 0.01 (column S). **fw** = system fw if irrigated, 1 if it rained, otherwise the previous day's fw (column T; footnote 5). **few** = min(1 − fc, fw) (Eq. 75, column U).
7. **De at start of day** = max(De end yesterday − P − I/fw, 0) (column V; footnote 6).
8. **Kr** (Eq. 74, column W). **Ke** (Eq. 71, column X). **E = Ke × ETo** (column Y).
9. **DPe** (Eq. 79, column Z). **De at end of day** (Eq. 77 with Tew = 0, column AA; footnote 6).
10. **Kc = Kcb + Ke** and **ETc = Kc × ETo** (Eq. 69; columns AB, AC; footnote 7).
11. **Root depth Zr** from Eq. 8-1, never decreasing (column AE; footnote 8).
12. **RAW (allowable depletion)** = MAD × Zr × available water, using the initial-stage MAD before the development date and the later MAD after it. The value is never allowed to decrease (column AF, labelled Eq. 82). With MAD = p, this is RAW = p × TAW (Eq. 82-83).
13. **First estimate of ending root zone depletion** = Dr end yesterday − P − yesterday's net irrigation + ETc, with no drainage and no stress (Eq. 85, column AG; footnote 9).
14. **Net irrigation needed** = that ending depletion, *if* it exceeds RAW and the day is between planting and the midpoint of the late season. Otherwise 0. It is applied the next morning (column AH; footnote 10).
15. **Deep percolation DP** from Eq. 88 (column AI).
16. **Ks** from Eq. 84 if the depletion exceeds RAW, otherwise 1 (column AJ; footnote 11).
17. **Kc adj = Ks × Kcb + Ke** (Eq. 80, column AK).
18. **Corrected ending depletion** = Dr end yesterday − P − irrigation + Kc adj × ETo + DP (Eq. 85, column AL; footnote 9). Tomorrow starts from this value.

### 6.4 Worked rows from Figure 8.1 (values as printed)

Figure 8.1 on the web page shows rows for 15-27 May 1974 (spreadsheet rows 14-26). Zr = 0.20 m and available water = 160 mm/m, so TAW = 32 mm and RAW = 0.70 × 32 = **22.4 mm** (column AF shows 22.4).

| Date (J) | ETo (mm/d) | Kcb | Ke | First-estimate ending Dr (mm) | Net irrigation needed (mm) | Ks | Kc adj | Corrected ending Dr (mm) |
|---|---|---|---|---|---|---|---|---|
| 18 May (138) | 3.8 | 0.15 | 0.11 | 23.2 | – | 0.92 | 0.25 | 23.2 |
| 22 May (142, planting) | 4.9 | 0.15 | 0.13 | 25.3 | **25.3** | 0.70 | 0.23 | 25.1 |
| 23 May (143) | 5.2 | 0.15 | 0.61 | 3.7 | – | 1.00 | 0.76 | 3.7 |

- On 22 May the ending depletion (25.3 mm) exceeded RAW (22.4 mm), so a net 25.3 mm is scheduled. On 23 May it appears as "Net Irrig./fw" = **50.6 mm** (= 25.3 / 0.5) on the wetted half of the surface. Evaporation-layer drainage DPe that day is 29.67 mm (Figure 8.1, columns R and Z).
- Ks on 22 May checks against Eq. 84: (32 − 25.3)/(32 − 22.4) = 0.70 (my arithmetic).
- Annex 8 itself notes that waiting until the previous day's depletion is ≥ RAW "occasionally causes a small amount of stress on the day prior to irrigation" (text after Eq. 8-3). Rows 18 May and 22 May show this (Ks < 1).
- Figures 8.2 and 8.3 plot daily Kcb, Kc and end-of-day depletion. Figure 8.3 shows the allowable depletion rising as the root zone deepens (Annex 8, text after Table 8.1).

### 6.5 Root depth growth (Annex 8)

```
Zr,i = Zr min + (Zr max − Zr min) × (Kcb,i − Kcb ini) / (Kcb mid − Kcb ini)    for J < J_mid     (Annex 8, Eq. 8-1)
Zr,i = Zr max                                                                for J ≥ J_mid     (Annex 8, Eq. 8-2)

Alternative, by date:
Zr,i = Zr min + (Zr max − Zr min) × (J − J_start) / (J_max − J_start)    for J_start ≤ J ≤ J_max (Annex 8, Eq. 8-3)
Zr,i = Zr min for J < J_start;  Zr,i = Zr max for J > J_max

Zr min  initial effective root depth at planting [m]; for many annual crops 0.15-0.20 m
Zr max  maximum effective root depth in mid-season [m], from Table 22
J       day of year [1-366]
```

Eq. 8-1 assumes root depth grows in proportion to Kcb, so the maximum depth is reached at the start of mid-season (Annex 8, text after Eq. 8-2).

### 6.6 Caveats FAO attaches to Annex 8

- "This particular example is intended only to demonstrate how to apply the soil evaporation equations during scheduling of irrigations. The procedure used to determine the irrigation schedule and the assumptions used may not always be appropriate. The reader should modify the irrigation scheduling procedure to fit the conditions of the local area." (Annex 8, final paragraph.)
- The theoretical schedule differs from the irrigations actually applied at Kimberly in 1974 (Box 16) (Annex 8, intro).

### 6.7 Inconsistencies observed inside Annex 8 (my observations; affect only someone reproducing the spreadsheet)

- Box 8.1 cell J6 adjusts Kcb end only if it is ≥ 0.45, so 0.25 should stay 0.25. Figure 8.1 nevertheless shows an adjusted Kcb end of **0.23**.
- The Kc max formula in Box 8.1 (cell Q14) multiplies daily wind by 0.9 (`F14*0.9`) before applying Eq. 72. Annex 8 does not explain this factor.
- Box 8.1 labels the Kcb input "Table 12", while Figure 8.1 labels it "Table 17". Table 17 is the correct source for Kcb (Ch. 7, Table 17 footnote 1).
- The HTML Box 8.1 has transcription errors: "014" for O14, "16" for I6, "AU 4" for AL14, "AJ14"/"AK14" repeated in the row-15 block, and "Eq. 8.1" vs "Eq. 81" labels.

---

## 7. Summary: one day in a FAO-56 drip planner

This chains the cited equations together. The ordering is my synthesis of Ch. 8 and Annex 8.

1. Get ETo for the day [mm/day] (computed with FAO Penman-Monteith; not covered here).
2. Find the crop's stage and interpolate Kc (single) or Kcb (dual) from the Table 11/12/17 values, adjusted with Eq. 62/65/70 (Eq. 66).
3. Single Kc: ETc = Kc × ETo (Eq. 56). Dual Kc: compute Ke from the evaporation-layer balance with drip fw and few (Eq. 71-79), then ETc = (Kcb + Ke) × ETo (Eq. 69).
4. Update root depth (Annex 8, Eq. 8-1) and TAW and RAW (Eq. 82-83, p from Table 22, optionally adjusted).
5. Update root zone depletion Dr (Eq. 85-88). If Dr > RAW, apply Ks (Eq. 84) and use ETc adj (Eq. 80/81).
6. If Dr has reached RAW (or MAD), schedule a net irrigation ≤ Dr for the next morning (Ch. 8, "Forecasting or allocating irrigations"; Annex 8, Box 8.1, column AH).

---

## Sources

All fetched 2026-11-18. The `/3/` URLs redirect to `/4/` on fao.org.

1. FAO-56 table of contents: https://www.fao.org/3/x0490E/x0490e00.htm
2. Chapter 5, Introduction to crop evapotranspiration (ETc). Eq. 56-57, Tables 9-10, Figures 23-27: https://www.fao.org/3/x0490E/x0490e0a.htm
3. Chapter 6, ETc: single crop coefficient (Kc). Eq. 58-66, Tables 11-16, Examples 26-28, Box 15: https://www.fao.org/3/x0490E/x0490e0b.htm
4. Chapter 7, ETc: dual crop coefficient. Eq. 69-79, Tables 17-21, Examples 29-35: https://www.fao.org/3/x0490E/x0490e0c.htm
5. Chapter 8, ETc under soil water stress conditions. Eq. 80-88, Table 22, Examples 36-38: https://www.fao.org/3/x0490E/x0490e0e.htm
6. Annex 8, Calculation example for applying the dual Kc procedure in irrigation scheduling. Figure 8.1 (images x0490e7e/7f/7g.gif), Box 8.1, Table 8.1, Eq. 8-1 to 8-3: https://www.fao.org/3/x0490E/x0490e0p.htm

On these pages the equations are images. I read each equation image cited above directly (Eq. 59, 61-66, 70, 72, 74, 76, 77, 79, 84, 8-1, 8-3, and the Kc ini/Kcb column headers of Tables 12 and 17).

## Gaps / unverified

- **Ch. 4 (FAO Penman-Monteith ETo calculation) and Ch. 3 (meteorological data) were not fetched.** They are outside the question. The e°(T) formula above is quoted from Annex 8, Box 8.1, which cites Eq. 11; Eq. 11 was not read in Ch. 3.
- **Figures 29 and 30 (graphs for Kc ini) and Annex 7, Eq. 7-3 were not read.** This document cannot give a numeric Kc ini for a specific drip interval beyond Table 12's 0.6, Table 9's ranges and FAO's Example 26.
- **Figure 8.1 on the web page shows only 13 days (15-27 May 1974).** The rest of the season's rows (through day 225 and harvest) are not visible on the fetched page, so the full schedule was not verified. The Quattro-Pro version mentioned in Annex 8 was not fetched.
- **Box 14 mismatch:** Ch. 6 text says "expected variations for Kc mid for tomatoes … are presented in Box 14", but Box 14 as published demonstrates **wheat** (Kc mid 1.15, h = 1.0 m). No tomato-specific climate table was found.
- **Choices FAO-56 leaves open for tomato and pepper:** where to pick tomato Kc end within 0.70-0.90 (Kcb end 0.60-0.80); pepper L_ini of 25 or 30 days; which Table 11 regional row to use (FAO says to use local data); where to pick Zr within 0.7-1.5 m (tomato) or 0.5-1.0 m (pepper), where footnote 1 points to the smaller values for scheduling; and whether to use the staked-crop values from footnote 2.
- **Not covered by the chapters read:** converting net to gross irrigation (application efficiency, distribution uniformity), emitter flow rates and run times, drip wetted-bulb geometry, and salinity leaching for drip. Ch. 8's salinity section (Eq. 89-93, Table 23) was skipped as outside the question.
- **Not checked against the print/PDF edition.** Values were taken from the HTML pages, which contain visible typos (e.g. Table 19 "0-30 - 0.42" for silty clay θFC; Table 22 "Solarium"). Nothing here was cross-checked against the PDF.
