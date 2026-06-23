import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="AquaCalc Cloud 572", page_icon="🐠", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

def clean_df(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    d["Datum"] = d["Datum"].astype(str).replace("nan", str(datetime.now().date()))
    return d[["Datum", "Wert", "Zugabe"]].reset_index(drop=True)

# --- SETUP LADEN ---
df_s = conn.read(spreadsheet=SHEET_URL, worksheet="Setup", ttl=0).dropna(how="all")
sv = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0, "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0}

if not df_s.empty and "Parameter" in df_s.columns:
    for _, r in df_s.iterrows():
        p = str(r["Parameter"]).strip()
        if p in sv:
            val = str(r["Wert"])
            sv[p] = float(val) if val.replace('.','',1).isdigit() else r["Wert"]

if "kh_dosis_live" not in st.session_state: st.session_state.kh_dosis_live = float(sv["KH_Dosis"])
if "ca_dosis_live" not in st.session_state: st.session_state.ca_dosis_live = float(sv["CA_Dosis"])

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Setup")
    s_vol = st.number_input("Volumen (L)", value=float(sv["Volumen"]))
    s_b_kh = st.text_input("Marke KH", value=str(sv["KH_Brand"]))
    s_b_ca = st.text_input("Marke Ca", value=str(sv["CA_Brand"]))
    
    st.subheader("Dosierung (ml/Tag)")
    st.number_input(f"Dosis {s_b_kh}", format="%.1f", key="kh_dosis_live")
    st.number_input(f"Dosis {s_b_ca}", format="%.1f", key="ca_dosis_live")
    
    s_k_f = st.number_input("ml KH für +1° dKH / 100L", value=float(sv["KH_Faktor"]))
    s_c_f = st.number_input("ml Ca für +10mg Ca / 100L", value=float(sv["CA_Faktor"]))
    t_kh = st.number_input("Wunsch-KH", value=7.5, step=0.1)
    t_ca = st.number_input("Wunsch-Ca", value=420, step=5)

    if st.button("💾 Setup speichern"):
        df_new = pd.DataFrame({"Parameter": list(sv.keys()), "Wert": [s_vol, s_b_kh, s_b_ca, st.session_state.kh_dosis_live, st.session_state.ca_dosis_live, s_k_f, s_c_f, sv["KH_Verbrauch"], sv["CA_Verbrauch"]]})
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=df_new)
        st.cache_data.clear()
        st.success("Setup gespeichert!")
        st.rerun()

df_kh = clean_df(conn.read(spreadsheet=SHEET_URL, worksheet="KH", ttl=0))
df_ca = clean_df(conn.read(spreadsheet=SHEET_URL, worksheet="CA", ttl=0))

st.title("🌊 Zauberflos AquaCalc Cloud")
c1, c2 = st.columns(2)
today = str(datetime.now().date())

cfg = {
    "KH": {"df": df_kh, "brand": s_b_kh, "current_d": st.session_state.kh_dosis_live, "factor": s_k_f, "target": t_kh, "is_ca": False, "col": c1, "unit": "dKH", "step": 1.0, "def": 7.5},
    "CA": {"df": df_ca, "brand": s_b_ca, "current_d": st.session_state.ca_dosis_live, "factor": s_c_f, "target": t_ca, "is_ca": True, "col": c2, "unit": "mg/l", "step": 5.0, "def": 420}
}

# --- RECHEN-LOGIK ---
def calc_consumption(df, curr_dosis, vol, factor, target, is_ca=False):
    df_m = df.dropna(subset=["Wert"]).copy()
    if df_m is None or len(df_m) < 2: return None, None, None, None
    
    df_m["Datum"] = pd.to_datetime(df_m["Datum"])
    df_m = df_m.sort_values("Datum")
    last, prev = df_m.iloc
