# Real Exchange Rate App

Interactive Streamlit app for comparing the real exchange rate of two IMF economies using monthly CPI and FX data from January 1976 where available.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Definitions

- `S(t)`: units of Country 2 currency per unit of Country 1 currency.
- `P1(t)`, `P2(t)`: monthly CPI indexes.
- `RER(t) = S(t) * P1(t) / P2(t)`.
- `RER*`: average RER over valid months in the selected date range.
- `Real Index(t) = 100 * RER(t) / RER*` (average equals 100 over valid months).

FX data are retrieved as local currency per USD. Cross-rates are computed as `FX2 / FX1` (USD cancels). The IMF API may be unavailable or have incomplete historical series; the app displays errors and coverage rather than inventing observations.

## Sources

IMF SDMX 3.0 API: https://api.imf.org/external/sdmx/3.0/

- CPI: `IS03.CPI._TIX.M`
- FX: `IS03.XDC_USD_PA_RT.M`

## Notes

Data coverage and indicator names depend on the IMF dataset and country. The euro area uses IMF code `G163`. The app uses monthly periods, leaves gaps missing, and exports all valid paired observations in the selected range. Nominal exchange rates are displayed in actual currency units.
