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

# Standardwerte (Fallbacks)
setup_values = {
    "Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca",
    "KH_Dosis": 0.0, "CA_Dosis": 0.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0
}

# Werte aus Tabelle in Dictionary laden
if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = row["Parameter"]
        w = row["Wert"]
        if p in setup_values:
            # Versuch Zahl zu konvertieren, sonst String behalten
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
    
    if st.button("💾 Setup dauerhaft speichern"):
        new_setup = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor"],
            "Wert": [s_volumen, s_brand_kh, s_brand_ca, s_curr_kh_ml, s_curr_ca_ml, s_kh_factor, s_ca_factor]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup)
        st.cache_data.clear()
        st.success("Setup in Cloud gespeichert!")
        st.rerun()

# Variablen für Berechnungen zuweisen
volumen = s_volumen
brand_kh, brand_ca = s_brand_kh, s_brand_ca
curr_kh_ml, curr_ca_ml = s_curr_kh_ml, s_curr_ca_ml
kh_factor, ca_factor = s_kh_factor, s_ca_factor

# --- HAUPTDATEN LADEN ---
df_kh = load_data("KH")
df_ca = load_data("CA")

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- EINGABEBEREICH ---
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.subheader(f"🧪 {brand_kh} Messung")
    kh_date = st.date_input("Datum KH", datetime.now(), key="d_kh")
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kh_in")
    
    c1, c2 = st.columns(2)
    if c1.button("💾 KH Speichern"):
        current_df = load_data("KH")
        new_row = pd.DataFrame([{"Datum": str(kh_date), "Wert": float(kh_val)}])
        updated_df = pd.concat([current_df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=updated_df)
        st.cache_data.clear()
        st.success("KH gespeichert!")
        st.rerun()
    
    if c2.button("🗑️ KH Letzten löschen"):
        if not df_kh.empty:
            updated_df = df_kh[:-1]
            conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=updated_df)
            st.cache_data.clear()
            st.rerun()

with col_in2:
    st.subheader(f"🧪 {brand_ca} Messung")
    ca_date = st.date_input("Datum Ca", datetime.now(), key="d_ca")
    ca_val = st.number_input("Messwert (mg/l)", step=1, key="ca_in")
    
    c3, c4 = st.columns(2)
    if c3.button("💾 Ca Speichern"):
        current_df = load_data("CA")
        new_row = pd.DataFrame([{"Datum": str(ca_date), "Wert": float(ca_val)}])
        updated_df = pd.concat([current_df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=updated_df)
        st.cache_data.clear()
        st.success("Ca gespeichert!")
        st.rerun()
        
    if c4.button("🗑️ Ca Letzten löschen"):
        if not df_ca.empty:
            updated_df = df_ca[:-1]
            conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=updated_df)
            st.cache_data.clear()
            st.rerun()

# --- BERECHNUNG & AUSGABE ---
st.divider()
res_col1, res_col2 = st.columns(2)

# Berechnung KH
if df_kh is not None and len(df_kh) >= 2:
    df_kh_calc = df_kh.copy()
    df_kh_calc["Datum"] = pd.to_datetime(df_kh_calc["Datum"])
    df_kh_calc = df_kh_calc.sort_values("Datum")
    last, prev = df_kh_calc.iloc[-1], df_kh_calc.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    
    if tage > 0:
        verbrauch_messung = (prev["Wert"] - last["Wert"]) / tage
        dosis_in_kh = curr_kh_ml / (volumen / 100) / kh_factor
        gesamt_verbrauch_kh = verbrauch_messung + dosis_in_kh
        korrektur = verbrauch_messung * (volumen / 100) * kh_factor
        
        res_col1.metric(f"Empfohlene Dosis {brand_kh}", f"{round(curr_kh_ml + korrektur, 1)} ml", f"{round(korrektur, 1)} ml Delta")
        res_col1.subheader(f"📉 Realer Verbrauch: {round(gesamt_verbrauch_kh, 3)} dKH/Tag")
        res_col1.caption(f"Aktuelle Dosis deckt {round(dosis_in_kh, 3)} dKH ab.")
    else:
        res_col1.warning("Zwei Messungen an verschiedenen Tagen nötig.")
else:
    res_col1.info("Warte auf KH-Daten (min. 2)...")

# Berechnung Calcium
if df_ca is not None and len(df_ca) >= 2:
    df_ca_calc = df_ca.copy()
    df_ca_calc["Datum"] = pd.to_datetime(df_ca_calc["Datum"])
    df_ca_calc = df_ca_calc.sort_values("Datum")
    last, prev = df_ca_calc.iloc[-1], df_ca_calc.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    
    if tage > 0:
        verbrauch_messung_ca = (prev["Wert"] - last["Wert"]) / tage
        dosis_in_ca = curr_ca_ml / (volumen / 100) / (ca_factor / 10)
        gesamt_verbrauch_ca = verbrauch_messung_ca + dosis_in_ca
        korrektur_ca = (verbrauch_messung_ca / 10) * (volumen / 100) * ca_factor
        
        res_col2.metric(f"Empfohlene Dosis {brand_ca}", f"{round(curr_ca_ml + korrektur_ca, 1)} ml", f"{round(korrektur_ca, 1)} ml Delta")
        res_col2.subheader(f"📉 Realer Verbrauch: {round(gesamt_verbrauch_ca, 2)} mg/l / Tag")
        res_col2.caption(f"Aktuelle Dosis deckt {round(dosis_in_ca, 2)} mg/l ab.")
    else:
        res_col2.warning("Zwei Messungen an verschiedenen Tagen nötig.")
else:
    res_col2.info("Warte auf Ca-Daten (min. 2)...")

# --- HISTORIE ---
st.divider()
with st.expander("📊 Historie & Verlauf"):
    h1, h2 = st.columns(2)
    if not df_kh.empty:
        h1.write(f"Verlauf {brand_kh}")
        h1.line_chart(df_kh.set_index("Datum")["Wert"])
        h1.dataframe(df_kh, use_container_width=True)
    if not df_ca.empty:
        h2.write(f"Verlauf {brand_ca}")
        h2.line_chart(df_ca.set_index("Datum")["Wert"])
        h2.dataframe(df_ca, use_container_width=True)
