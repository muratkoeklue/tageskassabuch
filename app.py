import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import io
import os
from PIL import Image

# Seitenkonfiguration
st.set_page_config(page_title="Tages-Kassabuch (Österreich)", page_icon="💶", layout="wide")

UPLOAD_DIR = "belege_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

if "daily_sheets" not in st.session_state:
    st.session_state.daily_sheets = {}

if "temp_receipts" not in st.session_state:
    st.session_state.temp_receipts = {}

if "current_date_str" not in st.session_state:
    st.session_state.current_date_str = datetime.today().strftime("%Y-%m-%d")

st.title("💶 Digitales Tages-Kassabuch (Österreich-Standard & DATEV/BMD)")
st.markdown("Tageskassabuch mit automatischem Vortrag, Beleg-Scan, Felder-Leerung für Folgetage und korrekten DATEV EXTF-Exporten.")

# --- SEITENLEISTE: STEUERBERATER-STAMMDATEN ---
st.sidebar.header("⚙️ DATEV / BMD Stammdaten")
datev_user = st.sidebar.text_input("DATEV Benutzer", value="user")
datev_berater = st.sidebar.text_input("Beraternummer (Zelle K1)", value="503865")
datev_klient = st.sidebar.text_input("Mandantennummer (Zelle L1)", value="10288")

st.sidebar.divider()

# --- SEITENLEISTE: TAGESBLATT EINGEBEN ---
st.sidebar.header("📅 Tagesblatt erfassen / bearbeiten")

selected_date = st.sidebar.date_input("Datum des Tagesblatts", value=datetime.today())
date_str = selected_date.strftime("%Y-%m-%d")

prev_date_str = (selected_date - timedelta(days=1)).strftime("%Y-%m-%d")
auto_anfangsstand = 0.0
if prev_date_str in st.session_state.daily_sheets:
    auto_anfangsstand = st.session_state.daily_sheets[prev_date_str]["endstand"]

# Wenn sich das Datum ändert, Felder für den Tag zurücksetzen, falls noch nicht gespeichert
if st.session_state.current_date_str != date_str:
    st.session_state.current_date_str = date_str
    if date_str in st.session_state.daily_sheets:
        saved = st.session_state.daily_sheets[date_str]
        st.session_state.input_anfangsstand = float(saved["anfangsstand"])
        st.session_state.input_tageslosung = float(saved["tageslosung"])
        st.session_state.input_bar_boniert = float(saved["bar_boniert"])
        st.session_state.input_essensbons_ueb = float(saved["essensbons_ueberweisung"])
        st.session_state.input_bankomatkasse = float(saved["bankomatkasse"])
        st.session_state.input_unbar_ueb = float(saved["unbar_ueberweisung"])
        st.session_state.input_essenbons = float(saved["essenbons"])
        st.session_state.input_trinkgeld_ma = float(saved["trinkgeld_ma"])
        st.session_state.input_gaestereklamation = float(saved["gaestereklamation"])
        st.session_state.input_loehne_vorschuesse = float(saved["loehne_vorschuesse"])
        st.session_state.input_einzahlung_bank = float(saved["einzahlung_bank"])
        st.session_state.input_bemerkungen = saved["bemerkungen"]
    else:
        st.session_state.input_anfangsstand = float(auto_anfangsstand)
        st.session_state.input_tageslosung = 0.0
        st.session_state.input_bar_boniert = 0.0
        st.session_state.input_essensbons_ueb = 0.0
        st.session_state.input_bankomatkasse = 0.0
        st.session_state.input_unbar_ueb = 0.0
        st.session_state.input_essenbons = 0.0
        st.session_state.input_trinkgeld_ma = 0.0
        st.session_state.input_gaestereklamation = 0.0
        st.session_state.input_loehne_vorschuesse = 0.0
        st.session_state.input_einzahlung_bank = 0.0
        st.session_state.input_bemerkungen = ""

