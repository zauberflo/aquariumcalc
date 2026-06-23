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

def clean_df(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    d["Datum"] = d["Datum"].astype(str).replace("nan", str(datetime.now().date()))
    return d[["Datum", "Wert", "Zugabe"]].reset_index(drop=True)

# 1. SETUP-DATEN LADEN
df_setup = load_data("Setup")
setup_vals = {"Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca", "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0, "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0}

if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        if p in setup_vals:
            val = str(row["Wert"])
            setup_vals[p] = float(val) if val.replace('.','',1).isdigit() else row["Wert"]

# 2. SESSION STATE INITIALISIEREN
if "kh_dosis_live" not in st.session_state: st.session_state.kh_dosis_live = float(setup_vals["KH_Dosis"])
if "ca_dosis_live" not in st.session_state: st.session_state.ca_dosis_live = float(setup_vals["CA_Dosis"])

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=float(setup_vals["Volumen"]))
    s_brand_kh = st.text_input("Marke KH-Lösung", value=str(setup_vals["KH_Brand"]))
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=str(setup_vals["CA_Brand"]))
    
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    st.number_input(f"Dosis {s_brand_kh}", format="%.1f", key="kh_dosis_live")
    st.number_input(f"Dosis {s_brand_ca}", format="%.1f", key="ca_dosis_live")
    
    s_kh_f = st.number_input(f"ml {s_brand_kh} für +1° dKH / 100L", value=float(setup_vals["KH_Faktor"]))
    s_ca_f = st.number_input(f"ml {s_brand_ca} für +10mg Ca / 100L", value=float(setup_vals["CA_Faktor"]))
    target_kh = st.number_input("Wunsch-KH", value=7.5, step=0.1, format="%.1f")
    target_ca = st.number_input("Wunsch-Calcium", value=420, step=5)

    if st.button("💾 Setup manuell保存 speichern"):
        df_new = pd.DataFrame({
            "Parameter": list(setup_vals.keys()), 
            "Wert": [s_vol, s_brand_kh, s_brand_ca, st.session_state.kh_dosis_live, st.session_state.ca_dosis_live, s_kh_f, s_ca_f, setup_vals["KH_Verbrauch"], setup_vals["CA_Verbrauch"]]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=df_new)
        st.cache_data.clear()
        st.success("Setup gespeichert!")
        st.rerun()

df_kh = clean_df(load_data("KH"))
df_ca = clean_df(load_data("CA"))

st.title("🌊 Zauberflos AquaCalc Cloud")
c_in1, c_in2 = st.columns(2)
today_str = str(datetime.now().date())

# --- DYNAMISCHE SEKTIONEN FÜR KH & CA ---
cfg = {
    "KH": {"df": df_kh, "brand": s_brand_kh, "current_d": st.session_state.kh_dosis_live, "factor": s_kh_f, "target": target_kh, "is_ca": False, "col": c_in1, "unit": "dKH", "step": 1.0, "val_default": 7.5},
    "CA": {"df": df_ca, "brand": s_brand_ca, "current_d": st.session_state.ca_dosis_live, "factor": s_ca_f, "target": target_ca, "is_ca": True, "col": c_in2, "unit": "mg/l", "step": 5.0, "val_default": 420}
}

def calculate_aquarium_strict_vC(df, current_setup_dosis, vol, factor, target_val, is_ca=False):
    df_measured = df.dropna(subset=["Wert"]).copy()
    if df_measured is not None and len(df_measured) >= 2:
        df_measured["Datum"] = pd.to_datetime(df_measured["Datum"], errors='coerce')
        df_measured = df_measured.dropna(subset=["Datum"]).sort_values("Datum")
        if len(df_measured) >= 2:
            last = df_measured.iloc[-1]   
            prev = df_measured.iloc[-2]   
            tage = (last["Datum"] - prev["Datum"]).days
            if tage > 0:
                f_konzentration = factor / 10 if is_ca else factor
                becken_diff_pro_tag = (prev["Wert"] - last["Wert"]) / tage
                if "IntervallDosis" in prev and prev["IntervallDosis"] > 0:
                    historische_dosis = prev["IntervallDosis"]
                else:
                    historische_dosis = current_setup_dosis
                
                dosis_wirkung_pro_tag = historische_dosis / (vol / 100) / f_konzentration
                sub_df = df[(df["Datum"] >= str(prev["Datum"].date())) & (df["Datum"] < str(last["Datum"].date()))]
                total_extra_zugabe = sub_df["Zugabe"].sum()
                zugabe_wirkung_pro_tag = (total_extra_zugabe / (vol / 100) / f_konzentration) / tage
                
                v_real = round(becken_diff_pro_tag + dosis_wirkung_pro_tag + zugabe_wirkung_pro_tag, 3)
                d_neu = round(v_real * (vol / 100) * f_konzentration, 1)
                delta_ml = round(d_neu - historische_dosis, 1)
                diff_to_target = target_val - last["Wert"]
                einmalig_ml = round(diff_to_target * (vol / 100) * f_konzentration, 1) if diff_to_target > 0 else 0.0
                return v_real, d_neu, delta_ml, einmalig_ml, last["Wert"]
    return None, None, None, None, None

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
st.header("⏱️ Aktuelle Entwicklung (Letzte Messung)")
res1, res2 = st.columns(2)
res_cols = {"KH": res1, "CA": res2}

for key, c in cfg.items():
    r_col = res_cols[key]
    res = calculate_aquarium_strict_vC(c["df"], c["current_d"], s_vol, c["factor"], c["target"], c["is_ca"])
    if res:
        v_real, d_neu, delta, einmalig, _ = res
        dosis_bereits_aktiv = (abs(d_neu - c["current_d"]) < 0.1)
        if dosis_bereits_aktiv:
            r_col.success(f"🎉 **Tagesdosis optimal angepasst!** Pumpe läuft aktuell auf **{c['current_d']} ml**.")
            r_col.write(f"📉 Berechneter Verbrauch im letzten Intervall: **{v_real} {c['unit']}/Tag**")
        else:
            r_col.metric(f"Empfohlene Tagesdosis {c['brand']} (Wert halten)", f"{d_neu} ml", f"{delta} ml vs. Intervall-Basis")
            r_col.write(f"📉 Realer Gesamtverbrauch im Intervall: **{v_real} {c['unit']}/Tag**")
            
            if r_col.button(f"✅ Neue Tagesdosis für {key} aktivieren", key=f"act_{key}"):
                if key == "KH": st.session_state.kh_dosis_live = d_neu
                else: st.session_state.ca_dosis_live = d_neu
                
                # Zeilenumbruch-sichere Definition für den Sheet-Export
                p_list = ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"]
                w_list = [
                    s_vol, s_brand_kh, s_brand_ca, 
                    st.session_state.kh_dosis_live, st.session_state.ca_dosis_live, 
                    s_kh_f, s_ca_f, 
                    v_real if key=="KH" else setup_vals["KH_Verbrauch"], 
                    v_real if key=="CA" else setup_vals["CA_Verbrauch"]
                ]
                df_save = pd.DataFrame({"Parameter": p_list, "Wert": w_list})
                conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=df_save)
                st.cache_data.clear()
                st.rerun()
                
        if einmalig > 0 and not dosis_bereits_aktiv:
            r_col.warning(f"🔺 **Empfohlene Einzelerhöhung:** Dosiere einmalig **{einmalig} ml** extra für Wunschwert.")
    else:
        r_col.metric(f"Aktuelle Dosierung {c['brand']}", f"{c['current_d']} ml", "Warte auf neue Messdaten...")

# --- HISTORIE ---
st.divider()
with st.expander("📊 Historie & Verlauf", expanded=True):
    h1, h2 = st.columns(2)
    h_cols = {"KH": h1, "CA": h2}
    for key, c in cfg.items():
        with h_cols[key]:
            st.subheader(f"{c['brand']} Verlauf")
            if not c["df"].empty:
                st.line_chart(c["df"].dropna(subset=["Wert"]).set_index("Datum")["Wert"])
                st.dataframe(c["df"], use_container_width=True)
                sel_date = st.selectbox("Eintrag löschen:", options=c["df"]["Datum"].unique().tolist(), key=f"del_txt_{key}")
                if st.button(f"❌ Löschen ({key})", key=f"del_btn_{key}"):
                    conn.update(spreadsheet=SHEET_URL, worksheet=key, data=c["df"][c["df"]["Datum"] != sel_date])
                    st.cache_data.clear()
                    st.rerun()
