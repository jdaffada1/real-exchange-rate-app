import io
import json
import html
import numpy as np
import streamlit.components.v1 as components
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(page_title="FX Jungle 🦍", layout="wide")
st.markdown("""<style>
.stApp {background: radial-gradient(ellipse at 85% 0%, #152642 0%, #0c1325 40%, #090f1c 100%); color:#edf4ff}
[data-testid="stHeader"] {background:transparent}
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"] {color:#f5f8ff;}
/* Keep the dramatic dark jungle, but make every primary label legible. */
[data-testid="stMain"] p, [data-testid="stMain"] label,
[data-testid="stMain"] span, [data-testid="stMain"] h1,
[data-testid="stMain"] h2, [data-testid="stMain"] h3,
[data-testid="stMain"] h4, [data-testid="stMain"] li,
[data-testid="stMain"] [data-testid="stMarkdownContainer"] {color:#f2f7ff;}
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] p,
[data-testid="stMain"] small {color:#cad9ed !important;}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {color:#e2edff !important;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {color:#80f2db !important;}
/* Form fields and radio choices stay readable in both light/dark browser themes. */
[data-baseweb="select"] > div, [data-baseweb="input"] > div,
[data-testid="stDateInput"] input {background-color:#203653 !important;color:#fff !important;border-color:#6d89aa !important;}
[data-baseweb="select"] span, [data-baseweb="select"] input,
[data-testid="stDateInput"] input, [data-testid="stRadio"] label,
[data-testid="stRadio"] label p {color:#fff !important;}
[role="listbox"], [role="option"] {background-color:#203653 !important;color:#fff !important;}
[role="option"]:hover {background-color:#34567d !important;}
[data-testid="stExpander"] {background:#162a44;border:1px solid #41617e;border-radius:12px;}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {color:#f5f8ff !important;}
[data-testid="stDownloadButton"] button {background:#3de0bd;color:#071729;font-weight:800;border:0;}
[data-testid="stDownloadButton"] button p {color:#071729 !important;}

h1,h2,h3 {letter-spacing:-.035em}
[data-testid="stMetric"] {background:linear-gradient(145deg,#1c3150,#102038);border:1px solid #345275;border-radius:18px;padding:18px}
[data-testid="stMetricValue"] {color:#80f2db}
.stButton button {border-radius:16px;background:linear-gradient(95deg,#10bfa5,#7b5ce5);color:white;border:0;font-weight:750;transition:transform .18s,filter .18s}
.stButton button:hover {transform:scale(1.045);filter:brightness(1.2)}
[data-testid="stPlotlyChart"] {border-radius:20px;overflow:hidden}
.pulse-title, .pulse-title * {color:transparent !important;}
.pulse-title {font-size:clamp(32px,5vw,62px);font-weight:900;line-height:1.08;background:linear-gradient(90deg,#8cf7db,#d7b4ff,#ffb88e);color:transparent;background-clip:text;-webkit-background-clip:text;animation:shine 5s ease-in-out infinite alternate}
@keyframes shine {from{filter:hue-rotate(0deg)}to{filter:hue-rotate(28deg)}}
.fun-caption {color:#d5e4f6 !important;margin-bottom:16px}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="pulse-title">🦍 THE FX JUNGLE</div>', unsafe_allow_html=True)
st.markdown('<div class="fun-caption">Real Exchange Rate Explorer · IMF monthly data since 1976 · Kellogg economics lab</div>', unsafe_allow_html=True)

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
HEADERS = {"Accept": "application/vnd.sdmx.structurespecificdata+xml, application/xml, text/xml", "User-Agent": "Mozilla/5.0 (compatible; educational-exchange-rate-app/1.2)"}


def parse_imf_response(content):
    """Read SDMX 3.0 structure-specific XML or SDMX CSV."""
    import xml.etree.ElementTree as ET
    stripped = content.lstrip()
    if stripped.startswith(b"<"):
        root = ET.fromstring(content)
        observations = []
        for node in root.iter():
            if node.tag.split("}")[-1] != "Obs":
                continue
            period = node.attrib.get("TIME_PERIOD")
            value = node.attrib.get("OBS_VALUE")
            if period and value:
                observations.append((period, value))
        if not observations:
            return pd.Series(dtype=float)
        frame = pd.DataFrame(observations, columns=["TIME_PERIOD", "OBS_VALUE"])
    else:
        frame = pd.read_csv(io.BytesIO(content), low_memory=False)
        cols = {str(c).strip().upper(): c for c in frame.columns}
        if "TIME_PERIOD" not in cols or "OBS_VALUE" not in cols:
            raise ValueError(f"Unexpected IMF response columns: {list(frame.columns)[:10]}")
        frame = frame.rename(columns={cols["TIME_PERIOD"]: "TIME_PERIOD", cols["OBS_VALUE"]: "OBS_VALUE"})
    months = frame["TIME_PERIOD"].astype(str).str.replace(r"-M(?=\d{2}$)", "-", regex=True)
    dates = pd.to_datetime(months, errors="coerce")
    values = pd.to_numeric(frame["OBS_VALUE"], errors="coerce")
    result = pd.Series(values.to_numpy(), index=dates.dt.to_period("M"))
    return result[result.index.notna()].dropna().groupby(level=0).last().sort_index()


@st.cache_data(ttl=3600, show_spinner=False)
def get_series(code, kind):
    """Fetch official monthly IMF CPI or exchange rates using current SDMX 3.0 keys."""
    if kind == "cpi":
        dataflow = "CPI"
        key = f"{code}.CPI._T.IX.M"
    elif kind == "fx":
        if code == "USA":
            # USD per USD is identically 1; the IMF may not publish this identity series.
            return None
        dataflow = "ER"
        key = f"{code}.XDC_USD.PA_RT.M"
    else:
        raise ValueError("Unknown IMF indicator")
    url = f"{BASE}/data/dataflow/IMF.STA/{dataflow}/~/{key}"
    params = {"c[TIME_PERIOD]": "ge:1976-M01"}
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=45)
        response.raise_for_status()
        result = parse_imf_response(response.content)
        if result.empty:
            raise ValueError("The IMF returned no observations for this series")
        return result
    except (requests.RequestException, ValueError, pd.errors.ParserError, ET.ParseError) as exc:
        raise RuntimeError(f"IMF {dataflow} data unavailable for {code} ({key}): {exc}. Request: {response.url if 'response' in locals() else url}") from exc


@st.cache_data(ttl=3600, show_spinner=False)
def country_data(code):
    cpi = get_series(code, "cpi")
    fx = get_series(code, "fx")
    if fx is None:
        fx = pd.Series(1.0, index=cpi.index)
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
# Explicit year/month selectors avoid Streamlit's date picker showing only a
# small decade-sized window. Every available year can be selected directly.
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
available_years = list(range(start_avail.year, end_avail.year + 1))
st.caption(f"Available data: {start_avail.strftime('%B %Y')} through {end_avail.strftime('%B %Y')}. Select any year directly.")
a, b = st.columns(2)
with a:
    st.markdown("**Start date**")
    sy, sm = st.columns(2)
    with sy:
        start_year = st.selectbox("Start year", available_years, index=0, key="fx_start_year")
    with sm:
        start_month = st.selectbox("Start month", MONTHS, index=start_avail.month - 1, key="fx_start_month")
with b:
    st.markdown("**End date**")
    ey, em = st.columns(2)
    with ey:
        end_year = st.selectbox("End year", available_years, index=len(available_years) - 1, key="fx_end_year")
    with em:
        end_month = st.selectbox("End month", MONTHS, index=end_avail.month - 1, key="fx_end_month")
start_p = pd.Period(year=start_year, month=MONTHS.index(start_month) + 1, freq="M")
end_p = pd.Period(year=end_year, month=MONTHS.index(end_month) + 1, freq="M")
if start_p < start_avail or end_p > end_avail:
    st.error(f"Choose dates between {start_avail} and {end_avail}.")
    st.stop()
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

# Extra classroom lens: relative PPP predicts an unchanged real exchange rate.
# Volatility uses monthly log returns, annualized by sqrt(12).
real_dev = (sample["Real_Index"].iloc[-1] / 100 - 1) * 100
fx_log = np.log(sample["S"] / sample["S"].shift(1)).dropna()
annual_vol = fx_log.std(ddof=1) * np.sqrt(12) * 100 if len(fx_log) > 1 else float("nan")

st.markdown("### 🎓 Economics lab — ideas from class")
l1, l2, l3 = st.columns(3)
l1.metric("PPP deviation · latest month", f"{real_dev:+.1f}%", help="Latest real index minus 100, expressed as a percentage. This is a sample-relative PPP diagnostic, not a claim about fair value.")
l2.metric("Annualized nominal FX volatility", f"{annual_vol:.1f}%" if np.isfinite(annual_vol) else "N/A", help="Standard deviation of monthly log exchange-rate changes multiplied by sqrt(12). Descriptive historical estimate, not a forecast.")
l3.metric("Real index at latest month", f"{sample['Real_Index'].iloc[-1]:.1f}")
with st.expander("📚 Why this matters in international finance"):
    st.markdown("""**Relative purchasing power parity (PPP):** if exchange rates perfectly offset relative inflation, the real exchange rate stays constant. The index at **100** is the *selected sample average*, not a universal equilibrium level. A value above 100 means the real exchange rate is above its own sample mean.

**Exchange-rate volatility:** annualized monthly FX volatility is computed as `std(log(Sₜ/Sₜ₋₁)) × √12`. This is the historical risk measure discussed in class; it is **not** a forecast.

**Random-walk benchmark:** short-horizon exchange rates are difficult to predict; a useful benchmark for next month's nominal exchange rate is simply this month's value. The app reports actual observations rather than inventing a forecast.""")

st.markdown("### 🎛️ Choose your experience")
view = st.radio("Chart view", ["Both", "Real", "Nominal"], horizontal=True)
mode = st.radio("Visualization", ["🦍 Gorilla sneeze mode", "📈 Classic analyst chart"], horizontal=True)

# This is an actual animated data visualization, not a screenshot. The data line
# is drawn from the gorilla's nose by JavaScript in an embedded Streamlit component.
def gorilla_chart(data, selection, country1, country2):
    records = [{"month": str(month), "real": float(row["Real_Index"]), "nominal": float(row["S"])}
               for month, row in data.iterrows()]
    payload = json.dumps({"rows": records, "view": selection, "country1": country1, "country2": country2})
    template = r"""<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:#0b1728;color:#e9f5ff;font-family:system-ui,Arial,sans-serif}
#stage{position:relative;width:100%;height:530px;overflow:hidden;border:1px solid #355472;border-radius:24px;background:radial-gradient(circle at 18% 42%,#314b62 0%,#10253a 31%,#0b1728 78%)}
#canvas{width:100%;height:100%;display:block}
.controls{position:absolute;top:15px;right:15px;display:flex;gap:9px;align-items:center;z-index:3}
button{background:#77efd6;color:#071729;border:0;border-radius:12px;padding:10px 14px;font-weight:850;cursor:pointer;box-shadow:0 4px 20px #32cfa64a}button:hover{transform:scale(1.05)}
#status{font-size:12px;color:#b5c8dc;background:#122a43c9;padding:9px 12px;border-radius:12px}
#spectacle{position:absolute;inset:0;z-index:4;pointer-events:none;overflow:hidden}
#megaGorilla{position:absolute;left:50%;top:53%;transform:translate(-50%,120%) scale(.15) rotate(-17deg);font-size:clamp(150px,31vw,330px);line-height:1;filter:drop-shadow(0 22px 28px #000b);opacity:0;transition:none;text-align:center}
#megaGorilla .face{display:block;transform-origin:center;animation:none}
#megaGorilla .caption{display:block;font-size:clamp(15px,2.7vw,29px);font-weight:1000;letter-spacing:.12em;color:#fff;text-shadow:0 5px 0 #1a2046,0 0 30px #ffce43}
#blastText{position:absolute;left:50%;top:46%;transform:translate(-50%,-50%) scale(.1) rotate(-12deg);opacity:0;font-size:clamp(58px,12vw,155px);font-weight:1000;letter-spacing:-.08em;color:#ffef5a;-webkit-text-stroke:4px #1c214e;text-shadow:9px 12px 0 #f3457c,0 0 70px #ffb839;white-space:nowrap}
#wind{position:absolute;left:50%;top:50%;font-size:clamp(65px,14vw,150px);opacity:0;transform:translate(-50%,-50%) rotate(-15deg)}
#stage.prep #megaGorilla{animation:gorillaPop 1.6s cubic-bezier(.15,.8,.2,1) both}
#stage.prep #megaGorilla .face{animation:sniff .23s ease-in-out 4 alternate}
#stage.blast{animation:screenShake .42s ease-in-out}
#stage.blast #megaGorilla{opacity:1;transform:translate(-50%,-51%) scale(1.5) rotate(8deg);animation:gorillaExit 1.25s ease-in forwards}
#stage.blast #blastText{animation:comicBlast 1.2s cubic-bezier(.15,.85,.25,1) both}
#stage.blast #wind{animation:windBlast 1.15s ease-out both}
@keyframes gorillaPop{0%{opacity:0;transform:translate(-50%,110%) scale(.12) rotate(-22deg)}55%{opacity:1;transform:translate(-50%,-58%) scale(1.25) rotate(8deg)}75%{transform:translate(-50%,-47%) scale(.96) rotate(-4deg)}100%{opacity:1;transform:translate(-50%,-51%) scale(1.05)}}
@keyframes sniff{from{transform:scale(.94,1.04) rotate(-5deg)}to{transform:scale(1.09,.9) rotate(6deg)}}
@keyframes gorillaExit{0%{opacity:1;transform:translate(-50%,-51%) scale(1.05)}28%{opacity:1;transform:translate(-50%,-51%) scale(1.55) rotate(-9deg)}100%{opacity:0;transform:translate(140%,-80%) scale(2.5) rotate(30deg)}}
@keyframes comicBlast{0%{opacity:0;transform:translate(-50%,-50%) scale(.1) rotate(-20deg)}18%{opacity:1;transform:translate(-50%,-50%) scale(1.2) rotate(9deg)}35%{transform:translate(-50%,-50%) scale(.98) rotate(-5deg)}65%{opacity:1;transform:translate(-50%,-50%) scale(1.12)}100%{opacity:0;transform:translate(80%,-80%) scale(2.5) rotate(18deg)}}
@keyframes windBlast{0%{opacity:0;transform:translate(-40%,-50%) scale(.3)}30%{opacity:1;transform:translate(20%,-50%) scale(1.3)}100%{opacity:0;transform:translate(280%,-50%) scale(2.6)}}
@keyframes screenShake{0%,100%{transform:translate(0)}15%,45%,75%{transform:translate(-8px,5px)}30%,60%,90%{transform:translate(9px,-5px)}}
@media(prefers-reduced-motion:reduce){#stage,#stage *{animation-duration:.01ms!important;transition-duration:.01ms!important}}
#tooltip{position:absolute;display:none;background:#091b2cf2;border:1px solid #70e8d0;border-radius:12px;padding:9px 12px;font-size:12px;pointer-events:none;z-index:5;white-space:nowrap}
.legend{position:absolute;left:14px;bottom:13px;font-size:12px;color:#c2d6e5;background:#0a1a2ac9;padding:9px 12px;border-radius:10px}
@media(max-width:650px){#stage{height:450px}.controls{right:7px;top:7px}#status{display:none}}
</style></head><body><div id="stage"><canvas id="canvas"></canvas><div class="controls"><span id="status">🤧 Ready to sneeze</span><button id="sneeze">💨 ACHOO! Replay</button></div><div id="spectacle"><div id="megaGorilla"><span class="face">🦍</span><span class="caption">UH OH... TICKLE IN MY NOSE!</span></div><div id="blastText">AAA-CHOOOO!!</div><div id="wind">💨💥🌪️</div></div><div id="tooltip"></div><div class="legend">🟢 Real index (mean 100) &nbsp; 🟣 Nominal FX (currency units)<br>Axes use independent true scales · Hover for exact IMF values</div></div>
<script>
const cfg=__DATA__; const rows=cfg.rows;const canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d');const stage=document.getElementById('stage');const tip=document.getElementById('tooltip');let W=1000,H=530,dpr=1,progress=0,particles=[],raf=0,hover=-1;
function resize(){const r=stage.getBoundingClientRect();W=r.width;H=r.height;dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.floor(W*dpr);canvas.height=Math.floor(H*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);draw()}
const real=rows.map(r=>r.real),nom=rows.map(r=>r.nominal);
function range(v){let lo=Math.min(...v),hi=Math.max(...v),d=hi-lo||1;return [lo-d*.13,hi+d*.13]}
const rr=range(real),nr=range(nom);
function line(color,width=2){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin='round';ctx.lineCap='round'}
function ellipse(x,y,rx,ry,color,rot=0){ctx.beginPath();ctx.ellipse(x,y,rx,ry,rot,0,Math.PI*2);ctx.fillStyle=color;ctx.fill()}
function text(t,x,y,size,color,weight='600'){ctx.font=weight+' '+size+'px system-ui';ctx.fillStyle=color;ctx.fillText(t,x,y)}
function drawGorilla(){ctx.save();const sc=Math.min(W/1000,H/530);ctx.translate(W*.13,H*.51);ctx.scale(sc,sc);
// Layered, shaded silverback portrait, rendered live in Canvas (not a static image).
const grad=(x,y,r,stops)=>{let g=ctx.createRadialGradient(x-r*.3,y-r*.4,2,x,y,r);for(const [t,c] of stops)g.addColorStop(t,c);return g};
const oval=(x,y,rx,ry,fill,rot=0)=>{ctx.save();ctx.translate(x,y);ctx.rotate(rot);ctx.beginPath();ctx.ellipse(0,0,rx,ry,0,0,Math.PI*2);ctx.fillStyle=fill;ctx.fill();ctx.restore()};
const stroke=(points,color,w)=>{ctx.beginPath();ctx.moveTo(...points[0]);for(let i=1;i<points.length;i++)ctx.lineTo(...points[i]);ctx.strokeStyle=color;ctx.lineWidth=w;ctx.lineCap='round';ctx.stroke()};
// Massive shoulders and neck, with silverback highlights.
oval(-18,125,166,146,grad(-25,120,195,[[0,'#74828a'],[.38,'#45505b'],[.76,'#242a33'],[1,'#111821']]));
oval(-120,128,75,117,'#252e38',-.35);oval(104,134,78,115,'#202932',.33);
// Rounded ears recessed into the head.
oval(-102,-42,42,56,'#20262e',-.18);oval(103,-43,41,55,'#1c242d',.18);
oval(-102,-39,26,39,'#4c4a4b',-.18);oval(103,-40,25,37,'#514f4f',.18);
oval(-99,-36,13,23,'#181e25',-.2);oval(101,-37,12,23,'#1b2026',.2);
// Skull and heavy brow ridge.
oval(0,-19,121,133,grad(-18,-62,150,[[0,'#68737a'],[.35,'#3c4750'],[.73,'#252e38'],[1,'#101820']]));
oval(-3,-100,90,47,grad(-18,-106,108,[[0,'#687078'],[.7,'#39434d'],[1,'#222b35']]));
oval(1,-40,111,38,'#303842');
oval(-44,-42,55,26,'#222932',-.13);oval(46,-42,55,26,'#222932',.13);
// Deep-set eyes: lids, irises, wet highlights.
for(const [ex,ey] of [[-45,-29],[44,-29]]){oval(ex,ey,30,19,'#171b20');oval(ex,ey+2,21,12,'#9e9789');oval(ex,ey+2,13,12,'#5d4636');oval(ex+2,ey+2,8,10,'#171c20');oval(ex-3,ey-2,3.2,3.2,'#f7f2e7');oval(ex+6,ey+7,1.6,1.6,'#d1c6ae');}
// Broad leather-like muzzle with dimensional shading.
oval(4,42,91,77,grad(-22,17,120,[[0,'#8c8580'],[.4,'#6b6765'],[.78,'#44464a'],[1,'#272d33']]));
oval(4,12,62,47,grad(-18,-1,91,[[0,'#9d9590'],[.55,'#736c68'],[1,'#4c4b4c']]));
// Nose bridge and nostrils, with rim highlights.
oval(14,22,75,39,grad(-5,13,87,[[0,'#98908a'],[.56,'#6b6562'],[1,'#3a3c40']]));
oval(-32,36,20,12,'#26282b',-.13);oval(61,37,19,12,'#202327',.1);
oval(-36,32,9,3,'#9a8d84',-.2);oval(55,32,8,3,'#a4998f',.2);
// Mouth and subtle expression change when sneezing.
oval(7,91,61,22,'#383536');oval(8,93,53,11,'#17181c');
if(progress<.32){oval(8,92,35,17,'#171619');oval(9,98,20,6,'#aa7778');}else{stroke([[-39,91],[-16,97],[11,100],[38,96],[55,91]],'#151a20',5);stroke([[-20,105],[5,110],[30,105]],'#95827c',2)}
// Fine fur strokes following skull and shoulder contours, deterministic texture.
let seed=314159;function rand(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}
ctx.save();ctx.beginPath();ctx.ellipse(0,-19,120,133,0,0,Math.PI*2);ctx.clip();
for(let i=0;i<920;i++){const x=(rand()-.5)*250,y=(rand()-.5)*280;if(y>6&&Math.abs(x)<90)continue;const length=2+rand()*9;const ang=(x<0?-.7:.7)+(rand()-.5)*.8;stroke([[x,y],[x+Math.sin(ang)*length,y+Math.cos(ang)*length]],rand()>.5?'#87919826':'#090f192f',.4+rand()*.9)}ctx.restore();
ctx.save();ctx.beginPath();ctx.ellipse(-18,125,164,145,0,0,Math.PI*2);ctx.clip();for(let i=0;i<580;i++){let x=(rand()-.5)*345,y=20+rand()*240;let ang=(x<0?-.8:.8)+(rand()-.5)*.5;let l=3+rand()*13;stroke([[x,y],[x+Math.sin(ang)*l,y+Math.cos(ang)*l]],rand()>.42?'#bac0c026':'#0a111d32',.5+rand())}ctx.restore();
// Sneezing air glows from the right nostril (the graph's actual origin).
if(progress<.34){ctx.save();ctx.shadowBlur=24;ctx.shadowColor='#9dfbe5';oval(61,37,5+Math.sin(progress*90)*2,5,'#b5fff0');ctx.restore()}
ctx.restore()}
function plotArea(){const sc=Math.min(W/1000,H/530);return {left:Math.max(W*.13+65*sc,W*.30),right:W-(cfg.view==='Both'?66:28),top:94,bottom:H-91};}
function coords(i,arr,bounds){const a=plotArea();const x=a.left+(a.right-a.left)*(rows.length===1?.5:i/(rows.length-1));const t=(arr[i]-bounds[0])/(bounds[1]-bounds[0]);return [x,a.bottom-(a.bottom-a.top)*t]}
function axisLabel(t,x,y,color,align='left',size=12){ctx.fillStyle=color;ctx.font='600 '+size+'px system-ui';ctx.textAlign=align;ctx.fillText(t,x,y);ctx.textAlign='left'}
function drawAxes(){const a=plotArea();const hasReal=cfg.view!=='Nominal',hasNom=cfg.view!=='Real';
  // The two series always have separate, true numeric scales when both are visible.
  for(let k=0;k<=4;k++){const y=a.bottom-(a.bottom-a.top)*k/4;line('#8da9c04b',1);ctx.beginPath();ctx.moveTo(a.left,y);ctx.lineTo(a.right,y);ctx.stroke();
    if(hasReal)axisLabel((rr[0]+(rr[1]-rr[0])*k/4).toFixed(1),a.left-9,y+4,'#79f9d8','right',11);
    if(hasNom)axisLabel((nr[0]+(nr[1]-nr[0])*k/4).toFixed(3),hasReal?a.right+9:a.left-9,y+4,'#c3a0ff',hasReal?'left':'right',11);
  }
  const n=Math.min(6,rows.length);for(let k=0;k<n;k++){const i=n===1?0:Math.round(k*(rows.length-1)/(n-1));const [x]=coords(i,real,rr);axisLabel(rows[i].month.slice(0,7),x,a.bottom+22,'#d4e4f4','center',10)}
  axisLabel('Month', (a.left+a.right)/2,a.bottom+46,'#eaf4ff','center',13);
  if(hasReal)axisLabel('REAL INDEX · sample mean = 100',a.left,78,'#79f9d8','left',11);
  if(hasNom)axisLabel('NOMINAL S · '+cfg.country2+' currency / '+cfg.country1+' currency',a.right,hasReal?93:78,'#c3a0ff','right',11);
}
function drawTrace(arr,bounds,color,limit){const n=Math.min(arr.length,Math.max(0,Math.floor(limit*arr.length)));if(!n)return;const ox=W*.13+65*Math.min(W/1000,H/530),oy=H*.51+37*Math.min(W/1000,H/530);ctx.save();ctx.shadowBlur=15;ctx.shadowColor=color;line(color,3);ctx.beginPath();ctx.moveTo(ox,oy);for(let i=0;i<n;i++){const [x,y]=coords(i,arr,bounds);ctx.lineTo(x,y)}ctx.stroke();ctx.shadowBlur=0;for(let i=0;i<n;i+=Math.max(1,Math.floor(rows.length/16))){const [x,y]=coords(i,arr,bounds);ellipse(x,y,3,3,color)}ctx.restore()}
function draw(){ctx.clearRect(0,0,W,H);ctx.fillStyle='#132b42';ctx.globalAlpha=.3;for(let i=0;i<17;i++){const x=(i*173)%W,y=(i*127)%H;ellipse(x,y,2+(i%3),2+(i%3),'#a4ffe9')}ctx.globalAlpha=1;
drawAxes();drawGorilla();if(cfg.view!=='Nominal')drawTrace(real,rr,'#79f9d8',progress);if(cfg.view!=='Real')drawTrace(nom,nr,'#c3a0ff',progress);
text('FX JUNGLE',Math.max(18,W*.29),35,Math.min(25,W*.032),'#e9f5ff','850');text(cfg.country1+' → '+cfg.country2,Math.max(18,W*.29),56,12,'#b9cde1');
for(const p of particles){ellipse(p.x,p.y,p.size,p.size,p.color);p.x+=p.vx;p.y+=p.vy;p.life--;p.size*=.985}particles=particles.filter(p=>p.life>0);
if(hover>=0&&progress>.98){const arr=cfg.view==='Nominal'?nom:real,b=cfg.view==='Nominal'?nr:rr;const [x,y]=coords(hover,arr,b);ellipse(x,y,6,6,'#ffffff')}
}
function burst(){const ox=W*.13+65*Math.min(W/1000,H/530),oy=H*.51+37*Math.min(W/1000,H/530);for(let i=0;i<65;i++){const a=(Math.random()-.5)*1.6;const speed=2+Math.random()*8;particles.push({x:ox,y:oy,vx:Math.cos(a)*speed,vy:Math.sin(a)*speed,size:2+Math.random()*5,color:Math.random()>.5?'#79f9d8':'#c3a0ff',life:35+Math.random()*35})}}
function animate(){progress=Math.min(1,progress+.014);draw();if(progress<1||particles.length)raf=requestAnimationFrame(animate);else document.getElementById('status').textContent='✨ Data delivered!'}
let sneezeTimers=[];
function sneeze(){
 cancelAnimationFrame(raf);sneezeTimers.forEach(clearTimeout);sneezeTimers=[];
 stage.classList.remove('prep','blast');void stage.offsetWidth;
 progress=0;particles=[];hover=-1;tip.style.display='none';draw();
 document.getElementById('status').textContent='👃 Sniff... sniff... OH NO...';
 stage.classList.add('prep');
 sneezeTimers.push(setTimeout(()=>{
  stage.classList.remove('prep');stage.classList.add('blast');
  document.getElementById('status').textContent='💥 AAA-CHOOOO!!';
  burst();for(let i=0;i<4;i++)sneezeTimers.push(setTimeout(burst,i*140));
  animate();
 },1650));
 sneezeTimers.push(setTimeout(()=>stage.classList.remove('blast'),3100));
}
document.getElementById('sneeze').onclick=sneeze;
canvas.addEventListener('mousemove',e=>{if(progress<1)return;const r=canvas.getBoundingClientRect(),x=e.clientX-r.left;const a=plotArea();hover=Math.max(0,Math.min(rows.length-1,Math.round((x-a.left)/(a.right-a.left)*(rows.length-1))));const d=rows[hover];tip.style.display='block';tip.style.left=Math.min(W-180,Math.max(5,x+14))+'px';tip.style.top=Math.max(70,e.clientY-r.top-25)+'px';tip.textContent=d.month+(cfg.view==='Nominal'?' | Nominal S: '+d.nominal.toFixed(4):cfg.view==='Real'?' | Real index: '+d.real.toFixed(2):' | Real index: '+d.real.toFixed(2)+' | Nominal S: '+d.nominal.toFixed(4));draw()});canvas.addEventListener('mouseleave',()=>{hover=-1;tip.style.display='none';draw()});
window.addEventListener('resize',resize);resize();setTimeout(sneeze,350);
</script></body></html>"""
    components.html(template.replace("__DATA__", payload), height=540, scrolling=False)

if mode.startswith("🦍"):
    st.caption("A GIANT comic gorilla pops onto the chart, winds up, and unleashes an enormous ACHOO before the real IMF exchange-rate lines fly out of its nose. Click ACHOO to replay. Both modes now include numeric axes and exact monthly values; Classic mode offers additional zoom controls.")
    gorilla_chart(sample, view, name1, name2)
    st.caption("Real: 100 × (S × P1 / P2) / average(RER). Nominal: S = FX2 per USD ÷ FX1 per USD. In Both mode, each series uses its own labeled y-axis; no artificial offsets or normalization are applied to nominal rates.")
else:
    x = sample.index.to_timestamp()
    if view == "Both":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=x, y=sample["Real_Index"], name="Real index (mean 100)", mode="lines", line=dict(color="#77efd6",width=3)), secondary_y=False)
        fig.add_trace(go.Scatter(x=x, y=sample["S"], name="Nominal S (currency units)", mode="lines", line=dict(color="#c3a0ff",width=3)), secondary_y=True)
        fig.update_yaxes(title_text="Real index (sample mean = 100)", secondary_y=False)
        fig.update_yaxes(title_text=f"{name2} currency / {name1} currency", secondary_y=True)
    else:
        fig = go.Figure()
        if view == "Real":
            fig.add_trace(go.Scatter(x=x, y=sample["Real_Index"], name="Real index", mode="lines", line=dict(color="#77efd6",width=3)))
            fig.update_yaxes(title_text="Real index (sample mean = 100)")
        else:
            fig.add_trace(go.Scatter(x=x, y=sample["S"], name="Nominal exchange rate", mode="lines", line=dict(color="#c3a0ff",width=3)))
            fig.update_yaxes(title_text=f"{name2} currency / {name1} currency")
    fig.update_layout(xaxis_title="Month", hovermode="x unified", height=520, legend=dict(orientation="h"),paper_bgcolor="#102039",plot_bgcolor="#102039",font_color="#e8f5ff")
    st.plotly_chart(fig, use_container_width=True)

out = sample.reset_index()
out["Month"] = out["Month"].astype(str)
st.download_button("Download selected sample as CSV", data=out.to_csv(index=False).encode("utf-8"),
                   file_name=f"rer_{COUNTRIES[name1]}_{COUNTRIES[name2]}.csv", mime="text/csv")
with st.expander("View calculations"):
    st.dataframe(out, use_container_width=True)
    st.latex(r"S_t = \frac{FX_{2,t}}{FX_{1,t}}, \quad RER_t = S_t\frac{P_{1,t}}{P_{2,t}}, \quad RER^* = \operatorname{mean}(RER_t), \quad RealIndex_t = 100\frac{RER_t}{RER^*}")
