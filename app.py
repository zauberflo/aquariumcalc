import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

# --- KONFIGURATION ---
st.set_page_config(page_title="AquaCalc Cloud 572", page_icon="🐠", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

# --- DATEN-HILFSFUNKTIONEN ---
def load_data(sheet_name):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0).dropna(how="all")
    except: return pd.DataFrame()

def clean_dataframe(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe", "IntervallDosis"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    d["IntervallDosis"] = pd.to_numeric(d["IntervallDosis"], errors='coerce').fillna(0.0)
    d["Datum"] = d["Datum"].astype(str)
    return d.reset_index(drop=True)

# --- SETUP LADEN ---
df_setup = load_data("Setup")
s = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", 
     "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0}

if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        if p in s:
            try: s[p] = float(row["Wert"])
            except: pass

# --- BERECHNUNGSLOGIK (ROBUST) ---
def calculate_aquarium_strict_vB(df, current_setup_dosis, vol, factor, target_val, is_ca=False):
    df = df.copy()
    df["Datum"] = pd.to_datetime(df["Datum"], errors='coerce')
    df_m = df.dropna(subset=["Wert"]).sort_values("Datum")
    
    if len(df_m) >= 2:
        last, prev = df_m.iloc[-1], df_m.iloc[-2]
        tage = (last["Datum"] - prev["Datum"]).days
        if tage > 0:
            f_konz = factor / 10 if is_ca else factor
            becken_diff = prev["Wert"] - last["Wert"]
            hist_dosis = prev["IntervallDosis"] if prev["IntervallDosis"] > 0 else current_setup_dosis
            
            # Toleranz gegen Messfehler (0.1 dKH / 5 mg/l)
            toleranz = 0.1 if not is_ca else 5.0
            
            if abs(becken_diff) <= toleranz:
                v_real = hist_dosis / (vol / 100) / f_konz
            else:
                v_real = (becken_diff / tage) + (hist_dosis / (vol / 100) / f_konz)
            
            d_neu = round(v_real * (vol / 100) * f_konz, 1)
            delta = round(d_neu - current_setup_dosis, 1)
            up = round((target_val - last["Wert"]) * (vol / 100) * f_konz, 1) if target_val > last["Wert"] else 0.0
            return round(v_real, 3), d_neu, delta, up
    return None, None, None, None

# --- UI START ---
st.title("🌊 Zauberflos AquaCalc Cloud")
df_kh, df_ca = clean_dataframe(load_data("KH")), clean_dataframe(load_data("CA"))

res1, res2 = st.columns(2)
# KH-Bereich
v1, d1, delta1, up1 = calculate_aquarium_strict_vB(df_kh, s["KH_Dosis"], s["Volumen"], s["KH_Faktor"], 7.5, False)
if v1:
    res1.metric(f"Neue Dosis {s['KH_Brand']}", f"{d1} ml", f"{delta1} ml vs. bisher")
    if res1.button("✅ KH Dosis speichern"):
        df_kh.at[df_kh.index[-1], "IntervallDosis"] = d1
        conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=df_kh)
        st.rerun()
else: res1.write("Warte auf KH-Daten...")

# CA-Bereich
v2, d2, delta2, up2 = calculate_aquarium_strict_vB(df_ca, s["CA_Dosis"], s["Volumen"], s["CA_Faktor"], 420, True)
if v2:
    res2.metric(f"Neue Dosis {s['CA_Brand']}", f"{d2} ml", f"{delta2} ml vs. bisher")
    if res2.button("✅ CA Dosis speichern"):
        df_ca.at[df_ca.index[-1], "IntervallDosis"] = d2
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=df_ca)
        st.rerun()
else: res2.write("Warte auf CA-Daten...")

with st.expander("📊 Historie"):
    st.dataframe(df_kh)
    st.dataframe(df_ca)
