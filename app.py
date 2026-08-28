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

# --- SETUP DATEN LADEN & ROBUST PARSEN ---
df_setup = load_data("Setup")

setup_values = {
    "Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca",
    "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0,
    "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0
}

if not df_setup.empty and "Parameter" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        val = row["Wert"]
        if p in setup_values:
            if p in ["KH_Brand", "CA_Brand"]:
                setup_values[p] = str(val)
            else:
                try:
                    if isinstance(val, str):
                        val = val.replace('.', '').replace(',', '.')
                    setup_values[p] = float(val)
                except:
                    setup_values[p] = val

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

# --- ROBUSTE DATENBEREINIGUNG (DATUM & KOMMAS) ---
raw_kh = load_data("KH")
raw_ca = load_data("CA")

def clean_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Datum", "Wert", "Zugabe", "IntervallDosis"])
    
    d = df.copy()
    d.columns = [str(c).strip() for c in d.columns]
    
    if "DataFrame" in d.columns:
        d.rename(columns={"DataFrame": "Datum"}, inplace=True)
        
    if "Datum" not in d.columns: 
        d["Datum"] = str(datetime.now().date())
    
    date_col = d["Datum"].astype(str).str.strip()
    parsed_dates = pd.to_datetime(date_col, format='%d.%m.%Y', errors='coerce')
    mask_nat = parsed_dates.isna()
    if mask_nat.any():
        parsed_dates[mask_nat] = pd.to_datetime(date_col[mask_nat], errors='coerce')
        
    d["Datum"] = parsed_dates.dt.strftime('%Y-%m-%d')
    d["Datum"] = d["Datum"].fillna(date_col)
    
    def to_float_german(series):
        if series.dtype == object or pd.api.types.is_string_dtype(series):
            return pd.to_numeric(series.astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')
        return pd.to_numeric(series, errors='coerce')

    d["Wert"] = to_float_german(d["Wert"])
    d["Zugabe"] = to_float_german(d["Zugabe"]).fillna(0.0)
    
    if "IntervallDosis" not in d.columns:
        d["IntervallDosis"] = 0.0
    d["IntervallDosis"] = to_float_german(d["IntervallDosis"]).fillna(0.0)
    
    return d[["Datum", "Wert", "Zugabe", "IntervallDosis"]].reset_index(drop=True)

df_kh = clean_dataframe(raw_kh)
df_ca = clean_dataframe(raw_ca)

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- MESSWERTE EINGEBEN ---
c_in1, c_in2 = st.columns(2)
today_str = str(datetime.now().date())

with c_in1:
    st.subheader(f"🧪 {s_brand_kh} Messung & Zugabe")
    only_extra_kh = st.checkbox("Nur manuelle Extra-Zugabe buchen (ohne neuen Messwert)", key="only_k")
    
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kin", disabled=only_extra_kh, value=7.5)
    kh_extra = st.number_input("Manuelle Extra-Zugabe JETZT (ml)", value=0.0, step=1.0, key="k_extra")
    
    if st.button("💾 KH Speichern"):
        if only_extra_kh:
            mask = df_kh["Datum"] == today_str
            if mask.any():
                df_kh.loc[mask, "Zugabe"] += float(kh_extra)
                new_kh = df_kh
            else:
                new_kh = pd.concat([df_kh, pd.DataFrame([{"Datum": today_str, "Wert": None, "Zugabe": float(kh_extra), "IntervallDosis": float(s_kh_d)}])], ignore_index=True)
        else:
            new_kh = pd.concat([df_kh, pd.DataFrame([{"Datum": today_str, "Wert": float(kh_val), "Zugabe": float(kh_extra), "IntervallDosis": float(s_kh_d)}])], ignore_index=True)
        
        conn.update(spreadsheet=SHEET_URL, worksheet="KH", data=new_kh)
        st.cache_data.clear()
        st.success("KH-Eintrag erfolgreich gespeichert!")
        st.rerun()

with c_in2:
    st.subheader(f"🧪 {s_brand_ca} Messung & Zugabe")
    only_extra_ca = st.checkbox("Nur manuelle Extra-Zugabe buchen (ohne neuen Messwert)", key="only_c")
    
    ca_val = st.number_input("Messwert (mg/l)", step=1, key="cin", disabled=only_extra_ca, value=420)
    ca_extra = st.number_input("Manuelle Extra-Zugabe JETZT (ml)", value=0.0, step=5.0, key="c_extra")
    
    if st.button("💾 Ca Speichern"):
        if only_extra_ca:
            mask = df_ca["Datum"] == today_str
            if mask.any():
                df_ca.loc[mask, "Zugabe"] += float(ca_extra)
                new_ca = df_ca
            else:
                new_ca = pd.concat([df_ca, pd.DataFrame([{"Datum": today_str, "Wert": None, "Zugabe": float(ca_extra), "IntervallDosis": float(s_ca_d)}])], ignore_index=True)
        else:
            new_ca = pd.concat([df_ca, pd.DataFrame([{"Datum": today_str, "Wert": float(ca_val), "Zugabe": float(ca_extra), "IntervallDosis": float(s_ca_d)}])], ignore_index=True)
        
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=new_ca)
        st.cache_data.clear()
        st.success("Ca-Eintrag erfolgreich gespeichert!")
        st.rerun()

