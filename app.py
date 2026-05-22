import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
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

# Standardwerte (Fallbacks)
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

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=float(setup_values["Volumen"]))
    
    st.divider()
    s_brand_kh = st.text_input("Marke KH-Lösung", value=str(setup_values["KH_Brand"]))
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=str(setup_values["CA_Brand"]))
    
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    st.caption("Wichtig: Das ist die Menge, die bis JETZT gelaufen ist!")
    s_kh_d = st.number_input(f"Dosis {s_brand_kh}", value=float(setup_values["KH_Dosis"]), format="%.1f")
    s_ca_d = st.number_input(f"Dosis {s_brand_ca}", value=float(setup_values["CA_Dosis"]), format="%.1f")
    
    st.divider()
    st.subheader("Produkt-Parameter")
    s_kh_f = st.number_input(f"ml {s_brand_kh} für +1° dKH / 100L", value=float(setup_values["KH_Faktor"]))
    s_ca_f = st.number_input(f"ml {s_brand_ca} für +10mg Ca / 100L", value=float(setup_values["CA_Faktor"]))

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

# --- DATEN LADEN ---
df_kh = load_data("KH")
df_ca = load_data("CA")

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- MESSWERTE EINGEBEN & AUTO-SAVE DOSIERUNG ---
c_in1, c_in2 = st.columns(2)
with c_in1:
    st.subheader(f"🧪 {s_brand_kh} Messung")
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kin")
    if st.button("💾 KH Speichern"):
        new_kh = pd.concat([df_kh, pd.DataFrame([{"Datum": str(datetime.now().date()), "Wert": float(kh_val)}])], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=new_kh)
        
        new_setup = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
            "Wert": [s_vol, s_brand_kh, s_brand_ca, s_kh_d, s_ca_d, s_kh_f, s_ca_f, setup_values["KH_Verbrauch"], setup_values["CA_Verbrauch"]]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup)
        st.cache_data.clear()
        st.success("Messwert & Dosierung gespeichert!")
        st.rerun()

with c_in2:
    st.subheader(f"🧪 {s_brand_ca} Messung")
    ca_val = st.number_input("Messwert (mg/l)", step=1, key="cin")
    if st.button("💾 Ca Speichern"):
        new_ca = pd.concat([df_ca, pd.DataFrame([{"Datum": str(datetime.now().date()), "Wert": float(ca_val)}])], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=new_ca)
        
        new_setup = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
            "Wert": [s_vol, s_brand_kh, s_brand_ca, s_kh_d, s_ca_d, s_kh_f, s_ca_f, setup_values["KH_Verbrauch"], setup_values["CA_Verbrauch"]]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup)
        st.cache_data.clear()
        st.success("Messwert & Dosierung gespeichert!")
        st.rerun()

# --- HILFSFUNKTION FÜR MONATS-DURCHSCHNITT ---
def calculate_monthly_average(df, running_dosis, vol, factor, is_ca=False):
    if df is not None and len(df) >= 2:
        d = df.copy()
        d["Datum"] = pd.to_datetime(d["Datum"])
        d["Wert"] = pd.to_numeric(d["Wert"])
        d = d.dropna().sort_values("Datum")
        
        # Filter auf die letzten 30 Tage ab heute
        one_month_ago = datetime.now() - timedelta(days=30)
        d = d[d["Datum"] >= one_month_ago]
        
        if len(d) >= 2:
            verbrauche = []
            f_konzentration = factor / 10 if is_ca else factor
            
            # Gehe paarweise durch die Messungen des letzten Monats
            for i in range(1, len(d)):
                prev = d.iloc[i-1]
                last = d.iloc[i]
                tage = (last["Datum"] - prev["Datum"]).days
                
                if tage > 0:
                    becken_diff = (prev["Wert"] - last["Wert"]) / tage
                    dosis_wirkung = running_dosis / (vol / 100) / f_konzentration
                    v_intervall = becken_diff + dosis_wirkung
                    verbrauche.append(v_intervall)
            
            if verbrauche:
                avg_v = sum(verbrauche) / len(verbrauche)
                d_empfohlen = avg_v * (vol / 100) * f_konzentration
                return round(avg_v, 3), round(d_empfohlen, 1)
    return None, None

# --- BASIS-BERECHNUNG (LETZTE BEIDEN MESSUNGEN) ---
st.divider()
st.header("⏱️ Aktuelle Entwicklung (Letzte Messung)")
res1, res2 = st.columns(2)

