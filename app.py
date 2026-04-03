import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="AquaCalc Separat", page_icon="🐠")

# --- DATEI HANDLING (Getrennte Dateien für KH und Ca) ---
KH_FILE = "data_kh.csv"
CA_FILE = "data_ca.csv"

for f, cols in [(KH_FILE, ["Datum", "Wert"]), (CA_FILE, ["Datum", "Wert"])]:
    if not os.path.exists(f) or os.stat(f).st_size == 0:
        pd.DataFrame(columns=cols).to_csv(f, index=False)

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Setup")
    volumen = st.number_input("Beckenvolumen (L)", value=100)
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    curr_kh_ml = st.number_input("Aktuell KH Duo", value=0.0)
    curr_ca_ml = st.number_input("Aktuell Ca Duo", value=0.0)
    st.divider()
    st.subheader("Produkte")
    kh_factor = st.number_input("ml KH für +1° / 100L", value=10.0)
    ca_factor = st.number_input("ml Ca für +10mg / 100L", value=14.0)

st.title("🌊 AquaCalc: Getrennte Messung")

# --- EINGABE-BEREICH ---
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.subheader("🧪 KH Messung")
    kh_val = st.number_input("KH Wert", format="%.2f", key="kh_in")
    if st.button("KH Speichern"):
        df = pd.read_csv(KH_FILE)
        new = pd.DataFrame([[datetime.now().date(), kh_val]], columns=["Datum", "Wert"])
        pd.concat([df, new]).to_csv(KH_FILE, index=False)
        st.success("KH gespeichert!")

with col_in2:
    st.subheader("🧪 Ca Messung")
    ca_val = st.number_input("Ca Wert (mg/l)", step=1, key="ca_in")
    if st.button("Ca Speichern"):
        df = pd.read_csv(CA_FILE)
        new = pd.DataFrame([[datetime.now().date(), ca_val]], columns=["Datum", "Wert"])
        pd.concat([df, new]).to_csv(CA_FILE, index=False)
        st.success("Ca gespeichert!")

# --- BERECHNUNG ---
st.divider()
cols_res = st.columns(2)

# Logik für KH
df_kh = pd.read_csv(KH_FILE)
if len(df_kh) >= 2:
    df_kh["Datum"] = pd.to_datetime(df_kh["Datum"])
    df_kh = df_kh.sort_values("Datum")
    last, prev = df_kh.iloc[-1], df_kh.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    if tage > 0:
        diff = prev["Wert"] - last["Wert"]
        extra = (diff / tage) * (volumen / 100) * kh_factor
        cols_res[0].metric("Neue KH Dosis", f"{round(curr_kh_ml + extra, 1)} ml", f"{round(extra, 1)} ml Korrektur")

# Logik für Ca
df_ca = pd.read_csv(CA_FILE)
if len(df_ca) >= 2:
    df_ca["Datum"] = pd.to_datetime(df_ca["Datum"])
    df_ca = df_ca.sort_values("Datum")
    last, prev = df_ca.iloc[-1], df_ca.iloc[-2]
    tage = (last["Datum"] - prev["Datum"]).days
    if tage > 0:
        diff = prev["Wert"] - last["Wert"]
        extra = ((diff / 10) / tage) * (volumen / 100) * ca_factor
        cols_res[1].metric("Neue Ca Dosis", f"{round(curr_ca_ml + extra, 1)} ml", f"{round(extra, 1)} ml Korrektur")

# --- CHARTS ---
st.subheader("📈 Historie")
c1, c2 = st.columns(2)
if not df_kh.empty: c1.line_chart(df_kh.set_index("Datum"), y="Wert")
if not df_ca.empty: c2.line_chart(df_ca.set_index("Datum"), y="Wert")