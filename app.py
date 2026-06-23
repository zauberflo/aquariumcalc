import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- SETUP ---
st.set_page_config(page_title="AquaCalc Cloud 572", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

def load_data(sheet):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=sheet, ttl=0).dropna(how="all")
    except: return pd.DataFrame()

# Lade Daten
df_setup = load_data("Setup")
# (Hier käme deine Setup-Logik zur Extraktion der Werte aus df_setup hin)
s_vol, s_kh_f, s_ca_f = 572.0, 10.0, 14.0 # Beispielwerte
if "kh_dosis_live" not in st.session_state: st.session_state.kh_dosis_live = 12.0
if "ca_dosis_live" not in st.session_state: st.session_state.ca_dosis_live = 15.0

# --- UI: EINGABE ---
st.title("🌊 Zauberflos AquaCalc Cloud")
c1, c2 = st.columns(2)
cfg = {"KH": {"col": c1, "brand": "Oceamo Duo KH", "dosis": "kh_dosis_live"}, 
       "CA": {"col": c2, "brand": "Oceamo Duo CA", "dosis": "ca_dosis_live"}}

for key, c in cfg.items():
    with c["col"]:
        st.subheader(f"🧪 {c['brand']} Messung")
        val = st.number_input(f"Messwert {key}", key=f"val_{key}")
        if st.button(f"💾 Speichern {key}", key=f"btn_{key}"):
            new_row = {"Datum": str(datetime.now().date()), "Wert": val, "IntervallDosis": st.session_state[c['dosis']]}
            conn.update(spreadsheet=SHEET_URL, worksheet=key, data=pd.concat([load_data(key), pd.DataFrame([new_row])]))
            st.rerun()

# --- UI: AUSWERTUNG ---
st.divider()
st.header("⏱️ Aktuelle Entwicklung")
for key, c in cfg.items():
    df = load_data(key)
    if len(df) >= 2:
        last, prev = df.iloc[-1], df.iloc[-2]
        verbrauch = (float(prev["Wert"]) - float(last["Wert"])) / (pd.to_datetime(last["Datum"]) - pd.to_datetime(prev["Datum"])).days
        empfehlung = round(verbrauch * (s_vol / 100) * (s_kh_f if key=="KH" else s_ca_f), 1)
        
        col_res = st.columns(2)[0 if key=="KH" else 1]
        col_res.write(f"**{key} Verbrauch:** {round(verbrauch, 2)} pro Tag")
        if col_res.button(f"✅ Übernehmen: {empfehlung} ml", key=f"act_{key}"):
            st.session_state[c['dosis']] = empfehlung
            # Update Sheet-Historie
            df.at[df.index[-1], "IntervallDosis"] = empfehlung
            conn.update(spreadsheet=SHEET_URL, worksheet=key, data=df)
            st.rerun()
    else:
        st.write(f"Nicht genug Daten für {key}")

# --- UI: HISTORIE ---
with st.expander("📊 Historie anzeigen"):
    for key in ["KH", "CA"]:
        st.subheader(f"{key} Verlauf")
        st.dataframe(load_data(key))
