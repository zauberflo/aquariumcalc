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

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=float(setup_values["Volumen"]))
    
    st.divider()
    s_brand_kh = st.text_input("Marke KH-Lösung", value=str(setup_values["KH_Brand"]))
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=str(setup_values["CA_Brand"]))
    
    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
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

# --- DATEN LADEN & BEREINIGUNG ---
raw_kh = load_data("KH")
raw_ca = load_data("CA")

def clean_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Datum", "Wert", "Zugabe"])
    d = df.copy()
    if "DataFrame" in d.columns:
        d.rename(columns={"DataFrame": "Datum"}, inplace=True)
    if "Datum" not in d.columns: d["Datum"] = str(datetime.now().date())
    
    # Ermöglicht leere Werte für reine Zugabe-Buchungen
    d["Wert"] = pd.to_numeric(d["Wert"], errors='coerce')
    d["Zugabe"] = pd.to_numeric(d["Zugabe"], errors='coerce').fillna(0.0)
    
    # Sortieren nach Datum
    d["Datum"] = d["Datum"].astype(str)
    return d[["Datum", "Wert", "Zugabe"]].reset_index(drop=True)

df_kh = clean_dataframe(raw_kh)
df_ca = clean_dataframe(raw_ca)

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- MESSWERTE EINGEBEN ---
c_in1, c_in2 = st.columns(2)
today_str = str(datetime.now().date())

with c_in1:
    st.subheader(f"🧪 {s_brand_kh} Messung & Zugabe")
    only_extra_kh = st.checkbox("Nur manuelle Extra-Zugabe buchen (ohne neuen Messwert)", key="only_k")
    
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kin", disabled=only_extra_kh, value=7.5 if only_extra_kh else 7.5)
    kh_extra = st.number_input("Manuelle Extra-Zugabe JETZT (ml)", value=0.0, step=1.0, key="k_extra")
    
    if st.button("💾 KH Speichern"):
        if only_extra_kh:
            # Falls am selben Tag schon gemessen wurde, addieren wir die Zugabe dort dazu, ansonsten neue Zeile ohne Messwert
            mask = df_kh["Datum"] == today_str
            if mask.any():
                df_kh.loc[mask, "Zugabe"] += float(kh_extra)
                new_kh = df_kh
            else:
                new_kh = pd.concat([df_kh, pd.DataFrame([{"Datum": today_str, "Wert": None, "Zugabe": float(kh_extra)}])], ignore_index=True)
        else:
            new_kh = pd.concat([df_kh, pd.DataFrame([{"Datum": today_str, "Wert": float(kh_val), "Zugabe": float(kh_extra)}])], ignore_index=True)
        
        conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=new_kh)
        st.cache_data.clear()
        st.success("KH-Eintrag erfolgreich gespeichert!")
        st.rerun()

with c_in2:
    st.subheader(f"🧪 {s_brand_ca} Messung & Zugabe")
    only_extra_ca = st.checkbox("Nur manuelle Extra-Zugabe buchen (ohne neuen Messwert)", key="only_c")
    
    ca_val = st.number_input("Messwert (mg/l)", step=1, key="cin", disabled=only_extra_ca, value=420 if only_extra_ca else 420)
    ca_extra = st.number_input("Manuelle Extra-Zugabe JETZT (ml)", value=0.0, step=5.0, key="c_extra")
    
    if st.button("💾 Ca Speichern"):
        if only_extra_ca:
            mask = df_ca["Datum"] == today_str
            if mask.any():
                df_ca.loc[mask, "Zugabe"] += float(ca_extra)
                new_ca = df_ca
            else:
                new_ca = pd.concat([df_ca, pd.DataFrame([{"Datum": today_str, "Wert": None, "Zugabe": float(ca_extra)}])], ignore_index=True)
        else:
            new_ca = pd.concat([df_ca, pd.DataFrame([{"Datum": today_str, "Wert": float(ca_val), "Zugabe": float(ca_extra)}])], ignore_index=True)
        
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=new_ca)
        st.cache_data.clear()
        st.success("Ca-Eintrag erfolgreich gespeichert!")
        st.rerun()

# --- EXAKTE STRIKTE BERECHNUNG (Ignoriert reine Zugabezeilen am Ende bei der Verbrauchsberechnung) ---
st.divider()
st.header("⏱️ Aktuelle Entwicklung (Letzte Messung)")
res1, res2 = st.columns(2)

def calculate_aquarium_strict_vB(df, running_dosis, vol, factor, target_val, is_ca=False):
    # Filtere für die Verbrauchsberechnung nur Einträge mit echten Messwerten heraus
    df_measured = df.dropna(subset=["Wert"]).copy()
    
    if df_measured is not None and len(df_measured) >= 2:
        df_measured["Datum"] = pd.to_datetime(df_measured["Datum"], errors='coerce')
        df_measured = df_measured.dropna(subset=["Datum"]).sort_values("Datum")
        
        if len(df_measured) >= 2:
            last = df_measured.iloc[-1]   
            prev = df_measured.iloc[-2]   
            tage = (last["Datum"] - prev["Datum"]).days
            
            if tage > 0:
                f_konzentration = factor / 10 if is_ca else factor
                becken_diff_pro_tag = (prev["Wert"] - last["Wert"]) / tage
                dosis_wirkung_pro_tag = running_dosis / (vol / 100) / f_konzentration
                
                # Wir holen ALLE manuellen Zugaben, die NACH der vorletzten Messung und BIS ZUR letzten Messung getätigt wurden
                # Damit werden auch "reine Zugabe-Zeilen" dazwischen mathematisch korrekt erfasst!
                sub_df = df[(df["Datum"] >= str(prev["Datum"].date())) & (df["Datum"] < str(last["Datum"].date()))]
                total_extra_zugabe = sub_df["Zugabe"].sum()
                
                zugabe_wirkung_pro_tag = (total_extra_zugabe / (vol / 100) / f_konzentration) / tage
                
                v_real = round(becken_diff_pro_tag + dosis_wirkung_pro_tag + zugabe_wirkung_pro_tag, 3)
                d_neu = round(v_real * (vol / 100) * f_konzentration, 1)
                delta_ml = round(d_neu - running_dosis, 1)
                
                diff_to_target = target_val - last["Wert"]
                einmalig_ml = round(diff_to_target * (vol / 100) * f_konzentration, 1) if diff_to_target > 0 else 0.0
                
                return v_real, d_neu, delta_ml, einmalig_ml, last["Wert"]
                
    return None, None, None, None, None

