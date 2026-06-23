import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

# --- CONFIG & LOGO ---
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/zauberflo/aquariumcalc/main/logo.png"
def get_logo():
    try: return Image.open(BytesIO(requests.get(GITHUB_LOGO_URL).content))
    except: return "🐠"

st.set_page_config(page_title="AquaCalc Cloud 572", page_icon=get_logo(), layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

# --- DATA LOADING ---
def load_data(sheet_name):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0).dropna(how="all")
    except: return pd.DataFrame()

def clean_df(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe", "IntervallDosis"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    d["Datum"] = d["Datum"].astype(str)
    return d

# Setup laden
df_setup = load_data("Setup")
setup_vals = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0}
if not df_setup.empty:
    for _, row in df_setup.iterrows():
        if row["Parameter"] in setup_vals: setup_vals[row["Parameter"]] = float(row["Wert"])

if "kh_dosis_live" not in st.session_state: st.session_state.kh_dosis_live = setup_vals["KH_Dosis"]
if "ca_dosis_live" not in st.session_state: st.session_state.ca_dosis_live = setup_vals["CA_Dosis"]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=setup_vals["Volumen"])
    s_brand_kh = st.text_input("Marke KH", value=setup_vals["KH_Brand"])
    s_brand_ca = st.text_input("Marke Ca", value=setup_vals["CA_Brand"])
    st.number_input("Dosis KH", key="kh_dosis_live")
    st.number_input("Dosis Ca", key="ca_dosis_live")
    s_kh_f = st.number_input("KH Faktor", value=setup_vals["KH_Faktor"])
    s_ca_f = st.number_input("Ca Faktor", value=setup_vals["CA_Faktor"])

df_kh = clean_df(load_data("KH"))
df_ca = clean_df(load_data("CA"))

# --- HAUPTSEITE ---
st.title("🌊 Zauberflos AquaCalc Cloud")
c_in1, c_in2 = st.columns(2)
cfg = {
    "KH": {"df": df_kh, "brand": s_brand_kh, "current": st.session_state.kh_dosis_live, "factor": s_kh_f, "col": c_in1},
    "CA": {"df": df_ca, "brand": s_brand_ca, "current": st.session_state.ca_dosis_live, "factor": s_ca_f, "col": c_in2}
}

for key, c in cfg.items():
    with c["col"]:
        st.subheader(f"🧪 {c['brand']} Messung")
        val_in = st.number_input(f"Messwert", key=f"v_{key}")
        if st.button(f"💾 Speichern {key}", key=f"s_{key}"):
            new_row = {"Datum": str(datetime.now().date()), "Wert": val_in, "Zugabe": 0, "IntervallDosis": c["current"]}
            conn.update(spreadsheet=SHEET_URL, worksheet=key, data=pd.concat([c["df"], pd.DataFrame([new_row])]))
            st.rerun()

st.divider()
st.header("⏱️ Aktuelle Entwicklung")
for key, c in cfg.items():
    if len(c["df"]) >= 2:
        last, prev = c["df"].iloc[-1], c["df"].iloc[-2]
        # Berechnung fixiert: Nutzt den historischen Dosiswert des letzten Messpunkts
        h_dosis = float(last.get("IntervallDosis", c["current"]))
        tage = (pd.to_datetime(last["Datum"]) - pd.to_datetime(prev["Datum"])).days
        if tage > 0:
            verbrauch = ((float(prev["Wert"]) - float(last["Wert"])) / tage) + (h_dosis / (s_vol/100) / c["factor"])
            empfehlung = round(verbrauch * (s_vol/100) * c["factor"], 1)
            st.write(f"**{key} Empfehlung:** {empfehlung} ml (Basis: {h_dosis} ml)")
            if st.button(f"✅ Übernehmen {key}"):
                c["df"].at[c["df"].index[-1], "IntervallDosis"] = empfehlung
                conn.update(spreadsheet=SHEET_URL, worksheet=key, data=c["df"])
                st.rerun()

with st.expander("📊 Historie"):
    st.dataframe(df_kh)
    st.dataframe(df_ca)
