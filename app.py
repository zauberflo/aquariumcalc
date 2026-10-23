import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

# --- LOGO LADEN (gecacht, mit Timeout) ---
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/zauberflo/aquariumcalc/main/logo.png"


@st.cache_resource
def get_logo():
    try:
        r = requests.get(GITHUB_LOGO_URL, timeout=5)
        r.raise_for_status()
        return Image.open(BytesIO(r.content))
    except Exception:
        return "🐠"


logo_img = get_logo()

# --- APP KONFIGURATION ---
st.set_page_config(page_title="AquaCalc Cloud 572", page_icon=logo_img, layout="wide")

# --- VERBINDUNG ZU GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16YwX5iHpHM-yaSPV8KI9ds_FbPPdggaTvzrDZJevNMI/edit"

# Maximale Einmalgabe pro Tag (Sicherheitslimit für Fische/Korallen)
MAX_STEP_KH = 1.0    # dKH
MAX_STEP_CA = 30.0   # mg/l


def load_data(sheet_name):
    """Liefert (DataFrame, ok). Bei Fehler ok=False -> Speichern wird blockiert."""
    try:
        data = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=30)
        return data.dropna(how="all"), True
    except Exception as e:
        st.warning(f"⚠️ Konnte Sheet '{sheet_name}' nicht laden: {e}")
        return pd.DataFrame(), False


def save_sheet(sheet_name, data, load_ok):
    """Schreibt nur, wenn das Sheet vorher sauber geladen wurde (kein Überschreiben mit leeren Daten)."""
    if not load_ok:
        st.error(f"❌ Speichern blockiert: Sheet '{sheet_name}' wurde nicht korrekt geladen. "
                 f"Seite neu laden und erneut versuchen.")
        st.stop()
    conn.update(spreadsheet=SHEET_URL, worksheet=sheet_name, data=data)
    st.cache_data.clear()


def parse_number(val):
    """Zahl robust parsen: '1.234,5' -> 1234.5, '7.5' -> 7.5, '7,5' -> 7.5"""
    if isinstance(val, str):
        s = val.strip()
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        return float(s)
    return float(val)


# --- SETUP DATEN LADEN & ROBUST PARSEN ---
df_setup, setup_ok = load_data("Setup")

SETUP_KEYS = ["Volumen", "KH_Brand", "CA_Brand", "KH_Dosis", "CA_Dosis",
              "KH_Faktor", "CA_Faktor", "KH_Verbrauch", "CA_Verbrauch"]

setup_values = {
    "Volumen": 572.0, "KH_Brand": "Oceamo Duo KH", "CA_Brand": "Oceamo Duo Ca",
    "KH_Dosis": 12.0, "CA_Dosis": 15.0, "KH_Faktor": 10.0, "CA_Faktor": 14.0,
    "KH_Verbrauch": 0.0, "CA_Verbrauch": 0.0,
}

if not df_setup.empty and "Parameter" in df_setup.columns and "Wert" in df_setup.columns:
    for _, row in df_setup.iterrows():
        p = str(row["Parameter"]).strip()
        val = row["Wert"]
        if p in setup_values:
            if p in ("KH_Brand", "CA_Brand"):
                setup_values[p] = str(val)
            else:
                try:
                    setup_values[p] = parse_number(val)
                except (ValueError, TypeError):
                    pass  # Default behalten

s_vol = float(setup_values["Volumen"])
s_brand_kh = str(setup_values["KH_Brand"])
s_brand_ca = str(setup_values["CA_Brand"])
s_kh_d = float(setup_values["KH_Dosis"])
s_ca_d = float(setup_values["CA_Dosis"])
s_kh_f = float(setup_values["KH_Faktor"])
s_ca_f = float(setup_values["CA_Faktor"])


def build_setup_df(vol, brand_kh, brand_ca, kh_d, ca_d, kh_f, ca_f, kh_v, ca_v):
    return pd.DataFrame({
        "Parameter": SETUP_KEYS,
        "Wert": [vol, brand_kh, brand_ca, kh_d, ca_d, kh_f, ca_f, kh_v, ca_v],
    })


# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("⚙️ Aquarium Setup")
    s_vol = st.number_input("Beckenvolumen (Netto L)", value=s_vol, min_value=1.0)

    st.divider()
    s_brand_kh = st.text_input("Marke KH-Lösung", value=s_brand_kh)
    s_brand_ca = st.text_input("Marke Ca-Lösung", value=s_brand_ca)

    st.divider()
    st.subheader("Aktuelle Dosierung (ml/Tag)")
    s_kh_d = st.number_input(f"Dosis {s_brand_kh}", value=s_kh_d, min_value=0.0, format="%.1f")
    s_ca_d = st.number_input(f"Dosis {s_brand_ca}", value=s_ca_d, min_value=0.0, format="%.1f")

    st.divider()
    st.subheader("Produkt-Parameter")
    s_kh_f = st.number_input(f"ml {s_brand_kh} für +1° dKH / 100L", value=s_kh_f, min_value=0.1)
    s_ca_f = st.number_input(f"ml {s_brand_ca} für +10mg Ca / 100L", value=s_ca_f, min_value=0.1)

    st.divider()
    st.subheader("🎯 Wunschwerte")
    target_kh = st.number_input("Wunsch-KH", value=7.5, step=0.1, format="%.1f")
    target_ca = st.number_input("Wunsch-Calcium", value=420.0, step=5.0, format="%.0f")

    if st.button("💾 Setup manuell speichern"):
        new_setup = build_setup_df(s_vol, s_brand_kh, s_brand_ca, s_kh_d, s_ca_d, s_kh_f, s_ca_f,
                                   setup_values["KH_Verbrauch"], setup_values["CA_Verbrauch"])
        save_sheet("Setup", new_setup, setup_ok)
        st.success("Setup gespeichert!")
        st.rerun()

# --- ROBUSTE DATENBEREINIGUNG ---
raw_kh, kh_ok = load_data("KH")
raw_ca, ca_ok = load_data("CA")

COLS = ["Datum", "Wert", "Zugabe", "IntervallDosis"]


def to_float_german(series):
    if series.dtype == object or pd.api.types.is_string_dtype(series):
        s = series.astype(str).str.strip()
        has_comma = s.str.contains(",", regex=False)
        s = s.where(~has_comma, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
        return pd.to_numeric(s, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def clean_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=COLS)

    d = df.copy()
    d.columns = [str(c).strip() for c in d.columns]

    if "DataFrame" in d.columns:  # Altlast: falsch benannte Spalte
        d.rename(columns={"DataFrame": "Datum"}, inplace=True)

    if "Datum" not in d.columns:
        d["Datum"] = str(datetime.now().date())
    for c in ("Wert", "Zugabe", "IntervallDosis"):
        if c not in d.columns:
            d[c] = None

    date_col = d["Datum"].astype(str).str.strip()
    parsed = pd.to_datetime(date_col, format="%d.%m.%Y", errors="coerce")
    mask_nat = parsed.isna()
    if mask_nat.any():
        parsed[mask_nat] = pd.to_datetime(date_col[mask_nat], format="%Y-%m-%d", errors="coerce")
    d["Datum"] = parsed.dt.strftime("%Y-%m-%d").fillna(date_col)

    d["Wert"] = to_float_german(d["Wert"])
    d["Zugabe"] = to_float_german(d["Zugabe"]).fillna(0.0)
    d["IntervallDosis"] = to_float_german(d["IntervallDosis"]).fillna(0.0)

    return d[COLS].reset_index(drop=True)


df_kh = clean_dataframe(raw_kh)
df_ca = clean_dataframe(raw_ca)

st.title("🌊 Zauberflos AquaCalc Cloud")

# --- MESSWERTE EINGEBEN ---
today_str = str(datetime.now().date())


def add_entry(df, wert, extra, dosis, only_extra):
    """Fügt Eintrag hinzu. Pro Tag max. ein Messwert: vorhandene Messung wird aktualisiert."""
    df = df.copy()
    today_rows = df.index[df["Datum"] == today_str]

    if only_extra:
        if len(today_rows) > 0:
            idx = today_rows[0]  # nur EINER Zeile zuschlagen (nicht allen von heute)
            df.loc[idx, "Zugabe"] = float(df.loc[idx, "Zugabe"]) + float(extra)
            return df
        new_row = {"Datum": today_str, "Wert": None, "Zugabe": float(extra), "IntervallDosis": float(dosis)}
        return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    meas_rows = df.index[(df["Datum"] == today_str) & df["Wert"].notna()]
    if len(meas_rows) > 0:
        idx = meas_rows[0]  # heutige Messung überschreiben statt Duplikat
        df.loc[idx, "Wert"] = float(wert)
        df.loc[idx, "Zugabe"] = float(df.loc[idx, "Zugabe"]) + float(extra)
        df.loc[idx, "IntervallDosis"] = float(dosis)
        return df
    new_row = {"Datum": today_str, "Wert": float(wert), "Zugabe": float(extra), "IntervallDosis": float(dosis)}
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)


