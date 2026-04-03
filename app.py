import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="AquaCalc Pro", page_icon="🐠")

# --- DATEI HANDLING ---
KH_FILE = "data_kh.csv"
CA_FILE = "data_ca.csv"

for f, cols in [(KH_FILE, ["Datum", "Wert"]), (CA_FILE, ["Datum", "Wert"])]:
    if not os.path.exists(f) or os.stat(f).st_size == 0:
        pd.DataFrame(columns=cols).to_csv(f, index=False)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Setup & Marken")
    volumen = st.number_input("Beckenvolumen (L)", value=572)
    
    st.divider()
    # Dynamische Marken-Eingabe
    brand_kh = st.text_input("Name KH-Produkt", value="Oceamo Duo KH")
    brand_ca = st.text_input("Name Ca-Produkt", value="Oceamo Duo Ca")
    
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    curr_kh_ml = st.number_input(f"Aktuell {brand_kh}", value=0.0, format="%.1f")
    curr_ca_ml = st.number_input(f"Aktuell {brand_ca}", value=0.0, format="%.1f")
    
    st.divider()
    st.subheader("Produkt-Konzentration")
    kh_factor = st.number_input(f"ml {brand_kh} für +1° / 100L", value=10.0)
    ca_factor = st.number_input(f"ml {brand_ca} für +10mg / 100L", value=14.0)
    
    st.divider()
    if st.button("⚠️ Historie komplett löschen"):
        pd.DataFrame(columns=["Datum", "Wert"]).to_csv(KH_FILE, index=False)
        pd.DataFrame(columns=["Datum", "Wert"]).to_csv(CA_FILE, index=False)
        st.rerun()

st.title("🌊 AquaCalc 572L")

# --- EINGABE ---
col_in1, col_in2 = st.columns(2)

with col_in1:
    st.subheader(f"🧪 {brand_kh} Messung")
    kh_date = st.date_input("Datum KH", datetime.now(), key="d_kh")
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kh_in")
    b1, b2 = st.columns(2)
    if b1.button("💾 KH Speichern"):
        df = pd.read_csv(KH_FILE)
        new = pd.DataFrame([[kh_date, kh_val]], columns=["Datum", "Wert"])
        pd.concat([df, new]).to_csv(KH_FILE, index=False)
        st.rerun()
    if b2.button("🗑️ KH Letzten löschen"):
        df = pd.read_csv(KH_FILE)
        if not df.empty:
            df[:-1].to_csv(KH_FILE, index=False)
            st.rerun()

with col_in2:
    st.subheader(f"🧪 {brand_ca} Messung")
    ca_date = st.date_input("Datum Ca", datetime.now(), key="d_ca")
    ca_val = st.number_input("Messwert (mg/l)", step=1, key="ca_in")
    b3, b4 = st.columns(2)
    if b3.button("💾 Ca Speichern"):
        df = pd.read_csv(CA_FILE)
        new = pd.DataFrame([[ca_date, ca_val]], columns=["Datum", "Wert"])
        pd.concat([df, new]).to_csv(CA_FILE, index=False)
        st.rerun()
    if b4.button("🗑️ Ca Letzten löschen"):
        df = pd.read_csv(CA_FILE)
        if not df.empty:
            df[:-1].to_csv(CA_FILE, index=False)
            st.rerun()

# --- BERECHNUNG ---
st.divider()
cols_res = st.columns(2)

def calc_dose(file, factor, current_ml, is_ca=False):
    df = pd.read_csv(file)
    if len(df) >= 2:
        df["Datum"] = pd.to_datetime(df["Datum"])
        df = df.sort_values("Datum")
        last, prev = df.iloc[-1], df.iloc[-2]
        tage = (last["Datum"] - prev["Datum"]).days
        if tage > 0:
            verbrauch_pro_tag = (prev["Wert"] - last["Wert"]) / tage
            divisor = 10 if is_ca else 1
            extra_ml = (verbrauch_pro_tag / divisor) * (volumen / 100) * factor
            return f"{round(current_ml + extra_ml, 1)} ml", f"{round(extra_ml, 1)} ml Anpassung"
    return None, "Warte auf 2. Messung..."

kh_res, kh_hint = calc_dose(KH_FILE, kh_factor, curr_kh_ml)
ca_res, ca_hint = calc_dose(CA_FILE, ca_factor, curr_ca_ml, is_ca=True)

cols_res[0].metric(f"Dosis {brand_kh}", kh_res if kh_res else "---", kh_hint)
cols_res[1].metric(f"Dosis {brand_ca}", ca_res if ca_res else "---", ca_hint)

# --- HISTORIE ---
with st.expander("📊 Historie & Tabellen"):
    c1, c2 = st.columns(2)
    c1.write(f"Werte {brand_kh}")
    c1.dataframe(pd.read_csv(KH_FILE), use_container_width=True)
    c2.write(f"Werte {brand_ca}")
    c2.dataframe(pd.read_csv(CA_FILE), use_container_width=True)