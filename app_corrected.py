import io
import re
import requests
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(page_title="Real Exchange Rate Explorer", layout="wide")
st.title("Real Exchange Rate Explorer")
st.caption("Monthly IMF CPI and exchange rates · January 1976 onward where available")

# IMF ISO3 economy identifiers, including the euro area aggregate G163.
COUNTRIES = {
    "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT", "Belgium": "BEL",
    "Brazil": "BRA", "Canada": "CAN", "Chile": "CHL", "China": "CHN",
    "Colombia": "COL", "Czech Republic": "CZE", "Denmark": "DNK", "Egypt": "EGY",
    "Euro area": "G163", "Finland": "FIN", "France": "FRA", "Germany": "DEU",
    "Greece": "GRC", "Hungary": "HUN", "India": "IND", "Indonesia": "IDN",
    "Ireland": "IRL", "Israel": "ISR", "Italy": "ITA", "Japan": "JPN",
    "Malaysia": "MYS", "Mexico": "MEX", "Netherlands": "NLD", "New Zealand": "NZL",
    "Norway": "NOR", "Pakistan": "PAK", "Peru": "PER", "Philippines": "PHL",
    "Poland": "POL", "Portugal": "PRT", "Romania": "ROU", "Saudi Arabia": "SAU",
    "Singapore": "SGP", "South Africa": "ZAF", "South Korea": "KOR", "Spain": "ESP",
    "Sweden": "SWE", "Switzerland": "CHE", "Thailand": "THA", "Turkey": "TUR",
    "United Kingdom": "GBR", "United States": "USA", "Vietnam": "VNM",
}

BASE = "https://api.imf.org/external/sdmx/3.0"
HEADERS = {"Accept": "csvfile, text/csv, application/vnd.sdmx.csv;version=2", "User-Agent": "RealExchangeRateExplorer/1.1 (educational research)"}


def normalize_imf_csv(content):
    """Extract month/value columns from SDMX CSV (2.0 or legacy IMF CSV layouts)."""
    frame = pd.read_csv(io.BytesIO(content), low_memory=False)
    if frame.empty:
        return pd.Series(dtype=float)
    cols = {str(c).strip().upper(): c for c in frame.columns}
    date_col = next((cols[k] for k in ("TIME_PERIOD", "TIME", "DATE") if k in cols), None)
    value_col = next((cols[k] for k in ("OBS_VALUE", "VALUE", "OBS_VALUE_N") if k in cols), None)
    if date_col is None or value_col is None:
        raise ValueError(f"Unexpected IMF CSV columns: {list(frame.columns)[:12]}")
    dates = pd.to_datetime(frame[date_col].astype(str), errors="coerce")
    values = pd.to_numeric(frame[value_col], errors="coerce")
    series = pd.Series(values.to_numpy(), index=dates.dt.to_period("M"))
    series = series[series.index.notna()].dropna()
    return series.groupby(level=0).last().sort_index()


@st.cache_data(ttl=3600, show_spinner=False)
def get_series(code, indicator):
    """Try the IMF's SDMX 3.0 data endpoint, with SDMX CSV responses."""
    # The IMF's current CPI dataflow uses five dimensions, not the old IS03 key.
    # Current CPI key order: COUNTRY.INDEX_TYPE.COICOP_1999.TYPE_OF_TRANSFORMATION.FREQUENCY
    if indicator == "CPI._TIX":
        urls = [
            f"{BASE}/data/dataflow/IMF.STA/CPI/+/{code}.CPI._T.IX.M?startPeriod=1976-01",
            f"{BASE}/data/dataflow/IMF.STA/CPI/+/*?c[COUNTRY]={code}&c[INDEX_TYPE]=CPI&c[COICOP_1999]=_T&c[TYPE_OF_TRANSFORMATION]=IX&c[FREQUENCY]=M&c[TIME_PERIOD]=ge:1976-01",
        ]
    else:
        # The FX dataflow/series identifier must be checked against current IMF metadata.
        # Keep the assignment-supplied IS03 key as a provisional compatibility fallback.
        key = f"M.{code}.{indicator}"
        urls = [
            f"{BASE}/data/dataflow/IMF/IS03/+/{key}?startPeriod=1976-01",
            f"{BASE}/data/IMF/IS03/+/{key}?startPeriod=1976-01",
        ]
    errors = []
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 403:
                raise RuntimeError("IMF returned HTTP 403. This may be an API access restriction; changing the URL alone cannot resolve a server-side block.")
            r.raise_for_status()
            if b"<html" in r.content[:300].lower() or b"<?xml" in r.content[:100].lower():
                raise ValueError("API returned HTML/XML rather than CSV")
            data = normalize_imf_csv(r.content)
            if len(data):
                return data
            errors.append("No numeric observations")
        except (requests.RequestException, RuntimeError, ValueError, pd.errors.ParserError) as exc:
            errors.append(str(exc)[:180])
    raise RuntimeError(f"Unable to retrieve {indicator} for {code}. The IMF API may be blocking the server, or the series key may need updating. Details: {'; '.join(errors[:2])}")


