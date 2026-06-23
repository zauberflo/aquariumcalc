import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="AquaCalc Cloud 572", page_icon="🐠", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

# --- DATA CLEANING (BOMBENSICHER) ---
def clean_df(df):
    if df is None or df.empty: 
        return pd.DataFrame(columns=["Datum", "Wert", "Zugabe", "IntervallDosis"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    
    # Fehlende Spalten dynamisch ergänzen, damit Pandas nicht abstürzt
    for col in ["Wert", "Zugabe", "IntervallDosis"]:
        if col not in d.columns: d[col] = 0.0
        
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    d["IntervallDosis"] = pd.to_numeric(d["IntervallDosis"], errors='coerce').fillna(0.0)
    d["Datum"] = d["Datum"].astype(str).replace("nan", str(datetime.now().date()))
    return d[["Datum", "Wert", "Zugabe", "IntervallDosis"]].reset_index(drop=True)

# --- SETUP LADEN ---
try:
    df_s = conn.read(spreadsheet=SHEET_URL, worksheet="Setup", ttl=0).dropna(how="all")
except:
    df_s = pd.DataFrame()

sv = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0, "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0}

if not df_s.empty and "Parameter" in df_s.columns:
    for _, r in df_s.iterrows():
        p = str(r["Parameter"]).strip()
        if p in sv:
            val = str(r["Wert"])
            sv[p] = float(val) if val.replace('.','',1).isdigit() else r["Wert"]

# Session State für die Widgets initialisieren
if "kh_dosis_live" not in st.session_state: st.session_state.kh_dosis_live = float(sv["KH_Dosis"])
if "ca_dosis_live" not in st.session_state: st.session_state.ca_dosis_live = float(sv["CA_Dosis"])

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=float(sv["Volumen"]))
    s_b_kh = st.text_input("Marke KH-Lösung", value=str(sv["KH_Brand"]))
    s_b_ca = st.text_input("Marke Ca-Lösung", value=str(sv["CA_Brand"]))
    
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    st.number_input(f"Dosis {s_b_kh}", format="%.1f", key="kh_dosis_live")
    st.number_input(f"Dosis {s_b_ca}", format="%.1f", key="ca_dosis_live")
    
    s_k_f = st.number_input(f"ml {s_b_kh} für +1° dKH / 100L", value=float(sv["KH_Faktor"]))
    s_c_f = st.number_input(f"ml {s_b_ca} für +10mg Ca / 100L", value=float(sv["CA_Faktor"]))
    t_kh = st.number_input("Wunsch-KH", value=7.5, step=0.1, format="%.1f")
    t_ca = st.number_input("Wunsch-Calcium", value=420, step=5)

    if st.button("💾 Setup manuell speichern"):
        df_new = pd.DataFrame({
            "Parameter": list(sv.keys()), 
            "Wert": [s_vol, s_b_kh, s_b_ca, st.session_state.kh_dosis_live, st.session_state.ca_dosis_live, s_k_f, s_c_f, sv["KH_Verbrauch"], sv["CA_Verbrauch"]]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=df_new)
        st.cache_data.clear()
        st.success("Setup gespeichert!")
        st.rerun()

# Daten mit Failback laden
df_kh = clean_df(conn.read(spreadsheet=SHEET_URL, worksheet="KH", ttl=0)) if conn else clean_df(None)
df_ca = clean_df(conn.read(spreadsheet=SHEET_URL, worksheet="CA", ttl=0)) if conn else clean_df(None)

st.title("🌊 Zauberflos AquaCalc Cloud")
c1, c2 = st.columns(2)
today = str(datetime.now().date())

cfg = {
    "KH": {"df": df_kh, "brand": s_b_kh, "current_d": st.session_state.kh_dosis_live, "factor": s_k_f, "target": t_kh, "is_ca": False, "col": c1, "unit": "dKH", "step": 1.0, "def": 7.5},
    "CA": {"df": df_ca, "brand": s_b_ca, "current_d": st.session_state.ca_dosis_live, "factor": s_c_f, "target": t_ca, "is_ca": True, "col": c2, "unit": "mg/l", "step": 5.0, "def": 420}
}

# --- KORREKTE VERBRAUCHSBERECHNUNG ---
def calc_consumption(df, curr_dosis, vol, factor, target, is_ca=False):
    try:
        df_m = df.dropna(subset=["Wert"]).copy()
        if df_m.empty or len(df_m) < 2: return None, None, None, None
        
        df_m["Datum_dt"] = pd.to_datetime(df_m["Datum"], errors='coerce')
        df_m = df_m.dropna(subset=["Datum_dt"]).sort_values("Datum_dt")
        if len(df_m) < 2: return None, None, None, None
        
        last = df_m.iloc[-1]
        prev = df_m.iloc[-2]
        
        days = (last["Datum_dt"] - prev["Datum_dt"]).days
        if days <= 0: return None, None, None, None
        
        f_konz = factor / 10 if is_ca else factor
        
        # 1. Verbrauch durch Abfall des Beckenwerts
        diff_p_d = (prev["Wert"] - last["Wert"]) / days
        
        # 2. Verbrauch abgedeckt durch die reguläre Dosierung im Intervall
        hist_dosis = curr_dosis
        if "IntervallDosis" in prev and float(prev["IntervallDosis"]) > 0:
            hist_dosis = float(prev["IntervallDosis"])
        wirk_p_d = hist_dosis / (vol / 100) / f_konz
        
        # 3. Verbrauch abgedeckt durch Extra-Zugaben im Intervall
        df_temp = df.copy()
        df_temp["Datum_dt"] = pd.to_datetime(df_temp["Datum"], errors='coerce')
        sub_df = df_temp[(df_temp["Datum_dt"] >= prev["Datum_dt"]) & (df_temp["Datum_dt"] < last["Datum_dt"])]
        ext_wirk = (sub_df["Zugabe"].sum() / (vol / 100) / f_konz) / days if not sub_df.empty else 0.0
        
        # Gesamter realer Verbrauch pro Tag
        v_real = round(diff_p_d + wirk_p_d + ext_wirk, 3)
        
        # Neue empfohlene Dosierung, um exakt diesen Verbrauch zu halten
        d_neu = round(v_real * (
