def calculate_aquarium_strict_vB(df, current_setup_dosis, vol, factor, target_val, is_ca=False):
    df_measured = df.dropna(subset=["Wert"]).copy()
    
    if df_measured is not None and len(df_measured) >= 2:
        df_measured["Datum"] = pd.to_datetime(df_measured["Datum"], errors='coerce')
        df_measured = df_measured.dropna(subset=["Datum"]).sort_values("Datum")
        
        last = df_measured.iloc[-1]   
        prev = df_measured.iloc[-2]   
        tage = (last["Datum"] - prev["Datum"]).days
        
        if tage > 0:
            f_konz = factor / 10 if is_ca else factor
            becken_diff = prev["Wert"] - last["Wert"]
            becken_diff_pro_tag = becken_diff / tage
            
            historische_dosis = prev["IntervallDosis"] if prev["IntervallDosis"] > 0 else current_setup_dosis
            dosis_wirkung_pro_tag = historische_dosis / (vol / 100) / f_konz
            
            sub_df = df[(df["Datum"] >= str(prev["Datum"].date())) & (df["Datum"] < str(last["Datum"].date()))]
            total_extra = sub_df["Zugabe"].sum()
            zugabe_wirkung_pro_tag = (total_extra / (vol / 100) / f_konz) / tage
            
            # --- DIE NEUE BERUHIGUNGS-LOGIK ---
            # Toleranz: KH 0.1 dKH / Ca 5.0 mg/l
            toleranz = 0.1 if not is_ca else 5.0
            
            if abs(becken_diff) <= toleranz:
                # Wert ist stabil -> kein Eingriff nötig
                v_real = dosis_wirkung_pro_tag
            else:
                # Wirkliche Abweichung gefunden -> korrigieren
                v_real = becken_diff_pro_tag + dosis_wirkung_pro_tag + zugabe_wirkung_pro_tag
            
            # --- ENDE BERUHIGUNGS-LOGIK ---
            
            d_neu = round(v_real * (vol / 100) * f_konz, 1)
            delta_ml = round(d_neu - current_setup_dosis, 1)
            diff_to_target = target_val - last["Wert"]
            einmalig_ml = round(diff_to_target * (vol / 100) * f_konz, 1) if diff_to_target > 0 else 0.0
            
            return round(v_real, 3), d_neu, delta_ml, einmalig_ml, last["Wert"]
            
    return None, None, None, None, None