c_in1, c_in2 = st.columns(2)

with c_in1:
    st.subheader(f"🧪 {s_brand_kh} Messung & Zugabe")
    only_extra_kh = st.checkbox("Nur manuelle Extra-Zugabe buchen (ohne neuen Messwert)", key="only_k")
    kh_val = st.number_input("Messwert (dKH)", format="%.2f", key="kin", disabled=only_extra_kh, value=7.5)
    kh_extra = st.number_input("Manuelle Extra-Zugabe JETZT (ml)", value=0.0, min_value=0.0, step=1.0, key="k_extra")

    if st.button("💾 KH Speichern"):
        new_kh = add_entry(df_kh, kh_val, kh_extra, s_kh_d, only_extra_kh)
        save_sheet("KH", new_kh, kh_ok)
        st.success("KH-Eintrag erfolgreich gespeichert!")
        st.rerun()

with c_in2:
    st.subheader(f"🧪 {s_brand_ca} Messung & Zugabe")
    only_extra_ca = st.checkbox("Nur manuelle Extra-Zugabe buchen (ohne neuen Messwert)", key="only_c")
    ca_val = st.number_input("Messwert (mg/l)", step=1.0, format="%.0f", key="cin", disabled=only_extra_ca, value=420.0)
    ca_extra = st.number_input("Manuelle Extra-Zugabe JETZT (ml)", value=0.0, min_value=0.0, step=5.0, key="c_extra")

    if st.button("💾 Ca Speichern"):
        new_ca = add_entry(df_ca, ca_val, ca_extra, s_ca_d, only_extra_ca)
        save_sheet("CA", new_ca, ca_ok)
        st.success("Ca-Eintrag erfolgreich gespeichert!")
        st.rerun()

# --- BERECHNUNGSLOGIK ---
st.divider()
st.header("⏱️ Aktuelle Entwicklung (Letzte 2 Messpunkte)")
res1, res2 = st.columns(2)