if "input_tageslosung" not in st.session_state:
    if date_str in st.session_state.daily_sheets:
        saved = st.session_state.daily_sheets[date_str]
        st.session_state.input_anfangsstand = float(saved["anfangsstand"])
        st.session_state.input_tageslosung = float(saved["tageslosung"])
        st.session_state.input_bar_boniert = float(saved["bar_boniert"])
        st.session_state.input_essensbons_ueb = float(saved["essensbons_ueberweisung"])
        st.session_state.input_bankomatkasse = float(saved["bankomatkasse"])
        st.session_state.input_unbar_ueb = float(saved["unbar_ueberweisung"])
        st.session_state.input_essenbons = float(saved["essenbons"])
        st.session_state.input_trinkgeld_ma = float(saved["trinkgeld_ma"])
        st.session_state.input_gaestereklamation = float(saved["gaestereklamation"])
        st.session_state.input_loehne_vorschuesse = float(saved["loehne_vorschuesse"])
        st.session_state.input_einzahlung_bank = float(saved["einzahlung_bank"])
        st.session_state.input_bemerkungen = saved["bemerkungen"]
    else:
        st.session_state.input_anfangsstand = float(auto_anfangsstand)
        st.session_state.input_tageslosung = 0.0
        st.session_state.input_bar_boniert = 0.0
        st.session_state.input_essensbons_ueb = 0.0
        st.session_state.input_bankomatkasse = 0.0
        st.session_state.input_unbar_ueb = 0.0
        st.session_state.input_essenbons = 0.0
        st.session_state.input_trinkgeld_ma = 0.0
        st.session_state.input_gaestereklamation = 0.0
        st.session_state.input_loehne_vorschuesse = 0.0
        st.session_state.input_einzahlung_bank = 0.0
        st.session_state.input_bemerkungen = ""

if date_str not in st.session_state.temp_receipts:
    existing_saved = st.session_state.daily_sheets.get(date_str, {})
    st.session_state.temp_receipts[date_str] = existing_saved.get("receipt_items", [])


# --- BELEG-UPLOAD ---
st.sidebar.divider()
st.sidebar.header("📸 Einkaufsbelege hochladen")

uploaded_single_file = st.sidebar.file_uploader(
    "Beleg auswählen (PNG, JPG)", 
    type=["png", "jpg", "jpeg"],
    key=f"uploader_key_{date_str}"
)

if uploaded_single_file is not None:
    pil_img = Image.open(uploaded_single_file).convert('RGB')
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Beleg-Vorschau & Betrag")
    st.sidebar.image(pil_img, caption=uploaded_single_file.name, use_container_width=True)
    
    input_beleg_betrag = st.sidebar.number_input(
        "Rechnungsbetrag bestätigen (€)", 
        value=0.0, 
        step=5.0, 
        format="%.2f",
        key=f"amt_{uploaded_single_file.name}"
    )
    
    col_btn1, col_btn2 = st.sidebar.columns(2)
    if col_btn1.button("✅ Speichern & Ablegen"):
        file_path = os.path.join(UPLOAD_DIR, f"{date_str}_{datetime.now().strftime('%H%M%S')}_{uploaded_single_file.name}")
        pil_img.save(file_path)
            
        st.session_state.temp_receipts[date_str].append({
            "path": file_path,
            "amount": input_beleg_betrag,
            "name": uploaded_single_file.name
        })
        st.sidebar.success("Beleg abgelegt & Summe aktualisiert!")
        st.rerun()
        
    if col_btn2.button("❌ Verwerfen"):
        st.rerun()

current_receipts = st.session_state.temp_receipts.get(date_str, [])
calculated_total_einkauf = sum(r["amount"] for r in current_receipts)

if current_receipts:
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Bereits abgelegte Belege ({len(current_receipts)}):**")
    for idx, rec in enumerate(current_receipts):
        c_txt, c_del = st.sidebar.columns([3, 1])
        c_txt.text(f"• {rec['name']} ({rec['amount']:.2f} €)")
        if c_del.button("🗑️", key=f"del_{date_str}_{idx}"):
            current_receipts.pop(idx)
            st.rerun()

