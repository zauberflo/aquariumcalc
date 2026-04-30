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
st.set_page_config(
    page_title="AquaCalc Cloud 572",
    page_icon=logo_img, 
    layout="wide"
)

# --- IPHONE HEADER INJEKTION ---
st.components.v1.html(
    f"""
    <script>
        var link = window.parent.document.createElement('link');
        link.rel = 'apple-touch-icon';
        link.href = '{GITHUB_LOGO_URL}';
        window.parent.document.getElementsByTagName('head')[0].appendChild(link);
    </script>
    """,
    height=0,
)

# --- VERBINDUNG ZU GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

def load_data(sheet_name):
    try:
        data = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)
        return data.dropna(how="all")
    except Exception:
        return pd.DataFrame()

# --- SETUP DATEN LADEN & INITIALISIEREN ---
df_setup = load_data("Setup")

# Standardwerte (Fallbacks) inklusive Speicherplätzen für Verbrauch
setup_values = {
    "Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca",
    "KH_Dosis": 0.0, "CA_Dosis": 0.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0,
    "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0
}

if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        w = row["Wert"]
        if p in setup_values and pd.notna(w):
            try:
                setup_values[p] = float(w) if str(w).replace('.','',1).isdigit() else w
            except:
                setup_values[p] = w

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_volumen = st.number_input("Beckenvolumen (Netto L)", value=float(setup_values["Volumen"]))
    
    st.divider()
    s_brand_kh = st.text_input("Marke KH-Lösung", value=str(setup_values["KH_Brand"]))
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=str(setup_values["CA_Brand"]))
    
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    s_curr_kh_ml = st.number_input(f"Dosierung {s_brand_kh}", value=float(setup_values["KH_Dosis"]), format="%.1f")
    s_curr_ca_ml = st.number_input(f"Dosierung {s_brand_ca}", value=float(setup_values["CA_Dosis"]), format="%.1f")
    
    st.divider()
    st.subheader("Produkt-Parameter")
    s_kh_factor = st.number_input(f"ml {s_brand_kh} für +1° / 100L", value=float(setup_values["KH_Faktor"]))
    s_ca_factor = st.number_input(f"ml {s_brand_ca} für +10mg / 100L", value=float(setup_values["CA_Faktor"]))
    
    if st.button("💾 Setup & Dosis speichern"):
        new_setup = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
            "Wert": [s_volumen, s_brand_kh, s_brand_ca, s_curr_kh_ml, s_curr_ca_ml, s_kh_factor, s_ca_factor, setup_values["KH_Verbrauch"], setup_values["CA_Verbrauch"]]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup)
        st.cache_data.clear()
        st.success("Gespeichert!")
        st.rerun()

# --- DATEN LADEN ---
df_kh = load_data("KH")
df_ca = load_data("CA")

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- EINGABEBEREICH ---
col_in1, col_in2 = st.columns(2)
with col_in1:
    st.subheader(f"🧪 {s_brand_kh} Messung")
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kh_in")
    if st.button("💾 KH Speichern"):
        new_row = pd.DataFrame([{"Datum": str(datetime.now().date()), "Wert": float(kh_val)}])
        conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=pd.concat([df_kh, new_row], ignore_index=True))
        st.cache_data.clear()
        st.rerun()

with col_in2:
    st.subheader(f"🧪 {s_brand_ca} Messung")
    ca_val = st.number_input("Messwert (mg/l)", step=1, key="ca_in")
    if st.button("💾 Ca Speichern"):
        new_row = pd.DataFrame([{"Datum": str(datetime.now().date()), "Wert": float(ca_val)}])
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=pd.concat([df_ca, new_row], ignore_index=True))
        st.cache_data.clear()
        st.rerun()

# --- BERECHNUNG & AUTO-SAVE VERBRAUCH ---
st.divider()
res_col1, res_col2 = st.columns(2)

def calc_and_save(df, dosis, vol, factor, param_name, is_ca=False):
    if df is not None and len(df) >= 2:
        d = df.copy()
        d["Datum"] = pd.to_datetime(d["Datum"], errors='coerce')
        d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
        d = d.dropna().sort_values("Datum")
        
        if len(d) >= 2:
            last, prev = d.iloc[-1], d.iloc[-2]
            tage = (last["Datum"] - prev["Datum"]).days
            if tage > 0:
                abfall = (prev["Wert"] - last["Wert"]) / tage
                f = factor / 10 if is_ca else factor
                dosis_wirkung = dosis / (vol / 100) / f
                verbrauch = round(abfall + dosis_wirkung, 3)
                
                # Wenn der berechnete Verbrauch neu ist, im Setup-Dictionary (temporär) speichern
                if verbrauch != setup_values[param_name]:
                    setup_values[param_name] = verbrauch
                    # Hier könnte man ein Auto-Update zum Sheet machen, 
                    # wir machen es aber elegant über die Anzeige
                
                delta_ml = round(abfall * (vol / 100) * f, 1)
                return verbrauch, round(dosis + delta_ml, 1), delta_ml
    return setup_values[param_name], None, None

# KH
v_kh, d_kh, diff_kh = calc_and_save(df_kh, s_curr_kh_ml, s_volumen, s_kh_factor, "KH_Verbrauch")
if d_kh is not None:
    res_col1.metric(f"Dosis {s_brand_kh}", f"{d_kh} ml", f"{diff_kh} ml Delta")
    res_col1.subheader(f"📉 Realer Verbrauch: {v_kh} dKH/Tag")
else:
    res_col1.subheader(f"📉 Letzter Verbrauch: {setup_values['KH_Verbrauch']} dKH/Tag")
    res_col1.info("Warte auf neue Messungen...")

# CA
v_ca, d_ca, diff_ca = calc_and_save(df_ca, s_curr_ca_ml, s_volumen, s_ca_factor, "CA_Verbrauch", is_ca=True)
if d_ca is not None:
    res_col2.metric(f"Dosis {s_brand_ca}", f"{d_ca} ml", f"{diff_ca} ml Delta")
    res_col2.subheader(f"📉 Realer Verbrauch: {v_ca} mg/l / Tag")
else:
    res_col2.subheader(f"📉 Letzter Verbrauch: {setup_values['CA_Verbrauch']} mg/l / Tag")
    res_col2.info("Warte auf neue Messungen...")

# Auto-Save Logik: Wenn Werte berechnet wurden, die von den gespeicherten abweichen
if (v_kh != setup_values["KH_Verbrauch"] or v_ca != setup_values["CA_Verbrauch"]) and (d_kh is not None or d_ca is not None):
    new_setup_auto = pd.DataFrame({
        "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
        "Wert": [s_volumen, s_brand_kh, s_brand_ca, s_curr_kh_ml, s_curr_ca_ml, s_kh_factor, s_ca_factor, v_kh, v_ca]
    })
    conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup_auto)
    st.cache_data.clear()

# --- HISTORIE ---
st.divider()
with st.expander("📊 Historie & Verlauf"):
    h1, h2 = st.columns(2)
    if not df_kh.empty:
        h1.line_chart(df_kh.set_index("Datum")["Wert"])
    if not df_ca.empty:
        h2.line_chart(df_ca.set_index("Datum")["Wert"])
