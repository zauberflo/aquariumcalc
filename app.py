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
            # Ohne Toleranz-Filter
            v_real = (becken_diff / tage) + (hist_dosis / (vol / 100) / f_konz)
            d_neu = round(v_real * (vol / 100) * f_konz, 1)
            return round(v_real, 3), d_neu, round(d_neu - current_setup_dosis, 1), round((target_val - last["Wert"]) * (vol / 100) * f_konz, 1)
    return None, None, None, None

# --- UI START ---
st.title("🌊 Zauberflos AquaCalc Cloud")
today_str = str(datetime.now().date())

# Sidebar
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s["Volumen"] = st.number_input("Beckenvolumen", value=s["Volumen"])
    s["KH_Dosis"] = st.number_input("KH Dosis", value=s["KH_Dosis"])
    s["CA_Dosis"] = st.number_input("CA Dosis", value=s["CA_Dosis"])
    if st.button("💾 Setup speichern"): st.success("Gespeichert!")

# Datenreinigung
def clean_df(df):
    d = df.copy()
    if "Zugabe" not in d.columns: d["Zugabe"] = 0.0
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    d["IntervallDosis"] = pd.to_numeric(d["IntervallDosis"], errors='coerce').fillna(0.0)
    return d.reset_index(drop=True)

df_kh, df_ca = clean_df(load_data("KH")), clean_df(load_data("CA"))

# Eingabe-Bereich für Messungen & Extra-Zugaben
c_in1, c_in2 = st.columns(2)
for c, df, brand, d_set, key, worksheet in [(c_in1, df_kh, "KH", s["KH_Dosis"], "k", "KH"), (c_in2, df_ca, "CA", s["CA_Dosis"], "c", "CA")]:
    with c:
        st.subheader(f"🧪 {brand} buchen")
        only_extra = st.checkbox(f"Nur manuelle Extra-Zugabe (keine Messung)", key=f"only_{key}")
        val = st.number_input(f"Messwert", key=f"val_{key}", disabled=only_extra)
        extra = st.number_input(f"Extra Zugabe (ml)", key=f"ex_{key}")
        if st.button(f"💾 Speichern {brand}"):
            new_row = {"Datum": today_str, "Wert": None if only_extra else val, "Zugabe": extra, "IntervallDosis": d_set}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            conn.update(spreadsheet=SHEET_URL, worksheet=worksheet, data=df); st.rerun()

# Berechnung & Anzeige
res1, res2 = st.columns(2)
for res, df, d_set, brand, f, target, name in [(res1, df_kh, s["KH_Dosis"], s["KH_Brand"], s["KH_Faktor"], 7.5, "KH"), (res2, df_ca, s["CA_Dosis"], s["CA_Brand"], s["CA_Faktor"], 420, "CA")]:
    v, d, delta, up = calculate_aquarium_strict_vB(df, d_set, s["Volumen"], f, target, name == "CA")
    if v:
        res.metric(f"Neue Dosis {brand}", f"{d} ml", f"{delta} ml")
        if res.button(f"✅ Aktivieren {name}"):
            df.at[df.index[-1], "IntervallDosis"] = d
            conn.update(spreadsheet=SHEET_URL, worksheet=name, data=df); st.rerun()

# Archiv
st.divider()
with st.expander("📊 Historie & Verlauf", expanded=True):
    h1, h2 = st.columns(2)
    for h, df, name, ws, key in [(h1, df_kh, "KH", "KH", "del_kh"), (h2, df_ca, "CA", "CA", "del_ca")]:
        with h:
            st.subheader(name)
            st.dataframe(df, use_container_width=True)
            d_del = st.selectbox(f"Datum löschen:", df["Datum"].unique(), key=key)
            if st.button(f"❌ {name} löschen"):
                conn.update(spreadsheet=SHEET_URL, worksheet=ws, data=df[df["Datum"] != d_del])
                st.rerun()
