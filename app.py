import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="AquaCalc Pro", page_icon="🐠")

# --- DATEI HANDLING ---
DB_FILE = "data.csv"
if not os.path.exists(DB_FILE) or os.stat(DB_FILE).st_size == 0:
    df = pd.DataFrame(columns=["Datum", "KH", "Ca"])
    df.to_csv(DB_FILE, index=False)

# --- SIDEBAR: KONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    # Gesamtzahl der Liter (Netto)
    volumen = st.number_input("Gesamtvolumen Aquarium (Netto L)", value=100, step=10)
    
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    curr_kh_ml = st.number_input("Aktuell KH Duo", value=0.0, step=0.1)
    curr_ca_ml = st.number_input("Aktuell Ca Duo", value=0.0, step=0.1)
    
    st.divider()
    st.subheader("Produkt-Parameter")
    kh_ml_per_1 = st.number_input("ml KH-Duo für +1° dKH (pro 100L)", value=10.0)
    ca_ml_per_10 = st.number_input("ml Ca-Duo für +10mg/l (pro 100L)", value=14.0)

# --- HAUPTBEREICH ---
st.title("🌊 Zauberflos AquaCalc")

# Eingabe-Bereich
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
        st.success("Gespeichert! Die App aktualisiert jetzt die Berechnung.")

# Daten laden
df_display = pd.read_csv(DB_FILE)

if len(df_display) >= 2:
    df_display["Datum"] = pd.to_datetime(df_display["Datum"])
    df_display = df_display.sort_values("Datum")
    
    last = df_display.iloc[-1]
    prev = df_display.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days

    if tage > 0:
        # 1. Differenz zwischen den Messungen
        kh_diff = prev["KH"] - last["KH"]
        ca_diff = prev["Ca"] - last["Ca"]
        
        # 2. Zusätzlicher Bedarf (was fehlte, um den Wert zu halten)
        kh_extra_ml = (kh_diff / tage) * (volumen / 100) * kh_ml_per_1
        ca_extra_ml = ((ca_diff / 10) / tage) * (volumen / 100) * ca_ml_per_10

        # 3. Neue Gesamtdosierung
        new_kh_total = curr_kh_ml + kh_extra_ml
        new_ca_total = curr_ca_ml + ca_extra_ml

        st.subheader("🚀 Neue Dosierempfehlung")
        st.info(f"Berechnet auf Basis von **{volumen} Litern** über **{tage} Tage**.")
        
        res1, res2 = st.columns(2)
        
        # KH Anzeige
        with res1:
            st.metric("Neue KH Dosis", f"{round(max(0, new_kh_total), 1)} ml/Tag")
            st.caption(f"Anpassung: {'+' if kh_extra_ml >= 0 else ''}{round(kh_extra_ml, 1)} ml")
            if last["KH"] < 7.0: st.warning("KH zu niedrig!")

        # Ca Anzeige
        with res2:
            st.metric("Neue Ca Dosis", f"{round(max(0, new_ca_total), 1)} ml/Tag")
            st.caption(f"Anpassung: {'+' if ca_extra_ml >= 0 else ''}{round(ca_extra_ml, 1)} ml")
            if last["Ca"] < 400: st.warning("Ca zu niedrig!")

        st.divider()
        st.subheader("📈 Verlauf")
        st.line_chart(df_display.set_index("Datum")[["KH", "Ca"]])
    else:
        st.info("Bitte zwei Messungen an unterschiedlichen Tagen eintragen.")

if st.checkbox("Tabellen-Historie zeigen"):
    st.dataframe(df_display)