@st.cache_data(ttl=3600, show_spinner=False)
def country_data(code):
    cpi = get_series(code, "CPI._TIX")
    fx = get_series(code, "XDC_USD_PA_RT")
    return pd.concat([cpi.rename("cpi"), fx.rename("fx_per_usd")], axis=1)


left, right = st.columns(2)
labels = list(COUNTRIES)
with left:
    name1 = st.selectbox("Country 1", labels, index=labels.index("United Kingdom"))
with right:
    name2 = st.selectbox("Country 2", labels, index=labels.index("United States"))

if name1 == name2:
    st.warning("Choose two different economies.")
    st.stop()

with st.spinner("Retrieving IMF monthly data…"):
    try:
        d1 = country_data(COUNTRIES[name1]).rename(columns={"cpi": "P1", "fx_per_usd": "FX1_per_USD"})
        d2 = country_data(COUNTRIES[name2]).rename(columns={"cpi": "P2", "fx_per_usd": "FX2_per_USD"})
    except Exception as exc:
        st.error(str(exc))
        st.info("Check IMF API availability and series coverage. Missing data are never replaced with estimated values.")
        st.stop()

all_data = d1.join(d2, how="outer").sort_index()
all_data = all_data[all_data.index >= pd.Period("1976-01", freq="M")]
valid = all_data.dropna(subset=["P1", "P2", "FX1_per_USD", "FX2_per_USD"]).copy()
valid = valid[(valid[["P1", "P2", "FX1_per_USD", "FX2_per_USD"]] > 0).all(axis=1)]
if valid.empty:
    st.error("No overlapping CPI and FX observations were found for this pair.")
    st.stop()

start_avail, end_avail = valid.index.min(), valid.index.max()
a, b = st.columns(2)
with a:
    start = st.date_input("Start month", value=start_avail.to_timestamp().date(),
                          min_value=start_avail.to_timestamp().date(), max_value=end_avail.to_timestamp().date())
with b:
    end = st.date_input("End month", value=end_avail.to_timestamp().date(),
                        min_value=start_avail.to_timestamp().date(), max_value=end_avail.to_timestamp().date())
start_p, end_p = pd.Period(start, freq="M"), pd.Period(end, freq="M")
if start_p > end_p:
    st.error("Start month must be on or before end month.")
    st.stop()

sample = valid.loc[(valid.index >= start_p) & (valid.index <= end_p)].copy()
if sample.empty:
    st.warning("No overlapping valid observations in the selected date range.")
    st.stop()

# IMF FX quotes are units of local currency per USD.
# S = (Country 2 currency/USD) / (Country 1 currency/USD).
sample["S"] = sample["FX2_per_USD"] / sample["FX1_per_USD"]
sample["RER"] = sample["S"] * sample["P1"] / sample["P2"]
rer_star = sample["RER"].mean()
sample["Real_Index"] = 100 * sample["RER"] / rer_star
sample.index.name = "Month"

st.subheader("Results")
c1, c2, c3 = st.columns(3)
c1.metric("Valid monthly observations", f"{len(sample):,}")
c2.metric("Sample average RER (RER*)", f"{rer_star:.5f}")
c3.metric("Average real index", f"{sample['Real_Index'].mean():.2f}")
st.caption(f"S = {name2} currency per 1 unit of {name1} currency. IMF FX inputs are local currency per USD; S = FX2 / FX1. Missing months are excluded.")

view = st.radio("Chart view", ["Both", "Real", "Nominal"], horizontal=True)
x = sample.index.to_timestamp()
if view == "Both":
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=x, y=sample["Real_Index"], name="Real index (mean 100)", mode="lines"), secondary_y=False)
    fig.add_trace(go.Scatter(x=x, y=sample["S"], name="Nominal S (currency units)", mode="lines"), secondary_y=True)
    fig.update_yaxes(title_text="Real index (sample mean = 100)", secondary_y=False)
    fig.update_yaxes(title_text=f"{name2} currency / {name1} currency", secondary_y=True)
else:
    fig = go.Figure()
    if view == "Real":
        fig.add_trace(go.Scatter(x=x, y=sample["Real_Index"], name="Real index", mode="lines"))
        fig.update_yaxes(title_text="Real index (sample mean = 100)")
    else:
        fig.add_trace(go.Scatter(x=x, y=sample["S"], name="Nominal exchange rate", mode="lines"))
        fig.update_yaxes(title_text=f"{name2} currency / {name1} currency")
fig.update_layout(xaxis_title="Month", hovermode="x unified", height=520, legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)

out = sample.reset_index()
out["Month"] = out["Month"].astype(str)
st.download_button("Download selected sample as CSV", data=out.to_csv(index=False).encode("utf-8"),
                   file_name=f"rer_{COUNTRIES[name1]}_{COUNTRIES[name2]}.csv", mime="text/csv")
with st.expander("View calculations"):
    st.dataframe(out, use_container_width=True)
    st.latex(r"S_t = \frac{FX_{2,t}}{FX_{1,t}}, \quad RER_t = S_t\frac{P_{1,t}}{P_{2,t}}, \quad RER^* = \operatorname{mean}(RER_t), \quad RealIndex_t = 100\frac{RER_t}{RER^*}")
