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
    except:
        return "🐠"

logo_img = get_logo()

# --- APP KONFIGURATION ---
st.set_page_config(page_title="AquaCalc Cloud 572", page_icon=logo_img, layout="wide")

# --- VERBINDUNG ZU GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

def load_data(sheet_name):
    try:
        # ttl=0 stellt sicher, dass wir immer frische Daten laden
        data = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)
        return data.dropna(how="all")
    except:
        return pd.DataFrame()

# --- SETUP DATEN LADEN ---
df_setup = load_data("Setup")

# Standardwerte (Fallbacks)
setup_values = {
    "Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca",
    "KH_Dosis": 0.0, "CA_Dosis": 0.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0,
    "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0
}

# Werte aus Tabelle in unser Dictionary übertragen
if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        if p in setup_values:
            setup_values[p] = row["Wert"]

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Setup")
    s_vol = st.number_input("Volumen (L)", value=float(setup_values["Volumen"]))
    s_kh_b = st.text_input("Marke KH", value=str(setup_values["KH_Brand"]))
    s_ca_b = st.text_input("Marke Ca", value=str(setup_values["CA_Brand"]))
    
    st.divider()
    st.subheader("Aktuelle Dosierung (ml)")
    s_kh_d = st.number_input(f"{s_kh_b} ml/Tag", value=float(setup_values["KH_Dosis"]))
    s_ca_d = st.number_input(f"{s_ca_b} ml/Tag", value=float(setup_values["CA_Dosis"]))
    
    st.divider()
    s_kh_f = st.number_input("KH Faktor", value=float(setup_values["KH_Faktor"]))
    s_ca_f = st.number_input("Ca Faktor", value=float(setup_values["CA_Faktor"]))

    if st.button("💾 Alle Einstellungen speichern"):
        new_setup = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
            "Wert": [s_vol, s_kh_b, s_ca_b, s_kh_d, s_ca_d, s_kh_f, s_ca_f, setup_values["KH_Verbrauch"], setup_values["CA_Verbrauch"]]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup)
        st.cache_data.clear()
        st.success("Setup gespeichert!")
        st.rerun()

# --- DATEN LADEN ---
df_kh = load_data("KH")
df_ca = load_data("CA")

st.title("🌊 AquaCalc Cloud")

# --- MESSWERTE EINGEBEN ---
c_in1, c_in2 = st.columns(2)
with c_in1:
    st.subheader(f"🧪 {s_kh_b}")
    kh_val = st.number_input("KH Messwert", format="%.2f", key="kin")
    if st.button("Speichern KH"):
        new_kh = pd.concat([df_kh, pd.DataFrame([{"Datum": str(datetime.now().date()), "Wert": kh_val}])], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=new_kh)
        st.cache_data.clear()
        st.rerun()

with c_in2:
    st.subheader(f"🧪 {s_ca_b}")
    ca_val = st.number_input("Ca Messwert", step=1, key="cin")
    if st.button("Speichern Ca"):
        new_ca = pd.concat([df_ca, pd.DataFrame([{"Datum": str(datetime.now().date()), "Wert": ca_val}])], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=new_ca)
        st.cache_data.clear()
        st.rerun()

# --- BERECHNUNG ---
st.divider()
res1, res2 = st.columns(2)

def calculate(df, current_dosis, vol, factor, is_ca=False):
    if df is not None and len(df) >= 2:
        d = df.copy()
        d["Datum"] = pd.to_datetime(d["Datum"])
        d["Wert"] = pd.to_numeric(d["Wert"])
        d = d.sort_values("Datum")
        last, prev = d.iloc[-1], d.iloc[-2]
        tage = (last["Datum"] - prev["Datum"]).days
        if tage > 0:
            abfall = (prev["Wert"] - last["Wert"]) / tage
            f = factor / 10 if is_ca else factor
            v_real = round(abfall + (current_dosis / (vol/100) / f), 3)
            d_neu = round(v_real * (vol/100) * f, 1)
            return v_real, d_neu
    return None, None

# KH Ergebnis
v_kh, d_kh = calculate(df_kh, s_kh_d, s_vol, s_kh_f)
if v_kh is not None:
    res1.metric("Empfehlung KH", f"{d_kh} ml", f"{round(d_kh - s_kh_d, 1)} ml")
    res1.write(f"Realer Verbrauch: **{v_kh} dKH/Tag**")
    if res1.button("✅ KH Dosis & Verbrauch übernehmen"):
        setup_values["KH_Dosis"], setup_values["KH_Verbrauch"] = d_kh, v_kh
        new_s = pd.DataFrame({"Parameter": list(setup_values.keys()), "Wert": list(setup_values.values())})
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_s)
        st.cache_data.clear()
        st.rerun()
else:
    res1.info(f"Letzter KH Verbrauch: {setup_values['KH_Verbrauch']}")

# Ca Ergebnis
v_ca, d_ca = calculate(df_ca, s_ca_d, s_vol, s_ca_f, is_ca=True)
if v_ca is not None:
    res2.metric("Empfehlung Ca", f"{d_ca} ml", f"{round(d_ca - s_ca_d, 1)} ml")
    res2.write(f"Realer Verbrauch: **{v_ca} mg/l/Tag**")
    if res2.button("✅ Ca Dosis & Verbrauch übernehmen"):
        setup_values["CA_Dosis"], setup_values["CA_Verbrauch"] = d_ca, v_ca
        new_s = pd.DataFrame({"Parameter": list(setup_values.keys()), "Wert": list(setup_values.values())})
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_s)
        st.cache_data.clear()
        st.rerun()
else:
    res2.info(f"Letzter Ca Verbrauch: {setup_values['CA_Verbrauch']}")

# --- HISTORIE ---
st.divider()
with st.expander("📊 Verlauf"):
    if not df_kh.empty: st.line_chart(df_kh.set_index("Datum")["Wert"])
    if not df_ca.empty: st.line_chart(df_ca.set_index("Datum")["Wert"])