def calculate_aquarium(df, current_setup_dosis, vol, factor, target_val, is_ca=False):
    """
    Bilanz zwischen den letzten zwei Messungen (Start S am Tag d_prev, Ende L am Tag d_last):

        Änderung (L - S) = (Pumpe + Extra) / Umrechnung - Verbrauch
        => Verbrauch (ml) = Pumpe + Extra - (L - S) * Umrechnung
        => neue Tagesdosis = Verbrauch / Tage   (hält den Wert konstant)

    Umrechnung: ml pro 1 Einheit (1 dKH bzw. 1 mg/l) im ganzen Becken
      KH: factor = ml für +1 dKH / 100 L
      Ca: factor = ml für +10 mg/l / 100 L  -> pro 1 mg/l = factor / 10
    """
    temp_df = df.copy()
    temp_df["Datum_dt"] = pd.to_datetime(temp_df["Datum"].astype(str).str.strip(),
                                         format="%Y-%m-%d", errors="coerce")
    df_m = temp_df.dropna(subset=["Wert", "Datum_dt"]).sort_values("Datum_dt").reset_index(drop=True)

    if len(df_m) < 2 or vol <= 0:
        return None

    prev_row = df_m.iloc[-2]
    last_row = df_m.iloc[-1]
    d_prev, d_last = prev_row["Datum_dt"], last_row["Datum_dt"]
    tage = (d_last - d_prev).days
    if tage <= 0:
        return None

    f_konz = factor / 10.0 if is_ca else factor      # ml pro 1 Einheit / 100 L
    ml_pro_einheit = (vol / 100.0) * f_konz           # ml pro 1 Einheit im ganzen Becken

    # 1. Extra-Zugaben im Intervall: ab Starttag (nach der Startmessung) bis VOR dem Endtag
    #    (Zugaben am Endtag erfolgen nach der Endmessung und zählen erst für das nächste Intervall)
    mask_intervall = (temp_df["Datum_dt"] >= d_prev) & (temp_df["Datum_dt"] < d_last)
    ml_extra = float(temp_df.loc[mask_intervall, "Zugabe"].sum())
    extra_einheiten = ml_extra / ml_pro_einheit
    effektiver_startwert = float(prev_row["Wert"]) + extra_einheiten

    # 2. Pumpenmenge: historische Dosis des Startpunkts, sonst aktuelle Setup-Dosis
    dosis_intervall = float(prev_row["IntervallDosis"]) if pd.notna(prev_row["IntervallDosis"]) else 0.0
    if dosis_intervall <= 0:
        dosis_intervall = float(current_setup_dosis)
    pumpe_gesamt_ml = dosis_intervall * tage

    # 3. Verbrauch: alles was reinkam minus die tatsächliche Wertänderung
    aenderung = float(last_row["Wert"]) - float(prev_row["Wert"])
    verbrauch_ml = pumpe_gesamt_ml + ml_extra - aenderung * ml_pro_einheit

    # 4. Neue Tagesdosis (nie negativ)
    d_neu = max(0.0, round(verbrauch_ml / tage, 1))
    delta = round(d_neu - float(current_setup_dosis), 1)

    # 5. Einmalgabe bis Wunschwert, begrenzt auf Sicherheitslimit
    fehlend = target_val - float(last_row["Wert"])
    max_schritt = MAX_STEP_CA if is_ca else MAX_STEP_KH
    begrenzt = False
    if fehlend > 0:
        if fehlend > max_schritt:
            fehlend = max_schritt
            begrenzt = True
        up = round(fehlend * ml_pro_einheit, 1)
    else:
        up = 0.0

    return {
        "d_neu": d_neu, "delta": delta, "up": up, "begrenzt": begrenzt, "max_schritt": max_schritt,
        "start_eff": round(effektiver_startwert, 2), "last": float(last_row["Wert"]),
        "d_prev": prev_row["Datum"], "d_last": last_row["Datum"],
        "tage": tage, "verbrauch_tag": round(verbrauch_ml / tage, 1),
    }


