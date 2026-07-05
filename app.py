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
        data = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)
        return data.dropna(how="all")
    except:
        return pd.DataFrame()

# --- SETUP DATEN LADEN ---
df_setup = load_data("Setup")
setup_values = {
    "Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca",
    "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0,
    "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0
}

if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        if p in setup_values:
            try:
                setup_values[p] = float(row["Wert"]) if str(row["Wert"]).replace('.','',1).isdigit() else row["Wert"]
            except:
                setup_values[p] = row["Wert"]

s_vol = float(setup_values["Volumen"])
s_brand_kh = str(setup_values["KH_Brand"])
s_brand_ca = str(setup_values["CA_Brand"])
s_kh_d = float(setup_values["KH_Dosis"])
s_ca_d = float(setup_values["CA_Dosis"])
s_kh_f = float(setup_values["KH_Faktor"])
s_ca_f = float(setup_values["CA_Faktor"])

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=s_vol)
    st.divider()
    s_brand_kh = st.text_input("Marke KH-Lösung", value=s_brand_kh)
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=s_brand_ca)
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    s_kh_d = st.number_input(f"Dosis {s_brand_kh}", value=s_kh_d, format="%.1f")
    s_ca_d = st.number_input(f"Dosis {s_brand_ca}", value=s_ca_d, format="%.1f")
    st.divider()
    st.subheader("Produkt-Parameter")
    s_kh_f = st.number_input(f"ml {s_brand_kh} für +1° dKH / 100L", value=s_kh_f)
    s_ca_f = st.number_input(f"ml {s_brand_ca} für +10mg Ca / 100L", value=s_ca_f)
    st.divider()
    st.subheader("🎯 Wunschwerte")
    target_kh = st.number_input("Wunsch-KH", value=7.5, step=0.1, format="%.1f")
    target_ca = st.number_input("Wunsch-Calcium", value=420, step=5)

    if st.button("💾 Setup manuell speichern"):
        new_setup = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
            "Wert": [s_vol, s_brand_kh, s_brand_ca, s_kh_d, s_ca_d, s_kh_f, s_ca_f, setup_values["KH_Verbrauch"], setup_values["CA_Verbrauch"]]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup)
        st.cache_data.clear()
        st.success("Setup gespeichert!")
        st.rerun()

# --- DATEN LADEN & BEREINIGUNG ---
def clean_dataframe(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe", "IntervallDosis"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    if "IntervallDosis" not in d.columns: d["IntervallDosis"] = 0.0
    d["IntervallDosis"] = pd.to_numeric(d["IntervallDosis"], errors='coerce').fillna(0.0)
    d["Datum"] = d["Datum"].astype(str)
    return d.reset_index(drop=True)

df_kh = clean_dataframe(load_data("KH"))
df_ca = clean_dataframe(load_data("CA"))

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- MESSWERTE EINGEBEN ---
c_in1, c_in2 = st.columns(2)
today_str = str(datetime.now().date())

def handle_save(name, df, val, extra, current_dosis, is_extra_only, is_ca):
    if is_extra_only:
        mask = df["Datum"] == today_str
        if mask.any(): df.loc[mask, "Zugabe"] += float(extra)
        else: df = pd.concat([df, pd.DataFrame([{"Datum": today_str, "Wert": None, "Zugabe": float(extra), "IntervallDosis": float(current_dosis)}])], ignore_index=True)
    else:
        df = pd.concat([df, pd.DataFrame([{"Datum": today_str, "Wert": float(val), "Zugabe": float(extra), "IntervallDosis": float(current_dosis)}])], ignore_index=True)
    conn.update(spreadsheet=SHEET_URL, worksheet=name, data=df)
    st.cache_data.clear(); st.rerun()

with c_in1:
    st.subheader(f"🧪 {s_brand_kh} Messung")
    only_k = st.checkbox("Nur Extra-Zugabe", key="only_k")
    k_v = st.number_input("dKH", disabled=only_k, value=7.5)
    k_e = st.number_input("Extra ml", value=0.0, key="ke")
    if st.button("💾 KH Speichern"): handle_save("KH", df_kh, k_v, k_e, s_kh_d, only_k, False)

with c_in2:
    st.subheader(f"🧪 {s_brand_ca} Messung")
    only_c = st.checkbox("Nur Extra-Zugabe", key="only_c")
    c_v = st.number_input("Ca mg/l", disabled=only_c, value=420)
    c_e = st.number_input("Extra ml", value=0.0, key="ce")
    if st.button("💾 Ca Speichern"): handle_save("CA", df_ca, c_v, c_e, s_ca_d, only_c, True)

# --- BERECHNUNGSLOGIK (ROBUST) ---
def calculate_aquarium_strict_vB(df, current_setup_dosis, vol, factor, target_val, is_ca=False):
    df["Datum"] = pd.to_datetime(df["Datum"], errors='coerce')
    df_m = df.dropna(subset=["Wert"]).sort_values("Datum")
    if len(df_m) >= 2:
        last, prev = df_
