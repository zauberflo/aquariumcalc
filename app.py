import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# App Konfiguration
st.set_page_config(page_title="AquaCalc Cloud 572", page_icon="🐠", layout="wide")

# --- VERBINDUNG ZU GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# DEINE TABELLEN-URL (Direkt im Code, um SpreadsheetNotFound zu vermeiden)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit#gid=0"

def load_data(sheet_name):
    try:
        # Wir übergeben die URL hier explizit beim Lesen
        data = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)
        return data.dropna(how="all")
    except Exception:
        return pd.DataFrame(columns=["Datum", "Wert"])

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    volumen = st.number_input("Beckenvolumen (Netto L)", value=572)
    
    st.divider()
    brand_kh = st.text_input("Marke KH-Lösung", value="Oceamo Duo KH")
    brand_ca = st.text_input("Marke Ca-Lösung", value="Oceamo Duo Ca")
    
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    curr_kh_ml = st.number_input(f"Aktuell {brand_kh}", value=0.0, format="%.1f")
    curr_ca_ml = st.number_input(f"Aktuell {brand_ca}", value=0.0, format="%.1f")
    
    st.divider()
    st.subheader("Produkt-Parameter")
    kh_factor = st.number_input(f"ml {brand_kh} für +1° / 100L", value=10.0)
    ca_factor = st.number_input(f"ml {brand_ca} für +10mg / 100L", value=14.0)
    
    st.divider()
    st.info("Hinweis: Daten werden direkt in Google Sheets gespeichert.")

# --- DATEN LADEN ---
df_kh = load_data("KH")
df_ca = load_data("CA")

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- EINGABEBEREICH ---
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.subheader(f"🧪 {brand_kh} Messung")
    kh_date = st.date_input("Datum KH", datetime.now(), key="d_kh")
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kh_val")
    
    c1, c2 = st.columns(2)
    if c1.button("💾 KH Speichern"):
        new_row = pd.DataFrame([{"Datum": str(kh_date), "Wert": kh_val}])
        updated_df = pd.concat([df_kh, new_row], ignore_index=True)
        # URL beim Update hinzufügen
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
    ca_val = st.number_input("Messwert (mg/l)", step=1, key="ca_val")
    
    c3, c4 = st.columns(2)
    if c3.button("💾 Ca Speichern"):
        new_row = pd.DataFrame([{"Datum": str(ca_date), "Wert": ca_val}])
        updated_df = pd.concat([df_ca, new_row], ignore_index=True)
        # URL beim Update hinzufügen
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

# Berechnung Logik KH
if len(df_kh) >= 2:
    df_kh["Datum"] = pd.to_datetime(df_kh["Datum"])
    df_kh = df_kh.sort_values("Datum")
    last, prev = df_kh.iloc[-1], df_kh.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    if tage > 0:
        verbrauch_pro_tag = (prev["Wert"] - last["Wert"]) / tage
        korrektur = verbrauch_pro_tag * (volumen / 100) * kh_factor
        res_col1.metric(f"Neue Dosis {brand_kh}", f"{round(curr_kh_ml + korrektur, 1)} ml/Tag", f"{round(korrektur, 1)} ml Anpassung")
    else:
        res_col1.warning("Zwei Messungen an unterschiedlichen Tagen nötig.")
else:
    res_col1.info("Warte auf KH-Daten...")

# Berechnung Logik Ca
if len(df_ca) >= 2:
    df_ca["Datum"] = pd.to_datetime(df_ca["Datum"])
    df_ca = df_ca.sort_values("Datum")
    last, prev = df_ca.iloc[-1], df_ca.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    if tage > 0:
        verbrauch_pro_tag = (prev["Wert"] - last["Wert"]) / tage
        korrektur = (verbrauch_pro_tag / 10) * (volumen / 100) * ca_factor
        res_col2.metric(f"Neue Dosis {brand_ca}", f"{round(curr_ca_ml + korrektur, 1)} ml/Tag", f"{round(korrektur, 1)} ml Anpassung")
    else:
        res_col2.warning("Zwei Messungen an unterschiedlichen Tagen nötig.")
else:
    res_col2.info("Warte auf Ca-Daten...")

# --- HISTORIE & CHARTS ---
st.divider()
exp = st.expander("📊 Historie & Verlauf")
with exp:
    h1, h2 = st.columns(2)
    if not df_kh.empty:
        h1.write(f"Verlauf {brand_kh}")
        df_kh_plot = df_kh.copy()
        df_kh_plot["Datum"] = pd.to_datetime(df_kh_plot["Datum"]).dt.date
        h1.line_chart(df_kh_plot.set_index("Datum")["Wert"])
        h1.dataframe(df_kh, use_container_width=True)
        
    if not df_ca.empty:
        h2.write(f"Verlauf {brand_ca}")
        df_ca_plot = df_ca.copy()
        df_ca_plot["Datum"] = pd.to_datetime(df_ca_plot["Datum"]).dt.date
        h2.line_chart(df_ca_plot.set_index("Datum")["Wert"])
        h2.dataframe(df_ca, use_container_width=True)