def render_result(col, r, brand, unit, target, current_dose, key):
    if r is None:
        col.metric(f"Aktuelle Dosierung {brand}", f"{current_dose} ml", "Warte auf mind. 2 Messpunkte…")
        return False

    col.metric(f"Neue Tagesdosis {brand} (Wert halten)", f"{r['d_neu']} ml", f"{r['delta']} ml vs. bisher")
    col.info(f"💡 **Basis:** Start bei **{r['d_prev']}** (effektiv **{r['start_eff']} {unit}** nach Zugabe) "
             f"bis **{r['d_last']}** (Endwert: **{r['last']} {unit}**, {r['tage']} Tage). "
             f"Verbrauch ca. **{r['verbrauch_tag']} ml/Tag**.")
    if r["up"] > 0:
        txt = (f"🔺 **Empfohlene Einzelerhöhung:** Dosiere einmalig **{r['up']} ml** extra, "
               f"um Richtung Wunschwert ({target} {unit}) zu kommen.")
        if r["begrenzt"]:
            txt += (f" Aus Sicherheitsgründen auf max. +{r['max_schritt']:g} {unit} pro Tag begrenzt, "
                    f"den Rest auf mehrere Tage verteilen.")
        col.warning(txt)
    else:
        col.success("🎯 Wunschwert erreicht oder überschritten – kein zusätzlicher Einzelschub nötig!")
    return col.button(f"✅ Neue Tagesdosis für {key} dauerhaft aktivieren")


# --- AUSGABE KH ---
r_kh = calculate_aquarium(df_kh, s_kh_d, s_vol, s_kh_f, target_kh, is_ca=False)
if render_result(res1, r_kh, s_brand_kh, "dKH", target_kh, s_kh_d, "KH"):
    new_setup_kh = build_setup_df(s_vol, s_brand_kh, s_brand_ca, r_kh["d_neu"], s_ca_d, s_kh_f, s_ca_f,
                                  r_kh["verbrauch_tag"], setup_values["CA_Verbrauch"])
    save_sheet("Setup", new_setup_kh, setup_ok)
    st.success(f"Dosis von {r_kh['d_neu']} ml erfolgreich im Setup gespeichert!")
    st.rerun()

# --- AUSGABE CA ---
r_ca = calculate_aquarium(df_ca, s_ca_d, s_vol, s_ca_f, target_ca, is_ca=True)
if render_result(res2, r_ca, s_brand_ca, "mg/l", target_ca, s_ca_d, "Ca"):
    new_setup_ca = build_setup_df(s_vol, s_brand_kh, s_brand_ca, s_kh_d, r_ca["d_neu"], s_kh_f, s_ca_f,
                                  setup_values["KH_Verbrauch"], r_ca["verbrauch_tag"])
    save_sheet("Setup", new_setup_ca, setup_ok)  # Setup-Sheet, NICHT das CA-Messwerte-Sheet
    st.success(f"Dosis von {r_ca['d_neu']} ml erfolgreich im Setup gespeichert!")
    st.rerun()

# --- HISTORIE & LÖSCHEN ---
st.divider()


def history_block(col, df, brand, sheet, ok, key):
    with col:
        st.subheader(f"{brand} Verlauf & Editor")
        if df.empty:
            st.caption("Noch keine Einträge.")
            return
        plot = df.copy()
        plot["Datum_dt"] = pd.to_datetime(plot["Datum"], errors="coerce")
        plot = plot.dropna(subset=["Wert", "Datum_dt"])
        if not plot.empty:
            st.line_chart(plot.set_index("Datum_dt")["Wert"])
        st.dataframe(df, use_container_width=True)

        st.markdown("🗑️ **Eintrag löschen**")

        def label(i):
            r = df.loc[i]
            w = "—" if pd.isna(r["Wert"]) else f"{r['Wert']:g}"
            return f"{r['Datum']} | Wert: {w} | Zugabe: {r['Zugabe']:g} ml"

        sel = st.selectbox("Eintrag auswählen:", options=list(df.index), format_func=label, key=f"del_{key}_sel")
        if st.button(f"❌ Ausgewählten {key}-Eintrag löschen", type="secondary", key=f"del_{key}_btn"):
            new_df = df.drop(index=sel).reset_index(drop=True)
            save_sheet(sheet, new_df, ok)
            st.success("Eintrag wurde gelöscht!")
            st.rerun()


with st.expander("📊 Historie & Verlauf", expanded=True):
    h1, h2 = st.columns(2)
    history_block(h1, df_kh, s_brand_kh, "KH", kh_ok, "KH")
    history_block(h2, df_ca, s_brand_ca, "CA", ca_ok, "Ca")
