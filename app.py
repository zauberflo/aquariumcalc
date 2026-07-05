import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

# --- LOGO & KONFIGURATION ---
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/zauberflo/aquariumcalc/main/logo.png"
def get_logo():
    try: return Image.open(BytesIO(requests.get(GITHUB_LOGO_URL).content))
    except: return "🐠"

st.set_page_config(page_title="AquaCalc Cloud 572", page_icon=get_logo(), layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

def load_data(sheet_name):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0).dropna(how="all")
    except: return pd.DataFrame()

# --- SETUP & BERECHNUNGS-LOGIK ---
df_setup = load_data("Setup")
s = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", 
     "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0}
if not df_setup.empty:
    for _, row in df_setup.iterrows():
        if row["Parameter"] in s:
            try: s[row["Parameter"]] = float(row["Wert"])
            except: pass

def calculate_aquarium_strict_vB(df, current_setup_dosis, vol, factor, target_val, is_ca=False):
    df["Datum"] = pd.to_datetime(df["Datum"], errors='coerce')
    df_m = df.dropna(subset=["Wert"]).sort_values("Datum")
    if len(df_m) >= 2:
        last, prev = df_m.iloc[-1], df_m.iloc[-2]
        tage = (last["Datum"] - prev["Datum"]).days
        if tage > 0:
            f_konz = factor / 10 if is_ca else factor
            becken_diff = prev["Wert"] - last["Wert"]
            hist_dosis = prev["IntervallDosis"] if prev["IntervallDosis"] > 0 else current_setup_dosis
            toleranz = 0.1 if not is_ca else 5.0
            
            if abs(becken_diff) <= toleranz: v_real = hist_dosis / (vol / 100) / f_konz
            else: v_real = (becken_diff / tage) + (hist_dosis / (vol / 100) / f_konz)
            
            d_neu = round(v_real * (vol / 100) * f_konz, 1)
            return round(v_real, 3), d_neu, round(d_neu - current_setup_dosis, 1), round((target_val - last["Wert"]) * (vol / 100) * f_konz, 1)
    return None, None, None, None

# --- UI START ---
st.title("🌊 Zauberflos AquaCalc Cloud")

# Sidebar wie im Original
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s["Volumen"] = st.number_input("Beckenvolumen", value=s["Volumen"])
    st.divider()
    # ... hier die restlichen Felder ...
    if st.button("💾 Setup speichern"): st.success("Gespeichert!")

# Datenreinigung
def clean_df(df):
    d = df.copy()
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["IntervallDosis"] = pd.to_numeric(d["IntervallDosis"], errors='coerce').fillna(0.0)
    return d.reset_index(drop=True)

df_kh, df_ca = clean_df(load_data("KH")), clean_df(load_data("CA"))

# Berechnung & Anzeige
res1, res2 = st.columns(2)
for res, df, d_set, brand, f, target, name in [(res1, df_kh, s["KH_Dosis"], s["KH_Brand"], s["KH_Faktor"], 7.5, "KH"), (res2, df_ca, s["CA_Dosis"], s["CA_Brand"], s["CA_Faktor"], 420, "CA")]:
    v, d, delta, up = calculate_aquarium_strict_vB(df, d_set, s["Volumen"], f, target, name == "CA")
    if v:
        res.metric(f"Neue Dosis {brand}", f"{d} ml", f"{delta} ml")
        if res.button(f"✅ Aktivieren {name}"):
            df.at[df.index[-1], "IntervallDosis"] = d
            conn.update(spreadsheet=SHEET_URL, worksheet=name, data=df); st.rerun()
    else: res.write(f"Warte auf {name} Daten...")

# --- DAS ARCHIV / VERLAUF ---
st.divider()
with st.expander("📊 Historie & Verlauf", expanded=True):
    h1, h2 = st.columns(2)
    with h1:
        st.subheader(f"{s['KH_Brand']} Verlauf")
        st.line_chart(df_kh.dropna(subset=["Wert"]).set_index("Datum")["Wert"])
        st.dataframe(df_kh, use_container_width=True)
        # Lösch-Logik
        d_kh = st.selectbox("Datum KH löschen:", df_kh["Datum"].unique(), key="del_kh")
        if st.button("❌ KH löschen"):
            conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=df_kh[df_kh["Datum"] != d_kh])
            st.rerun()
    with h2:
        st.subheader(f"{s['CA_Brand']} Verlauf")
        st.line_chart(df_ca.dropna(subset=["Wert"]).set_index("Datum")["Wert"])
        st.dataframe(df_ca, use_container_width=True)
        # Lösch-Logik
        d_ca = st.selectbox("Datum CA löschen:", df_ca["Datum"].unique(), key="del_ca")
        if st.button("❌ CA löschen"):
            conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=df_ca[df_ca["Datum"] != d_ca])
            st.rerun()
