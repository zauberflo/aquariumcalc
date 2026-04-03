import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="AquaCalc Fix", page_icon="🐠")

# --- DATEI HANDLING ---
KH_FILE = "data_kh.csv"
CA_FILE = "data_ca.csv"

for f, cols in [(KH_FILE, ["Datum", "Wert"]), (CA_FILE, ["Datum", "Wert"])]:
    if not os.path.exists(f) or os.stat(f).st_size == 0:
        pd.DataFrame(columns=cols).to_csv(f, index=False)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Setup")
    volumen = st.number_input("Beckenvolumen (L)", value=100)
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    curr_kh_ml = st.number_input("Aktuell KH Duo", value=0.0, format="%.1f")
    curr_ca_ml = st.number_input("Aktuell Ca Duo", value=0.0, format="%.1f")
    st.divider()
    kh_factor = st.number_input("ml KH für +1° / 100L", value=10.0)
    ca_factor = st.number_input("ml Ca für +10mg / 100L", value=14.0)

st.title("🌊 AquaCalc: Messung & Korrektur")

# --- EINGABE ---
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.subheader("🧪 KH Messung")
    kh_date = st.date_input("Datum KH", datetime.now(), key="d_kh")
    kh_val = st.number_input("KH Wert", format="%.2f", key="kh_in")
    if st.button("KH Speichern"):
        df = pd.read_csv(KH_FILE)
        new = pd.DataFrame([[kh_date, kh_val]], columns=["Datum", "Wert"])
        pd.concat([df, new]).to_csv(KH_FILE, index=False)
        st.success("KH gespeichert!")
        st.rerun()

with col_in2:
    st.subheader("🧪 Ca Messung")
    ca_date = st.date_input("Datum Ca", datetime.now(), key="d_ca")
    ca_val = st.number_input("Ca Wert (mg/l)", step=1, key="ca_in")
    if st.button("Ca Speichern"):
        df = pd.read_csv(CA_FILE)
        new = pd.DataFrame([[ca_date, ca_val]], columns=["Datum", "Wert"])
        pd.concat([df, new]).to_csv(CA_FILE, index=False)
        st.success("Ca gespeichert!")
        st.rerun()

# --- BERECHNUNG ---
st.divider()
cols_res = st.columns(2)

# Berechnung KH
df_kh = pd.read_csv(KH_FILE)
if len(df_kh) >= 2:
    df_kh["Datum"] = pd.to_datetime(df_kh["Datum"])
    df_kh = df_kh.sort_values("Datum")
    last, prev = df_kh.iloc[-1], df_kh.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    if tage > 0:
        verbrauch_pro_tag = (prev["Wert"] - last["Wert"]) / tage
        extra_ml = verbrauch_pro_tag * (volumen / 100) * kh_factor
        cols_res[0].metric("Neue KH Dosis", f"{round(curr_kh_ml + extra_ml, 1)} ml", f"{round(extra_ml, 1)} ml Anpassung")
    else:
        cols_res[0].warning("Zweite KH-Messung an anderem Tag nötig.")
else:
    cols_res[0].info("Warte auf 2. KH-Messung...")

# Berechnung Ca
df_ca = pd.read_csv(CA_FILE)
if len(df_ca) >= 2:
    df_ca["Datum"] = pd.to_datetime(df_ca["Datum"])
    df_ca = df_ca.sort_values("Datum")
    last, prev = df_ca.iloc[-1], df_ca.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    if tage > 0:
        verbrauch_pro_tag = (prev["Wert"] - last["Wert"]) / tage
        extra_ml = (verbrauch_pro_tag / 10) * (volumen / 100) * ca_factor
        cols_res[1].metric("Neue Ca Dosis", f"{round(curr_ca_ml + extra_ml, 1)} ml", f"{round(extra_ml, 1)} ml Anpassung")
    else:
        cols_res[1].warning("Zweite Ca-Messung an anderem Tag nötig.")
else:
    cols_res[1].info("Warte auf 2. Ca-Messung...")

# --- CHARTS ---
st.subheader("📈 Historie")
c1, c2 = st.columns(2)
if not df_kh.empty:
    df_kh_plot = df_kh.copy()
    df_kh_plot["Datum"] = df_kh_plot["Datum"].dt.date
    c1.line_chart(df_kh_plot.set_index("Datum"))
if not df_ca.empty:
    df_ca_plot = df_ca.copy()
    df_ca_plot["Datum"] = df_ca_plot["Datum"].dt.date
    c2.line_chart(df_ca_plot.set_index("Datum"))