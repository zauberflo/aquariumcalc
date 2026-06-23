import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

# --- CONFIG & LOGO ---
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/zauberflo/aquariumcalc/main/logo.png"
def get_logo():
    try: return Image.open(BytesIO(requests.get(GITHUB_LOGO_URL).content))
    except: return "🐠"

st.set_page_config(page_title="AquaCalc Cloud 572", page_icon=get_logo(), layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

# --- DATA LOADING & CLEANING ---
def load_data(sheet_name):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0).dropna(how="all")
    except: return pd.DataFrame()

df_setup = load_data("Setup")
setup_vals = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0, "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0}

if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        if p in setup_vals:
            val = str(row["Wert"])
            setup_vals[p] = float(val) if val.replace('.','',1).isdigit() else row["Wert"]

if "kh_dosis_live" not in st.session_state: st.session_state.kh_dosis_live = float(setup_vals["KH_Dosis"])
if "ca_dosis_live" not in st.session_state: st.session_state.ca_dosis_live = float(setup_vals["CA_Dosis"])

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=float(setup_vals["Volumen"]))
    s_brand_kh = st.text_input("Marke KH-Lösung", value=str(setup_vals["KH_Brand"]))
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=str(setup_vals["CA_Brand"]))
    
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    st.session_state.kh_dosis_live = st.number_input(f"Dosis {s_brand_kh}", value=st.session_state.kh_dosis_live, format="%.1f")
    st.session_state.ca_dosis_live = st.number_input(f"Dosis {s_brand_ca}", value=st.session_state.ca_dosis_live, format="%.1f")
    
    s_kh_f = st.number_input(f"ml {s_brand_kh} für +1° dKH / 100L", value=float(setup_vals["KH_Faktor"]))
    s_ca_f = st.number_input(f"ml {s_brand_ca} für +10mg Ca / 100L", value=float(setup_vals["CA_Faktor"]))
    target_kh = st.number_input("Wunsch-KH", value=7.5, step=0.1, format="%.1f")
    target_ca = st.number_input("Wunsch-Calcium", value=420, step=5)

    if st.button("💾 Setup manuell speichern"):
        df_new = pd.DataFrame({"Parameter": list(setup_vals.keys()), "Wert": [s_vol, s_brand_kh, s_brand_ca, st.session_state.kh_dosis_live, st.session_state.ca_dosis_live, s_kh_f, s_ca_f, setup_vals["KH_Verbrauch"], setup_vals["CA_Verbrauch"]]})
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=df_new)
        st.cache_data.clear()
        st.success("Setup gespeichert!")
        st.rerun()

def clean_df(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    d["Datum"] = d["Datum"].astype(str).replace("nan", str(datetime.now().date()))
    return d[["Datum", "Wert", "Zugabe"]].reset_index(drop=True)

df_kh = clean_df(load_data("KH"))
df_ca = clean_df(load_data("CA"))

st.title("🌊 Zauberflos AquaCalc Cloud")
c_in1, c_in2 = st.columns(2)
today_str = str(datetime.now().date())

# --- DYNAMISCHE SEKTIONEN FÜR KH & CA ---
cfg = {
    "KH": {"df": df_kh, "brand": s_brand_kh, "live_d": st.session_state.kh_dosis_live, "factor": s_kh_f, "target": target_kh, "is_ca": False, "col": c_in1, "unit": "dKH", "step": 1.0, "val_default": 7.5},
    "CA": {"df": df_ca, "brand": s_brand_ca, "live_d": st.session_state.ca_dosis_live, "factor": s_ca_f, "target": target_ca, "is_ca": True, "col": c_in2, "unit": "mg/l", "step": 5.0, "val_default": 420}
}

def calc_strict(df, active_dosis, vol, factor, target_val, is_ca):
    m = df.dropna(subset=["Wert"]).copy()
    if len(m) < 2: return None
    m["Datum"] = pd.to_datetime(m["Datum"])
    m = m.sort_values("Datum")
    last, prev = m.iloc[-1], m.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    if tage <= 0: return None
    
    f = factor / 10 if is_ca else factor
    diff_tag = (prev["Wert"] - last["Wert"]) / tage
    d_wirk_tag = active_dosis / (vol / 100) / f
    sub_df = df[(df["Datum"] >= str(prev["Datum"].date())) & (df["Datum"] < str(last["Datum"].date()))]
    z_wirk_tag = (sub_df["Zugabe"].sum() / (vol / 100) / f) / tage
    
    v_real = round(diff_tag + d_wirk_tag + z_wirk_tag, 3)
    d_neu = round(v_real * (vol / 100) * f, 1)
    return v_real, d_neu, round(d_neu - active_dosis, 1), round((target_val - last["Wert"]) * (vol / 100) * f, 1)

for key, c in cfg.items():
    with c["col"]:
        st.subheader(f"🧪 {c['brand']} Messung")
        only_ex = st.checkbox("Nur Extra-Zugabe buchen", key=f"only_{key}")
        val_in = st.number_input(f"Messwert ({c['unit']})", value=float(c['val_default']), disabled=only_ex, key=f"v_{key}")
        ext_in = st.number_input("Extra-Zugabe JETZT (ml)", value=0.0, step=c["step"], key=f"e_{key}")
        
        if st.button("💾 Speichern", key=f"save_{key}"):
            new_row = {"Datum": today_str, "Wert": None if only_ex else float(val_in), "Zugabe": float(ext_in)}
            updated_df = pd.concat([c["df"], pd.DataFrame([new_row])], ignore_index=True)
            conn.update(spreadsheet=SHEET_URL, worksheet=key, data=updated_df)
            st.cache_data.clear()
            st.rerun()

st.divider()
st.header("⏱️ Aktuelle Entwicklung")
res1, res2 = st.columns(2)
res_cols = {"KH": res1, "CA": res2}

for key, c in cfg.items():
    r_col = res_cols[key]
    res = calc_strict(c["df"], c["live_d"], s_vol, c["factor"], c["target"], c["is_ca"])
    if res:
        v_real, d_neu, delta, einmalig = res
        if abs(delta) <= 0.1:
            r_col.success(f"🎉 **{key}-Dosis optimal!** Aktuell: **{c['live_d']} ml**. Verbrauch: {v_real} {c['unit']}/Tag")
        else:
            r_col.metric(f"Empfehlung {c['brand']}", f"{d_neu} ml", f"{delta} ml vs. bisher")
            r_col.write(f"📉 Realer Verbrauch: **{v_real} {c['unit']}/Tag**")
            if r_col.button(f"✅ Übernehmen ({key})", key=f