st.sidebar.markdown(f"👉 **Aktuelle Einkaufssumme: {calculated_total_einkauf:.2f} €**")


# --- HAUPTFORMULAR FÜR DAS TAGESBLATT ---
with st.sidebar.form("daily_form"):
    st.markdown("---")
    st.markdown(f"**Tagesblatt-Daten für: {selected_date.strftime('%d.%m.%Y')}**")
    
    anfangsstand = st.number_input("Anfangsstand - Übertrag v. Vortag (€)", key="input_anfangsstand", step=10.0)
    tageslosung = st.number_input("Tageslosung (Brutto) (€)", key="input_tageslosung", step=10.0)
    bar_boniert = st.number_input("bar kassiert bereits bonierte (€)", key="input_bar_boniert", step=10.0)
    essensbons_ueb = st.number_input("Essensbons oder Überweisung (€)", key="input_essensbons_ueb", step=10.0)
    
    st.markdown("--- *Abzüge / Auslagen* ---")
    bankomatkasse = st.number_input("abzüglich Bankomatkasse (€)", key="input_bankomatkasse", step=10.0)
    unbar_ueb = st.number_input("abzüglich unbar Überweisung (€)", key="input_unbar_ueb", step=10.0)
    essenbons = st.number_input("abzüglich Essensbons (€)", key="input_essenbons", step=10.0)
    trinkgeld_ma = st.number_input("abzüglich Trinkgeld - Mitarbeiter (€)", key="input_trinkgeld_ma", step=5.0)
    gaestereklamation = st.number_input("abzüglich Gästereklamation (€)", key="input_gaestereklamation", step=5.0)
    
    saved_einkauf = st.session_state.daily_sheets.get(date_str, {}).get("einkauf", 0.0)
    final_einkauf = calculated_total_einkauf if calculated_total_einkauf > 0 else float(saved_einkauf)
    st.markdown(f"**abzüglich Einkauf / Barauslagen: {final_einkauf:.2f} € (Automatisch)**")
    einkauf = final_einkauf
    
    loehne_vorschuesse = st.number_input("Mitarbeiter Löhne/Vorschüsse (€)", key="input_loehne_vorschuesse", step=10.0)
    
    st.markdown("--- *Ende des Tages* ---")
    einzahlung_bank = st.number_input("Einzahlung an Bank (Bargeld) (€)", key="input_einzahlung_bank", step=50.0)
    bemerkungen = st.text_area("Bemerkungen", key="input_bemerkungen")
    
    submitted = st.form_submit_button("Tagesblatt speichern")
    
    if submitted:
        zwischenstand = (anfangsstand + tageslosung + bar_boniert + essensbons_ueb 
                         - bankomatkasse - unbar_ueb - essenbons - trinkgeld_ma 
                         - gaestereklamation - einkauf - loehne_vorschuesse)
        endstand = zwischenstand - einzahlung_bank
        
        st.session_state.daily_sheets[date_str] = {
            "datum": date_str,
            "anfangsstand": anfangsstand,
            "tageslosung": tageslosung,
            "bar_boniert": bar_boniert,
            "essensbons_ueberweisung": essensbons_ueb,
            "bankomatkasse": bankomatkasse,
            "unbar_ueberweisung": unbar_ueb,
            "essenbons": essenbons,
            "trinkgeld_ma": trinkgeld_ma,
            "gaestereklamation": gaestereklamation,
            "einkauf": einkauf,
            "loehne_vorschuesse": loehne_vorschuesse,
            "zwischenstand": zwischenstand,
            "einzahlung_bank": einzahlung_bank,
            "endstand": endstand,
            "bemerkungen": bemerkungen,
            "receipt_items": current_receipts
        }
        st.success(f"Tagesblatt für {selected_date.strftime('%d.%m.%Y')} erfolgreich gespeichert!")