def calculate_aquarium(df, running_dosis, vol, factor, target_val, is_ca=False):
    if df is not None and len(df) >= 2:
        d = df.copy()
        d["Datum"] = pd.to_datetime(d["Datum"])
        d["Wert"] = pd.to_numeric(d["Wert"])
        d = d.dropna().sort_values("Datum")
        
        if len(d) >= 2:
            last, prev = d.iloc[-1], d.iloc[-2]
            tage = (last["Datum"] - prev["Datum"]).days
            
            if tage > 0:
                becken_differenz_pro_tag = (prev["Wert"] - last["Wert"]) / tage
                f_konzentration = factor / 10 if is_ca else factor
                dosierte_menge_in_wert = running_dosis / (vol / 100) / f_konzentration
                v_real = round(becken_differenz_pro_tag + dosierte_menge_in_wert, 3)
                d_neu = round(v_real * (vol / 100) * f_konzentration, 1)
                delta_ml = round(d_neu - running_dosis, 1)
                
                diff_to_target = target_val - last["Wert"]
                einmalig_ml = round(diff_to_target * (vol / 100) * f_konzentration, 1) if diff_to_target > 0 else 0.0
                
                return v_real, d_neu, delta_ml, einmalig_ml, last["Wert"]
    return None, None, None, None, None

# --- AUSGABE KH AKTUELL ---
v_kh, d_kh, delta_kh, up_kh, last_kh = calculate_aquarium(df_kh, s_kh_d, s_vol, s_kh_f, target_kh, is_ca=False)
if v_kh is not None:
    res1.metric(f"Empfehlung {s_brand_kh} (Kurzzeit)", f"{d_kh} ml", f"{delta_kh} ml vs. bisher")
    res1.write(f"Verbrauch aktuell: **{v_kh} dKH/Tag**")
    if up_kh > 0:
        res1.warning(f"🔺 **Einmalig:** +{up_kh} ml extra für Ziel {target_kh} dKH.")
    
    if res1.button("✅ Diese Kurzzeit-Dosis aktivieren"):
        setup_values["KH_Dosis"] = d_kh
        setup_values["KH_Verbrauch"] = v_kh
        new_s = pd.DataFrame({"Parameter": list(setup_values.keys()), "Wert": list(setup_values.values())})
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_s)
        st.cache_data.clear()
        st.rerun()
else:
    res1.info("Warte auf ausreichende KH Messdaten...")

# --- AUSGABE CA AKTUELL ---
v_ca, d_ca, delta_ca, up_ca, last_ca = calculate_aquarium(df_ca, s_ca_d, s_vol, s_ca_f, target_ca, is_ca=True)
if v_ca is not None:
    res2.metric(f"Empfehlung {s_brand_ca} (Kurzzeit)", f"{d_ca} ml", f"{delta_ca} ml vs. bisher")
    res2.write(f"Verbrauch aktuell: **{v_ca} mg/l/Tag**")
    if up_ca > 0:
        res2.warning(f"🔺 **Einmalig:** +{up_ca} ml extra für Ziel {target_ca} mg/l.")
    
    if res2.button("✅ Diese Kurzzeit-Dosis aktivieren"):
        setup_values["CA_Dosis"] = d_ca
        setup_values["CA_Verbrauch"] = v_ca
        new_s = pd.DataFrame({"Parameter": list(setup_values.keys()), "Wert": list(setup_values.values())})
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_s)
        st.cache_data.clear()
        st.rerun()
else:
    res2.info("Warte auf ausreichende Ca Messdaten...")

# --- NEUER BEREICH: LANGZEIT TREND (30 TAGE DURCHSCHNITT) ---
st.divider()
st.header("📊 Langzeit-Trend (Ø Letzte 30 Tage)")
trend1, trend2 = st.columns(2)

# KH Trend
avg_v_kh, avg_d_kh = calculate_monthly_average(df_kh, s_kh_d, s_vol, s_kh_f, is_ca=False)
if avg_v_kh is not None:
    trend1.metric(f"Glatte Monats-Dosis {s_brand_kh}", f"{avg_d_kh} ml", f"{round(avg_d_kh - s_kh_d, 1)} ml Delta")
    trend1.write(f"📈 Ø Verbrauch (30 Tage): **{avg_v_kh} dKH/Tag**")
    if trend1.button("📈 Gequetschte Monats-Dosis für KH übernehmen"):
        setup_values["KH_Dosis"] = avg_d