# --- MATHEMATISCH KORREKTE BERECHNUNG (LETZTE 2 MESSWERTE + KORREKTE ZWISCHENZUGABEN) ---
st.divider()
st.header("⏱️ Aktuelle Entwicklung (Letzten 2 Messpunkte)")
res1, res2 = st.columns(2)

def calculate_aquarium_strict_last_two(df, current_setup_dosis, vol, factor, target_val, is_ca=False):
    temp_df = df.copy()
    
    date_col = temp_df["Datum"].astype(str).str.strip()
    parsed_dates = pd.to_datetime(date_col, format='%Y-%m-%d', errors='coerce')
    mask_nat = parsed_dates.isna()
    if mask_nat.any():
        parsed_dates[mask_nat] = pd.to_datetime(date_col[mask_nat], format='%d.%m.%Y', errors='coerce')
    temp_df["Datum_dt"] = parsed_dates
    
    # 1. Nur Zeilen mit echtem Messwert für die letzten 2 Punkte
    df_m = temp_df.dropna(subset=["Wert", "Datum_dt"]).copy()
    df_m = df_m.sort_values("Datum_dt").reset_index(drop=True)
    
    if len(df_m) >= 2:
        prev_row = df_m.iloc[-2]
        last_row = df_m.iloc[-1]
        
        d_prev = prev_row["Datum_dt"]
        d_last = last_row["Datum_dt"]
        
        tage = (d_last - d_prev).days
        
        if tage > 0:
            f_konz = factor / 10.0 if is_ca else factor
            
            # 1. Was bewirkt die automatische Setup-Dosis pro Tag in Einheiten (dKH / mg/l)?
            dosis_effekt_pro_tag = current_setup_dosis / (vol / 100.0) / f_konz
            
            # 2. Summe aller manuellen Extra-Zugaben (in ml) im exakten Zeitraum zwischen den Messungen
            mask_intervall = (temp_df["Datum_dt"] > d_prev) & (temp_df["Datum_dt"] <= d_last)
            zugabe_ml_im_intervall = temp_df.loc[mask_intervall, "Zugabe"].sum()
            
            # Umrechnung der Extra-ml in Einheiten (dKH / mg/l)
            zugabe_in_einheiten = zugabe_ml_im_intervall / (vol / 100.0) / f_konz
            
            # 3. Netto-Abfall durch Verbrauch berechnen:
            # Startpunkt + Automatische Zufuhr + Manuelle Zufuhr = Was theoretisch da sein MÜSSTE ohne Verbrauch
            theoretischer_startwert = prev_row["Wert"] + (dosis_effekt_pro_tag * tage) + zugabe_in_einheiten
            
            # Der tatsächliche Verbrauch (Verlust) im Zeitraum
            gesamt_verlust = theoretischer_startwert - last_row["Wert"]
            
            # Verbrauch pro Tag insgesamt
            v_real = gesamt_verlust / tage
            
            if v_real < 0:
                v_real = 0.0  # Falls Wert gestiegen ist, kein negativer Verbrauch
                
            # Neue empfohlene Tagesdosis in ml
            d_neu = round(v_real * (vol / 100.0) * f_konz, 1)
            delta = round(d_neu - current_setup_dosis, 1)
            up = round((target_val - last_row["Wert"]) * (vol / 100.0) * f_konz, 1)
            
            return round(v_real, 3), d_neu, delta, up, last_row["Wert"], prev_row["Datum"], last_row["Datum"]
            
    return None, None, None, None, None, None, None