# --- AUSGABE KH ---
v_kh, d_kh, delta_kh, up_kh, last_kh = calculate_aquarium_strict_vB(df_kh, s_kh_d, s_vol, s_kh_f, target_kh, is_ca=False)
if v_kh is not None:
    res1.metric(f"Neue Tagesdosis {s_brand_kh} (Wert halten)", f"{d_kh} ml", f"{delta_kh} ml vs. bisher")
    res1.write(f"📉 Realer Gesamtverbrauch im Intervall: **{v_kh} dKH/Tag**")
    if up_kh > 0:
        res1.warning(f"🔺 **Empfohlene Einzelerhöhung:** Dosiere einmalig **{up_kh} ml** extra für Wunschwert ({target_kh} dKH).")
    
    if res1.button("✅ Neue Tagesdosis für KH aktivieren"):
        new_setup_kh = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
            "Wert": [s_vol, s_brand_kh, s_brand_ca, d_kh, s_ca_d, s_kh_f, s_ca_f, v_kh, setup_values["CA_Verbrauch"]]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup_kh)
        st.cache_data.clear()
        st.success(f"Dosis von {d_kh} ml dauerhaft im Setup aktiviert!")
        st.rerun()
else:
    res1.metric(f"Aktuelle Dosierung {s_brand_kh}", f"{s_kh_d} ml", "Warte auf neue Messdaten...")

# --- AUSGABE CA ---
v_ca, d_ca, delta_ca, up_ca, last_ca = calculate_aquarium_strict_vB(df_ca, s_ca_d, s_vol, s_ca_f, target_ca, is_ca=True)
if v_ca is not None:
    res2.metric(f"Neue Tagesdosis {s_brand_ca} (Wert halten)", f"{d_ca} ml", f"{delta_ca} ml vs. bisher")
    res2.write(f"📉 Realer Gesamtverbrauch im Intervall: **{v_ca} mg/l/Tag**")
    if up_ca > 0:
        res2.warning(f"🔺 **Empfohlene Einzelerhöhung:** Dosiere einmalig **{up_ca} ml** extra für Wunschwert ({target_ca} mg/l).")
    
    if res2.button("✅ Neue Tagesdosis für Ca aktivieren"):
        new_setup_ca = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
            "Wert": [s_vol, s_brand_kh, s_brand_ca, s_kh_d, d_ca, s_ca_f, s_ca_f, setup_values["KH_Verbrauch"], v_ca]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="Setup", data=new_setup_ca)
        st.cache_data.clear()
        st.success(f"Dosis von {d_ca} ml dauerhaft im Setup aktiviert!")
        st.rerun()
else:
    res2.metric(f"Aktuelle Dosierung {s_brand_ca}", f"{s_ca_d} ml", "Warte auf neue Messdaten...")

# --- HISTORIE & LIVE-EDIT-FUNKTION ---
st.divider()
with st.expander("📊 Historie & Verlauf", expanded=True):
    h1, h2 = st.columns(2)
    
    with h1:
        st.subheader(f"{s_brand_kh} Verlauf & Editor")
        if not df_kh.empty:
            st.line_chart(df_kh.dropna(subset=["Wert"]).set_index("Datum")["Wert"])
            st.dataframe(df_kh, use_container_width=True)
            
            st.markdown("🗑️ **Eintrag löschen**")
            kh_dates = df_kh["Datum"].unique().tolist()
            selected_kh_date = st.selectbox("Datum auswählen zum Löschen:", options=kh_dates, key="del_kh_date")
            
            if st.button("❌ Ausgewählten KH-Eintrag löschen", type="secondary"):
                new_df_kh = df_kh[df_kh["Datum"] != selected_kh_date]
                conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=new_df_kh)
                st.cache_data.clear()
                st.success(f"Eintrag vom {selected_kh_date} wurde gelöscht!")
                st.rerun()

    with h2:
        st.subheader(f"{s_brand_ca} Verlauf & Editor")
        if not df_ca.empty:
            st.line_chart(df_ca.dropna(subset=["Wert"]).set_index("Datum")["Wert"])
            st.dataframe(df_ca, use_container_width=True)
            
            st.markdown("🗑️ **Eintrag löschen**")
            ca_dates = df_ca["Datum"].unique().tolist()
            selected_ca_date = st.selectbox("Datum auswählen zum Löschen:", options=ca_dates, key="del_ca_date")
            
            if st.button("❌ Ausgewählten Ca-Eintrag löschen", type="secondary"):
                new_df_ca = df_ca[df_ca["Datum"] != selected_ca_date]
                conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=new_df_ca)
                st.cache_data.clear()
                st.success(f"Eintrag vom {selected_ca_date} wurde gelöscht!")
                st.rerun()
