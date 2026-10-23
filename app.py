    bar_boniert = st.number_input("bar kassiert bereits bonierte (€)", key="inp_bar_boniert", step=10.0)
with col2:
    note_bar_boniert = st.text_input("Bemerkung zu bar boniert", value=st.session_state.inp_notes_dict.get("bar_boniert", ""), key="note_bar_boniert")

col1, col2 = st.columns([1, 1])
with col1:
    essensbons_ueb = st.number_input("Essensbons oder Überweisung (€)", key="inp_essensbons_ueb", step=10.0)
with col2:
    note_essensbons_ueb = st.text_input("Bemerkung zu Essensbons/Überw.", value=st.session_state.inp_notes_dict.get("essensbons_ueb", ""), key="note_essensbons_ueb")

st.markdown("---")
st.markdown("#### 2. Ausgaben, Abzüge & Entnahmen")

col1, col2 = st.columns([1, 1])
with col1:
    bankomatkasse = st.number_input("abzüglich Bankomatkasse (€)", key="inp_bankomatkasse", step=10.0)
with col2:
    note_bankomatkasse = st.text_input("Bemerkung zu Bankomatkasse", value=st.session_state.inp_notes_dict.get("bankomatkasse", ""), key="note_bankomatkasse")

col1, col2 = st.columns([1, 1])
with col1:
    unbar_ueb = st.number_input("abzüglich unbar Überweisung (€)", key="inp_unbar_ueb", step=10.0)
with col2:
    note_unbar_ueb = st.text_input("Bemerkung zu unbar Überweisung", value=st.session_state.inp_notes_dict.get("unbar_ueb", ""), key="note_unbar_ueb")

col1, col2 = st.columns([1, 1])
with col1:
    essenbons = st.number_input("abzüglich Essenbons (€)", key="inp_essenbons", step=10.0)
with col2:
    note_essenbons = st.text_input("Bemerkung zu Essenbons", value=st.session_state.inp_notes_dict.get("essenbons", ""), key="note_essenbons")

col1, col2 = st.columns([1, 1])
with col1:
    trinkgeld_ma = st.number_input("abzüglich Trinkgeld - Mitarbeiter (€)", key="inp_trinkgeld_ma", step=5.0)
with col2:
    note_trinkgeld_ma = st.text_input("Bemerkung zu Trinkgeld", value=st.session_state.inp_notes_dict.get("trinkgeld_ma", ""), key="note_trinkgeld_ma")

col1, col2 = st.columns([1, 1])
with col1:
    gaestereklamation = st.number_input("abzüglich Gästereklamation (€)", key="inp_gaestereklamation", step=5.0)
with col2:
    note_gaestereklamation = st.text_input("Bemerkung zu Gästereklamation", value=st.session_state.inp_notes_dict.get("gaestereklamation", ""), key="note_gaestereklamation")

col1, col2 = st.columns([1, 1])
with col1:
    st.text_input("abzüglich Einkauf / Barauslagen (Automatisch)", value=f"{final_einkauf:.2f} €", disabled=True)
    einkauf = final_einkauf
with col2:
    note_einkauf = st.text_input("Bemerkung zu Einkauf", value=st.session_state.inp_notes_dict.get("einkauf", ""), key="note_einkauf")

col1, col2 = st.columns([1, 1])
with col1:
    barentnahme = st.number_input("Barentnahme (➖ Abzug) (€)", key="inp_barentnahme", step=10.0)
with col2:
    note_barentnahme = st.text_input("Bemerkung / Grund für Barentnahme", value=st.session_state.inp_notes_dict.get("barentnahme", ""), key="note_barentnahme")

col1, col2 = st.columns([1, 1])
with col1:
    loehne_vorschuesse = st.number_input("Mitarbeiter Löhne/Vorschüsse (€)", key="inp_loehne_vorschuesse", step=10.0)
with col2:
    note_loehne_vorschuesse = st.text_input("Bemerkung zu Löhne/Vorschüsse", value=st.session_state.inp_notes_dict.get("loehne_vorschuesse", ""), key="note_loehne_vorschuesse")

st.markdown("---")
st.markdown("#### 3. Kassaabschluss & Übertrag")

col1, col2 = st.columns([1, 1])
with col1:
    einzahlung_bank = st.number_input("Einzahlung an Bank (Bargeld) (€)", key="inp_einzahlung_bank", step=50.0)
with col2:
    note_einzahlung_bank = st.text_input("Bemerkung zu Einzahlung Bank", value=st.session_state.inp_notes_dict.get("einzahlung_bank", ""), key="note_einzahlung_bank")

if save_trigger:
    notes_dict = {
        "anfangsstand": note_anfangsstand,
        "tageslosung": note_tageslosung,
        "bareinlage": note_bareinlage,
        "bar_boniert": note_bar_boniert,
        "essensbons_ueb": note_essensbons_ueb,
        "bankomatkasse": note_bankomatkasse,
        "unbar_ueb": note_unbar_ueb,
        "essenbons": note_essenbons,
        "trinkgeld_ma": note_trinkgeld_ma,
        "gaestereklamation": note_gaestereklamation,
        "einkauf": note_einkauf,
        "barentnahme": note_barentnahme,
        "loehne_vorschuesse": note_loehne_vorschuesse,
        "einzahlung_bank": note_einzahlung_bank
    }

    record_payload = {
        "company_code": company_code_input,
        "datum": date_str,
        "anfangsstand": anfangsstand,
        "tageslosung": tageslosung,
        "bareinlage": bareinlage,
        "bar_boniert": bar_boniert,
        "essensbons_ueberweisung": essensbons_ueb,
        "bankomatkasse": bankomatkasse,
        "unbar_ueberweisung": unbar_ueb,
        "essenbons": essenbons,
        "trinkgeld_ma": trinkgeld_ma,
        "gaestereklamation": gaestereklamation,
        "einkauf": einkauf,
        "barentnahme": barentnahme,
        "loehne_vorschuesse": loehne_vorschuesse,
        "zwischenstand": live_zwischenstand,
        "einzahlung_bank": einzahlung_bank,
        "endstand": live_endstand,
        "notes": notes_dict,
        "receipt_items": current_receipts
    }

    if supabase:
        try:
            supabase.table("daily_sheets").upsert(record_payload, on_conflict="company_code, datum").execute()
            st.session_state.daily_sheets[date_str] = record_payload
            st.success(f"Tagesblatt für {selected_date.strftime('%d.%m.%Y')} erfolgreich gespeichert!")
        except Exception as e:
            st.error(f"Fehler beim Speichern in der Datenbank: {e}")