# --- HAUPTSEITE: ÜBERSICHT & EXPORTE ---
if len(st.session_state.daily_sheets) > 0:
    df_days = pd.DataFrame(list(st.session_state.daily_sheets.values()))
    df_days["Datum_Obj"] = pd.to_datetime(df_days["datum"])
    df_days = df_days.sort_values("Datum_Obj").reset_index(drop=True)

    st.subheader("📋 Erfasste Tagesblätter im Überblick")
    display_df = df_days[["datum", "anfangsstand", "tageslosung", "einkauf", "zwischenstand", "loehne_vorschuesse", "einzahlung_bank", "endstand"]].copy()
    display_df.columns = ["Datum", "Anfangsstand", "Tageslosung", "Einkauf", "Zwischenstand", "Löhne/Vorschüsse", "Bank-Einzahlung", "Endstand (Kassa)"]
    st.dataframe(display_df, use_container_width=True)

    st.divider()

    # --- EINZELNES TAGES-PDF (MIT MULTI-PAGE BELEGEN) ---
    st.subheader("📄 Tagesblatt-PDF generieren (inkl. aller Beleg-Fotos)")
    col_pdf_date, col_pdf_btn = st.columns([2, 1])
    
    available_dates = df_days["datum"].tolist()
    chosen_date_pdf = col_pdf_date.selectbox("Wähle das Datum für das Tages-PDF", available_dates)
    
    def generate_daily_pdf(data):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph(f"KASSABUCH - Tagesblatt vom {data['datum']}", styles['Heading1']))
        elements.append(Spacer(1, 10))
        
        table_data = [
            ["Position / Beschreibung", "Betrag (€)"],
            ["Anfangsstand - Übertrag v. Vortag", f"{data['anfangsstand']:.2f}"],
            ["Tageslosung", f"{data['tageslosung']:.2f}"],
            ["bar kassiert bereits bonierte", f"{data['bar_boniert']:.2f}"],
            ["Essensbons oder Überweisung", f"{data['essensbons_ueberweisung']:.2f}"],
            ["abzüglich Bankomatkasse", f"-{data['bankomatkasse']:.2f}"],
            ["abzüglich unbar Überweisung", f"-{data['unbar_ueberweisung']:.2f}"],
            ["abzüglich Essenbons", f"-{data['essenbons']:.2f}"],
            ["abzüglich Trinkgeld - Mitarbeiter", f"-{data['trinkgeld_ma']:.2f}"],
            ["abzüglich Gästereklamation", f"-{data['gaestereklamation']:.2f}"],
            ["abzüglich Einkauf / Barauslagen (Summe)", f"-{data['einkauf']:.2f}"],
            ["Mitarbeiter Löhne/Vorschüsse", f"-{data['loehne_vorschuesse']:.2f}"],
            ["--- ZWISCHENSTAND ---", f"{data['zwischenstand']:.2f}"],
            ["Einzahlung an Bank", f"-{data['einzahlung_bank']:.2f}"],
            ["=== ENDSTAND (Übertrag nächster Tag) ===", f"{data['endstand']:.2f}"]
        ]
        
        t = Table(table_data, colWidths=[350, 150])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#333333")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0, 12), (-1, 12), colors.HexColor("#eeeeee")),
            ('BACKGROUND', (0, 14), (-1, 14), colors.HexColor("#dddddd")),
            ('FONTNAME', (0, 14), (-1, 14), 'Helvetica-Bold'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(f"<b>Bemerkungen:</b> {data['bemerkungen'] if data['bemerkungen'] else 'Keine'}", styles['Normal']))
        
        receipts = data.get("receipt_items", [])
        for rec in receipts:
            f_path = rec["path"]
            if os.path.exists(f_path):
                elements.append(PageBreak())
                elements.append(Paragraph(f"<b>Beleg: {rec['name']} | Betrag: {rec['amount']:.2f} €</b>", styles['Heading2']))
                elements.append(Spacer(1, 10))
                img = RLImage(f_path, width=400, height=550)
                elements.append(img)
                    
        doc.build(elements)
        buffer.seek(0)
        return buffer

    if chosen_date_pdf:
        day_row = df_days[df_days["datum"] == chosen_date_pdf].iloc[0].to_dict()
        pdf_buffer = generate_daily_pdf(day_row)
        with col_pdf_btn:
            st.write("")
            st.download_button(
                label="📥 Tages-PDF (inkl. aller Belege) herunterladen",
                data=pdf_buffer,
                file_name=f"Tageskassabuch_mit_Belegen_{chosen_date_pdf}.pdf",
                mime="application/pdf"
            )

    st.divider()

    # --- ZEITRAUM-AUSWAHL FÜR STEUERBERATER-SCHNITTSTELLEN (DATEV & BMD AT) ---
    st.subheader("📊 Steuerberater-Schnittstellen (DATEV & BMD Österreich) - Zeitraum-Export")
    st.info("Wähle hier den gewünschten **Zeitraum (Von - Bis)** aus.")

    col_start, col_end = st.columns(2)
    min_date_val = df_days["Datum_Obj"].min().date()
    max_date_val = df_days["Datum_Obj"].max().date()

    export_start_date = col_start.date_input("Startdatum für Export", value=min_date_val, key="exp_start")
    export_end_date = col_end.date_input("Enddatum für Export", value=max_date_val, key="exp_end")

    mask = (df_days["Datum_Obj"].dt.date >= export_start_date) & (df_days["Datum_Obj"].dt.date <= export_end_date)
    df_export_period = df_days.loc[mask]

    col_datev_at, col_bmd_at = st.columns(2)

    def generate_datev_at_csv(period_df, user_val, berater_val, klient_val, start_d, end_d):
        start_str = start_d.strftime("%Y%m%d")
        end_str = end_d.strftime("%Y%m%d")
        # Wirtschaftsjahresbeginn (z.B. 20260101 basierend auf dem Startjahr)
        wj_beginn = f"{start_d.year}0101"
        now_str = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Mapping nach Vorgabe: 
        # Index 10 (Spalte K) = Beraternummer
        # Index 11 (Spalte L) = Mandantennummer
        # Index 12 (Spalte M) = Wirtschaftsjahresbeginn (z.B. 20260101)
        # Index 14 (Spalte O) = Zeitraumbeginn
        # Index 15 (Spalte P) = Zeitraumende
        header_cols = [
            "EXTF", "510", "21", "Buchungsstapel", "12", now_str, "", 
            user_val, "", "", berater_val, klient_val, wj_beginn, "", 
            start_str, end_str, "1", "0", "0", "EUR"
        ]
        lines = [";".join(header_cols)]
        
        for _, r in period_df.iterrows():
            datum_fmt = pd.to_datetime(r["datum"]).strftime("%d%m")
            belegfeld = r["datum"].replace("-", "")
            
            if r["tageslosung"] > 0:
                val_str = f"{r['tageslosung']:.2f}".replace('.', ',')
                lines.append(f"{val_str};S;EUR;;{datum_fmt};;{belegfeld};Tageslosung {r['datum']};4000;2700")
                
            if r["einkauf"] > 0:
                val_str = f"{r['einkauf']:.2f}".replace('.', ',')
                lines.append(f"{val_str};H;EUR;;{datum_fmt};;{belegfeld};Einkauf / Barauslagen {r['datum']};5000;2700")
                
            if r["loehne_vorschuesse"] > 0:
                val_str = f"{r['loehne_vorschuesse']:.2f}".replace('.', ',')
                lines.append(f"{val_str};H;EUR;;{datum_fmt};;{belegfeld};Mitarbeiter Löhne/Vorschüsse {r['datum']};3700;2700")
                
            if r["einzahlung_bank"] > 0:
                val_str = f"{r['einzahlung_bank']:.2f}".replace('.', ',')
                lines.append(f"{val_str};H;EUR;;{datum_fmt};;{belegfeld};Bank-Einzahlung {r['datum']};2800;2700")
                
        return "\n".join(lines)

    with col_datev_at:
        st.markdown("#### DATEV Österreich (EXTF-CSV)")
        st.write(f"Zeitraum: {export_start_date.strftime('%d.%m.%Y')} bis {export_end_date.strftime('%d.%m.%Y')} ({len(df_export_period)} Tage enthalten).")
        
        datev_text = generate_datev_at_csv(df_export_period, datev_user, datev_berater, datev_klient, export_start_date, export_end_date)
        if not df_export_period.empty:
            st.download_button(
                label="📥 DATEV AT EXTF-Datei herunterladen",
                data=datev_text.encode("cp1252", errors="replace"),
                file_name=f"EXTF_Kassabuch_{export_start_date}_bis_{export_end_date}.csv",
                mime="text/csv",
                key="dl_datev"
            )
        else:
            st.warning("Keine Buchungen im gewählten Zeitraum vorhanden.")

    def generate_bmd_at_csv(period_df):
        rows = []
        for _, r in period_df.iterrows():
            datum_fmt = pd.to_datetime(r["datum"]).strftime("%d.%m.%Y")
            if r["tageslosung"] > 0:
                rows.append({
                    "Belegdatum": datum_fmt,
                    "Belegnummer": r["datum"].replace("-", ""),
                    "Sollkonto": "2700",
                    "Habenkonto": "4000",
                    "Betrag": f"{r['tageslosung']:.2f}".replace('.', ','),
                    "Buchungstext": f"Tageslosung {r['datum']}"
                })
            if r["einkauf"] > 0:
                rows.append({
                    "Belegdatum": datum_fmt,
                    "Belegnummer": r["datum"].replace("-", ""),
                    "Sollkonto": "5000",
                    "Habenkonto": "2700",
                    "Betrag": f"{r['einkauf']:.2f}".replace('.', ','),
                    "Buchungstext": f"Einkauf / Barauslagen {r['datum']}"
                })
            if r["loehne_vorschuesse"] > 0:
                rows.append({
                    "Belegdatum": datum_fmt,
                    "Belegnummer": r["datum"].replace("-", ""),
                    "Sollkonto": "3700",
                    "Habenkonto": "2700",
                    "Betrag": f"{r['loehne_vorschuesse']:.2f}".replace('.', ','),
                    "Buchungstext": f"Mitarbeiter Löhne/Vorschüsse {r['datum']}"
                })
            if r["einzahlung_bank"] > 0:
                rows.append({
                    "Belegdatum": datum_fmt,
                    "Belegnummer": r["datum"].replace("-", ""),
                    "Sollkonto": "2800",
                    "Habenkonto": "2700",
                    "Betrag": f"{r['einzahlung_bank']:.2f}".replace('.', ','),
                    "Buchungstext": f"Bank-Einzahlung {r['datum']}"
                })
        export_df = pd.DataFrame(rows)
        if export_df.empty:
            return ""
        return export_df.to_csv(index=False, sep=";", encoding="cp1252")

    with col_bmd_at:
        st.markdown("#### BMD Österreich (CSV)")
        st.write(f"Zeitraum: {export_start_date.strftime('%d.%m.%Y')} bis {export_end_date.strftime('%d.%m.%Y')} ({len(df_export_period)} Tage enthalten).")
        bmd_at_data = generate_bmd_at_csv(df_export_period)
        if bmd_at_data:
            st.download_button(
                label="📥 BMD AT Zeitraum-CSV herunterladen",
                data=bmd_at_data,
                file_name=f"BMD_AT_Kassabuch_{export_start_date}_bis_{export_end_date}.csv",
                mime="text/csv",
                key="dl_bmd"
            )
        else:
            st.warning("Keine Buchungen im gewählten Zeitraum vorhanden.")

else:
    st.info("Noch keine Tagesblätter erfasst. Nutze die linke Seitenleiste!")