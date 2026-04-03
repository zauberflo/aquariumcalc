import streamlit as st
import pandas as pd
from datetime import datetime
import os

# Seite konfigurieren
st.set_page_config(page_title="AquaCalc", page_icon="🐠")

# --- DATEI HANDLING (DB ERSATZ) ---
DB_FILE = "data.csv"
if not os.path.exists(DB_FILE) or os.stat(DB_FILE).st_size == 0:
    df = pd.DataFrame(columns=["Datum", "KH", "Ca"])
    df.to_csv(DB_FILE, index=False)

# --- SIDEBAR (EINSTELLUNGEN) ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    volumen = st.number_input("Beckenvolumen (Netto L)", value=100)
    st.divider()
    st.subheader("Produkt-Parameter")
    kh_ml_per_1 = st.number_input("ml KH-Duo für +1° dKH (pro 100L)", value=10.0)
    ca_ml_per_10 = st.number_input("ml Ca-Duo für +10mg/l (pro 100L)", value=14.0)

# --- HAUPTBEREICH ---
st.title("🌊 Zauberflos AquaCalc")

# Neue Messung hinzufügen
with st.expander("📝 Neue Messwerte eintragen", expanded=True):
    col1, col2, col3 = st.columns(3)
    d_val = col1.date_input("Datum", datetime.now())
    kh_val = col2.number_input("KH Wert", format="%.2f", value=7.5)
    ca_val = col3.number_input("Ca Wert (mg/l)", value=420)
    
    if st.button("💾 Messung speichern"):
        df = pd.read_csv(DB_FILE)
        new_row = pd.DataFrame([[d_val, kh_val, ca_val]], columns=["Datum", "KH", "Ca"])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(DB_FILE, index=False)
        st.success("Daten wurden lokal gespeichert!")

# Daten laden und berechnen
df_display = pd.read_csv(DB_FILE)

if len(df_display) >= 2:
    # Sortieren nach Datum, falls durcheinander
    df_display["Datum"] = pd.to_datetime(df_display["Datum"])
    df_display = df_display.sort_values("Datum")
    
    # Die letzten zwei Zeilen
    last = df_display.iloc[-1]
    prev = df_display.iloc[-2]
    
    tage = (last["Datum"] - prev["Datum"]).days

    if tage > 0:
        # Verbräuche berechnen
        kh_diff = prev["KH"] - last["KH"]
        ca_diff = prev["Ca"] - last["Ca"]
        
        # Dosierung pro Tag (Formel: Verbrauch * (Volumen/100) * Produkt-Faktor)
        kh_daily_ml = (kh_diff / tage) * (volumen / 100) * kh_ml_per_1
        ca_daily_ml = ((ca_diff / 10) / tage) * (volumen / 100) * ca_ml_per_10

        st.subheader("🚀 Deine Dosierempfehlung")
        res1, res2 = st.columns(2)
        res1.metric("KH-Duo", f"{round(max(0, kh_daily_ml), 1)} ml / Tag", f"-{round(kh_diff/tage, 2)} dKH")
        res2.metric("Ca-Duo", f"{round(max(0, ca_daily_ml), 1)} ml / Tag", f"-{round(ca_diff/tage, 0)} mg/l")
        
        # Spielerei: Chart
        st.subheader("📈 Verlauf")
        st.line_chart(df_display.set_index("Datum")[["KH", "Ca"]])
    else:
        st.info("Trage Messungen von verschiedenen Tagen ein, um den Verbrauch zu sehen.")

# Tabelle zeigen
if st.checkbox("Rohdaten anzeigen"):
    st.dataframe(df_display)
