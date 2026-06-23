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

# --- DATA LOADING & CLEANING ---
def load_data(sheet_name):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0).dropna(how="all")
    except: return pd.DataFrame()

def clean_df(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe", "IntervallDosis"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    d["IntervallDosis"] = pd.to_numeric(d["IntervallDosis"], errors='coerce').fillna(0.0)
    d["Datum"] = d["Datum"].astype(str).replace("nan", str(datetime.now().date()))
    return d[["Datum", "Wert", "Zugabe", "IntervallDosis"]].reset_index(drop=True)

# 1. SETUP-DATEN LADEN
df_setup = load_data("Setup")
setup_vals = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0, "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0}
if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        if p in setup_vals:
            try: setup_vals[p] = float(row["Wert"])
            except: setup_vals[p] = row["Wert"]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=float(setup_vals["Volumen"]))
    s_brand_kh = st.text_input("Marke KH-Lösung", value=str(setup_vals["KH_Brand"]))
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=str(setup_vals["CA_Brand"]))
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    s_kh_d = st.number_input("Dosis KH", value=float(setup_vals["KH_Dosis"]))
    s_ca_d = st.number_input("Dosis CA", value=float(setup_vals["CA_Dosis"]))
    s_kh_f = st.number_input("KH Faktor", value=float(setup_vals["KH_Faktor"]))
    s_ca_f = st.number_input("CA Faktor", value=float(setup_vals["CA_Faktor"]))
    target_kh = st.number_input("Wunsch-KH", value=7.5)
    target_ca = st.number_input("Wunsch-Calcium", value=420)
    if st.button("💾 Setup manuell speichern"):
        df_new = pd.DataFrame({"Parameter": list(setup_vals.keys()), "Wert": [s_vol, s_brand_kh, s_brand_ca, s_kh_d, s_ca_d, s_kh_f, s_ca_f, 0.0, 0.0]})
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=df_new)
        st.rerun()

# --- HAUPTTEIL ---
st.title("🌊 Zauberflos AquaCalc Cloud")
c_in1, c_in2 = st.columns(2)
cfg = {
    "KH": {"df": clean_df(load_data("KH")), "brand": s_brand_kh, "dosis": s_kh_d, "factor": s_kh_f, "target": target_kh, "is_ca": False, "col": c_in1, "unit": "dKH", "step": 1.0},
    "CA": {"df": clean_df(load_data("CA")), "brand": s_brand_ca, "dosis": s_ca_d, "factor": s_ca_f, "target": target_ca, "is_ca": True, "col": c_in2, "unit": "mg/l", "step": 5.0}
}

# --- BERECHNUNG & INPUT ---
for key, c in cfg.items():
    with c["col"]:
        st.subheader(f"🧪 {c['brand']} Messung")
        val = st.number_input(f"Messwert", key=f"val_{key}")
        extra = st.number_input("Extra-Zugabe (ml)", key=f"ext_{key}")
        if st.button(f"💾 Speichern {key}"):
            new_row = {"Datum": str(datetime.now().date()), "Wert": val, "Zugabe": extra, "IntervallDosis": c["dosis"]}
            conn.update(spreadsheet=SHEET_URL, worksheet=key, data=pd.concat([c["df"], pd.DataFrame([new_row])]))
            st.rerun()

        # RECHEN-LOGIK (Strikt auf Tabellendaten)
        if len(c["df"]) >= 2:
            last, prev = c["df"].iloc[-1], c["df"].iloc[-2]
            tage = (pd.to_datetime(last["Datum"]) - pd.to_datetime(prev["Datum"])).days
            if tage > 0:
                f_k = c["factor"] / 10 if c["is_ca"] else c["factor"]
                hist_d = float(prev["IntervallDosis"]) if float(prev["IntervallDosis"]) > 0 else c["dosis"]
                v_real = ((prev["Wert"] - last["Wert"]) / tage) + (hist_d / (s_vol/100) / f_k)
                d_neu = round(v_real * (s_vol/100) * f_k, 1)
                st.metric(f"Empfohlene Dosis", f"{d_neu} ml", f"{round(d_neu - hist_d, 1)} ml vs. Basis")
                if st.button(f"✅ Übernehmen {key}"):
                    c["df"].at[c["df"].index[-1], "IntervallDosis"] = d_neu
                    conn.update(spreadsheet=SHEET_URL, worksheet=key, data=c["df"])
                    st.rerun()

# --- HISTORIE ---
st.divider()
with st.expander("📊 Historie & Verlauf", expanded=True):
    h1, h2 = st.columns(2)
    for key, col in [("KH", h1), ("CA", h2)]:
        with col:
            df = clean_df(load_data(key))
            st.dataframe(df)
            if st.button(f"❌ Löschen {key}"):
                conn.update(spreadsheet=SHEET_URL, worksheet=key, data=df.iloc[:-1])
                st.rerun()