# --- AUSGABE KH ---
v_kh, d_kh, delta_kh, up_kh, last_kh, d_prev_kh, d_last_kh = calculate_aquarium_strict_last_two(df_kh, s_kh_d, s_vol, s_kh_f, target_kh, is_ca=False)
if v_kh is not None:
    res1.metric(f"Neue Tagesdosis {s_brand_kh} (Wert halten)", f"{d_kh} ml", f"{delta_kh} ml vs. bisher")
    res1.info(f"💡 **Vergleich:** Von **{d_prev_kh}** bis **{d_last_kh}** (exakt die letzten 2 Messungen).")
    res1.write(f"📉 Realer Gesamtverbrauch: **{v_kh} dKH/Tag**")
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
    res1.metric(f"Aktuelle Dosierung {s_brand_kh}", f"{s_kh_d} ml", "Warte auf mind. 2 Messpunkte...")

# --- AUSGABE CA ---
v_ca, d_ca, delta_ca, up_ca, last_ca, d_prev_ca, d_last_ca = calculate_aquarium_strict_last_two(df_ca, s_ca_d, s_vol, s_ca_f, target_ca, is_ca=True)
if v_ca is not None:
    res2.metric(f"Neue Tagesdosis {s_brand_ca} (Wert halten)", f"{d_ca} ml", f"{delta_ca} ml vs. bisher")
    res2.info(f"💡 **Vergleich:** Von **{d_prev_ca}** bis **{d_last_ca}** (exakt die letzten 2 Messungen).")
    res2.write(f"📉 Realer Gesamtverbrauch: **{v_ca} mg/l/Tag**")
    if up_ca > 0:
        res2.warning(f"🔺 **Empfohlene Einzelerhöhung:** Dosiere einmalig **{up_ca} ml** extra für Wunschwert ({target_ca} mg/l).")
    
    if res2.button("✅ Neue Tagesdosis für Ca aktivieren"):
        new_setup_ca = pd.DataFrame({
            "Parameter": ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis", "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"],
            "Wert": [s_vol, s_brand_kh, s_brand_ca, s_kh_d, d_ca, s_kh_f, s_ca_f, setup_values["KH_Verbrauch"], v_ca]
        })
        conn.update(spreadsheet=SHEET_URL, worksheet="CA", data=new_setup_ca)
        st.cache_data.clear()
        st.success(f"Dosis von {d_ca} ml dauerhaft im Setup aktiviert!")
        st.rerun()
else:
    res2.metric(f"Aktuelle Dosierung {s_brand_ca}", f"{s_ca_d} ml", "Warte auf mind. 2 Messpunkte...")

# --- HISTORIE & LIVE-EDIT-FUNKTION ---
st.divider()
with st.expander("📊 Historie & Verlauf", expanded=True):
    h1, h2 = st.columns(2)
    
    with h1:
        st.subheader(f"{s_brand_kh} Verlauf & Editor")
        if not df_kh.empty:
            df_kh_plot = df_kh.copy()
            df_kh_plot["Datum_dt"] = pd.to_datetime(df_kh_plot["Datum"], errors='coerce')
            st.line_chart(df_kh_plot.dropna(subset=["Wert", "Datum_dt"]).set_index("Datum_dt")["Wert"])
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
            df_ca_plot = df_ca.copy()
            df_ca_plot["Datum_dt"] = pd.to_datetime(df_ca_plot["Datum"], errors='coerce')
            st.line_chart(df_ca_plot.dropna(subset=["Wert", "Datum_dt"]).set_index("Datum_dt")["Wert"])
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
