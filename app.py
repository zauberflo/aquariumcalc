import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

# --- LOGO LADEN ---
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/zauberflo/aquariumcalc/main/logo.png"
def get_logo():
    try:
        response = requests.get(GITHUB_LOGO_URL)
        return Image.open(BytesIO(response.content))
    except: return "🐠"

logo_img = get_logo()

# --- APP KONFIGURATION ---
st.set_page_config(page_title="AquaCalc Cloud 572", page_icon=logo_img, layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

def load_data(sheet_name):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0).dropna(how="all")
    except: return pd.DataFrame()

# --- SETUP DATEN LADEN & ROBUST ---
df_setup = load_data("Setup")
s = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0}
if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        if p in s:
            try: s[p] = float(row["Wert"])
            except: pass

# --- KORRIGIERTE BERECHNUNGS-LOGIK ---
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
            toleranz = 0.1 if not is_ca else 5.0
            
            # Kern-Logik: Keine Verfälschung durch manuelle Extra-Zugaben
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

# Sidebar bleibt erhalten
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s["Volumen"] = st.number_input("Beckenvolumen (Netto L)", value=s["Volumen"])
    s["KH_Dosis"] = st.number_input("Dosis KH", value=s["KH_Dosis"], format="%.1f")
    s["CA_Dosis"] = st.number_input("Dosis CA", value=s["CA_Dosis"], format="%.1f")
    # ... hier könntest du den Rest deines Sidebars einfügen ...

# Daten laden & reinigen
def clean_dataframe(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe", "IntervallDosis"])
    d = df.copy()
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["IntervallDosis"] = pd.to_numeric(d["IntervallDosis"], errors='coerce').fillna(0.0)
    return d

df_kh = clean_dataframe(load_data("KH"))
df_ca = clean_dataframe(load_data("CA"))

# Berechnung & Anzeige
res1, res2 = st.columns(2)
for res, df, d_set, brand, f, target, is_ca, name in [(res1, df_kh, s["KH_Dosis"], s["KH_Brand"], s["KH_Faktor"], 7.5, False, "KH"), (res2, df_ca, s["CA_Dosis"], s["CA_Brand"], s["CA_Faktor"], 420, True, "CA")]:
    v, d, delta, up = calculate_aquarium_strict_vB(df, d_set, s["Volumen"], f, target, is_ca)
    if v:
        res.metric(f"Neue Tagesdosis {brand}", f"{d} ml", f"{delta} ml")
        if res.button(f"✅ Dosis für {name} aktivieren"):
            df.at[df.index[-1], "IntervallDosis"] = d
            conn.update(spreadsheet=SHEET_URL, worksheet=name, data=df)
            st.rerun()
    else: res.write(f"Warte auf Messdaten für {name}...")
