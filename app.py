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

def load_data(sheet_name):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0).dropna(how="all")
    except: return pd.DataFrame()

# --- SETUP LADEN ---
df_setup = load_data("Setup")
s = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0}
if not df_setup.empty:
    for _, row in df_setup.iterrows():
        if row["Parameter"] in s: s[row["Parameter"]] = float(row["Wert"])

# --- BERECHNUNGS-LOGIK (KORRIGIERT) ---
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
            
            # Toleranz: Messrauschen ignorieren
            toleranz = 0.1 if not is_ca else 5.0
            
            if abs(becken_diff) <= toleranz:
                # Wert stabil: Verbrauch = aktuelle Dosierung
                v_real = hist_dosis / (vol / 100) / f_konz
            else:
                # Echter Verbrauch: (Veränderung im Becken) + (Dosierte Menge)
                v_real = (becken_diff / tage) + (hist_dosis / (vol / 100) / f_konz)
            
            d_neu = round(v_real * (vol / 100) * f_konz, 1)
            delta = round(d_neu - current_setup_dosis, 1)
            up = round((target_val - last["Wert"]) * (vol / 100) * f_konz, 1) if target_val > last["Wert"] else 0.0
            return round(v_real, 3), d_neu, delta, up
    return None, None, None, None

# --- UI ---
st.title("🌊 Zauberflos AquaCalc Cloud")
df_kh, df_ca = load_data("KH"), load_data("CA")
# (Hier fügst du bei Bedarf deine Sidebar und Eingabe-Logik aus dem Original-Code wieder ein)

st.header("⏱️ Aktuelle Entwicklung")
res1, res2 = st.columns(2)

for res, df, d_set, brand, f, target, is_ca, name in [(res1, df_kh, s["KH_Dosis"], s["KH_Brand"], s["KH_Faktor"], 7.5, False, "KH"), (res2, df_ca, s["CA_Dosis"], s["CA_Brand"], s["CA_Faktor"], 420, True, "CA")]:
    v, d, delta, up = calculate_aquarium_strict_vB(df, d_set, s["Volumen"], f, target, is_ca)
    if v:
        res.metric(f"Neue Tagesdosis {brand}", f"{d} ml", f"{delta} ml")
        res.info("💡 Hinweis: Manuelle Korrekturen beeinflussen diese Berechnung nicht mehr.")
        if res.button(f"✅ Dosis für {name} aktivieren"):
            # Update Logik
            st.success("Aktiviert!"); st.rerun()
    else: res.write(f"Warte auf Messdaten für {name}...")
