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

s_vol = float(setup_values["Volumen"])
s_brand_kh = str(setup_values["KH_Brand"])
s_brand_ca = str(setup_values["CA_Brand"])
s_kh_d = float(setup_values["KH_Dosis"])
s_ca_d = float(setup_values["CA_Dosis"])
s_kh_f = float(setup_values["KH_Faktor"])
s_ca_f = float(setup_values["CA_Faktor"])

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=s_vol)
    st.divider()
    s_brand_kh = st.text_input("Marke KH-Lösung", value=s_brand_kh)
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=s_brand_ca)
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    s_kh_d = st.number_input(f"Dosis {s_brand_kh}", value=s_kh_d, format="%.1f")
    s_ca_d = st.number_input(f"Dosis {s_brand_ca}", value=s_ca_d, format="%.1f")
    st.divider()
    st.subheader("Produkt-Parameter")
    s_kh_f = st.number_input(f"ml {s_brand_kh} für +1° dKH / 100L", value=s_kh_f)
    s_ca_f = st.number_input(f"ml {s_brand_ca} für +10mg Ca / 100L", value=s_ca_f)
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

# --- DATEN BEREINIGEN ---
def clean_dataframe(df):
    if df is None or df.empty: return pd.DataFrame(columns=["Datum", "Wert", "Zugabe", "IntervallDosis"])
    d = df.copy()
    if "DataFrame" in d.columns: d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    if "Datum" not in d.columns: d["Datum"] = str(datetime.now().date())
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    if "IntervallDosis" not in d.columns: d["IntervallDosis"] = 0.0
    d["IntervallDosis"] = pd.to_numeric(d["IntervallDosis"], errors='coerce').fillna(0.0)
    d["Datum"] = d["Datum"].astype(str)
    return d[["Datum", "Wert", "Zugabe", "IntervallDosis"]].reset_index(drop=True)

df_kh = clean_dataframe(load_data("KH"))
df_ca = clean_dataframe(load_data("CA"))

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- MESSWERTE EINGEBEN ---
c_in1, c_in2 = st.columns(2)
today_str = str(datetime.now().date())

with c_in1:
    st.subheader(f"🧪 {s_brand_kh} Messung & Zugabe")
    only_extra_kh = st.checkbox("Nur manuelle Extra-Zugabe buchen", key="only_k")
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kin", disabled=only_extra_kh, value=7.5)
    kh_extra = st.number_input("Manuelle Extra-Zugabe JETZT (ml)", value=0.0, step=1.0, key="k_extra")
    if st.button("💾 KH Speichern"):
        new_kh = pd.concat([df_kh, pd.DataFrame([{"Datum": today_str, "Wert": None if only_extra_kh else float(kh_val), "Zugabe": float(kh_extra), "IntervallDosis": float(s_kh_d)}])], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=new_kh)
        st.cache_data.clear(); st.rerun()

with c_in2:
    st.subheader(f"🧪 {s_brand_ca} Messung & Zugabe")
    only_extra_ca = st.checkbox("Nur manuelle Extra-Zugabe buchen", key="only_c")
    ca_val = st.number_input("Messwert (mg/l)", step=1, key="cin", disabled=only_extra_ca, value=420)
    ca_extra = st.number_input("Manuelle Extra-Zugabe JETZT (ml)", value=0.0, step=5.0, key="c_extra")
    if st.button("💾 Ca Speichern"):
        new_ca = pd.concat([df_ca, pd.DataFrame([{"Datum": today_str, "Wert": None if only_extra_ca else float(ca_val), "Zugabe": float(ca_extra), "IntervallDosis": float(s_ca_d)}])], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=new_ca)
        st.cache_data.clear(); st.rerun()

# --- BERECHNUNGSFUNKTION ---
def calculate_aquarium_strict_vB(df, current_setup_dosis, vol, factor, target_val, is_ca=False):
    df_measured = df.dropna(subset=["Wert"]).sort_values("Datum")
    if len(df_measured) >= 2:
        last, prev = df_measured.iloc[-1], df_measured.iloc[-2]
        tage = (pd.to_datetime(last["Datum"]) - pd.to_datetime(prev["Datum"])).days
        if tage > 0:
            f_konz = factor / 10 if is_ca else factor
            v_real = ((prev["Wert"] - last["Wert"]) / tage) + ((prev["IntervallDosis"] if prev["IntervallDosis"] > 0 else current_setup_dosis) / (vol/100) / f_konz) + ((df[(df["Datum"] >= prev["Datum"]) & (df["Datum"] < last["Datum"])]["Zugabe"].sum() / (vol/100) / f_konz) / tage)
            d_neu = round(v_real * (vol/100) * f_konz, 1)
            return round(v_real, 3), d_neu, round(d_neu - current_setup_dosis, 1), round((target_val - last["Wert"]) * (vol/100) * f_konz, 1)
    return None, None, None, None

# --- BERECHNUNG & AKTIVIERUNG ---
st.divider()
res1, res2 = st.columns(2)

for res, df, s_d, brand, factor, target, is_ca, name in [(res1, df_kh, s_kh_d, s_brand_kh, s_kh_f, target_kh, False, "KH"), (res2, df_ca, s_ca_d, s_brand_ca, s_ca_f, target_ca, True, "CA")]:
    v, d, delta, up = calculate_aquarium_strict_vB(df, s_d, s_vol, factor, target, is_ca)
    if v:
        res.metric(f"Neue Tagesdosis {brand}", f"{d} ml", f"{delta} ml vs. bisher")
        if res.button(f"✅ Neue Tagesdosis für {name} aktivieren"):
            # Update Setup
            new_setup = pd.DataFrame({"Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"], "Wert": [s_vol, s_brand_kh, s_brand_ca, d if name=="KH" else s_kh_d, d if name=="CA" else s_ca_d, s_kh_f, s_ca_f, v if name=="KH" else setup_values["KH_Verbrauch"], v if name=="CA" else setup_values["CA_Verbrauch"]]})
            conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup)
            # Update Sheet History (Der entscheidende Fix)
            data_fresh = load_data(name)
            data_fresh.at[data_fresh.index[-1], "IntervallDosis"] = d
            conn.update(spreadsheet=SHEET_URL, worksheet=name, data=data_fresh)
            st.rerun()
    else: res.metric(f"Aktuelle Dosis {brand}", f"{s_d} ml", "Warte auf Messdaten...")

# --- HISTORIE ---
with st.expander("📊 Historie"):
    h1, h2 = st.columns(2)
    h1.dataframe(df_kh); h2.dataframe(df_ca)
