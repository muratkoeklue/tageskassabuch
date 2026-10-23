import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import io
import os
import json
from PIL import Image
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from supabase import create_client, Client

# Seitenkonfiguration
st.set_page_config(page_title="Tages-Kassabuch (Multi-Tenant)", page_icon="💶", layout="wide")

# CSS für fixierten Header
st.markdown("""
<style>
    div[data-testid="stVerticalBlock"] > div:has(div.sticky-header-marker) {
        position: sticky;
        top: 2.8rem;
        background-color: var(--background-color, #ffffff);
        z-index: 999;
        padding-top: 10px;
        padding-bottom: 10px;
        border-bottom: 2px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

UPLOAD_DIR = "belege_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- SUPABASE DATENBANK VERBINDUNG ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL", "") if "SUPABASE_URL" in st.secrets else ""
    key = st.secrets.get("SUPABASE_KEY", "") if "SUPABASE_KEY" in st.secrets else ""
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None

supabase = init_supabase()

if not supabase:
    st.sidebar.warning("⚠️ Supabase API-Zugangsdaten nicht gefunden! Bitte in den Streamlit Cloud Secrets hinterlegen.")

# --- HELFER-FUNKTIONEN FÜR DOKUMENTE ---
def generate_multi_day_pdf(period_df):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()

    for idx, (_, data) in enumerate(period_df.iterrows()):
        if idx > 0:
            elements.append(PageBreak())

        date_formatted = datetime.strptime(str(data['datum']), "%Y-%m-%d").strftime("%d.%m.%Y")
        elements.append(Paragraph(f"KASSABUCH - Tagesblatt vom {date_formatted}", styles['Heading1']))
        elements.append(Spacer(1, 10))
        
        notes = data.get("notes", {}) or {}
        
        table_data = [
            ["Position / Beschreibung", "Betrag (€)", "Bemerkung"],
            ["Anfangsstand - Übertrag v. Vortag", f"{float(data['anfangsstand']):.2f}", notes.get("anfangsstand", "")],
            ["Tageslosung (Brutto)", f"{float(data['tageslosung']):.2f}", notes.get("tageslosung", "")],
            ["Bareinlage (Hinzurechnung)", f"{float(data.get('bareinlage', 0.0)):.2f}", notes.get("bareinlage", "")],
            ["bar kassiert bereits bonierte Essensbons oder Überweisung", f"{float(data.get('bar_boniert', 0) or 0) + float(data.get('essensbons_ueberweisung', 0) or 0):.2f}", notes.get("bar_boniert_essensbons_ueberweisung", notes.get("bar_boniert", "") or notes.get("essensbons_ueb", ""))],
            ["abzüglich Bankomatkasse", f"-{float(data['bankomatkasse']):.2f}", notes.get("bankomatkasse", "")],
            ["abzüglich unbar Überweisung", f"-{float(data['unbar_ueberweisung']):.2f}", notes.get("unbar_ueb", "")],
            ["abzüglich Essenbons", f"-{float(data['essenbons']):.2f}", notes.get("essenbons", "")],
            ["abzüglich Trinkgeld - Mitarbeiter", f"-{float(data['trinkgeld_ma']):.2f}", notes.get("trinkgeld_ma", "")],
            ["abzüglich Gästereklamation", f"-{float(data['gaestereklamation']):.2f}", notes.get("gaestereklamation", "")],
            ["abzüglich Einkauf / Barauslagen", f"-{float(data['einkauf']):.2f}", notes.get("einkauf", "")],
            ["Barentnahme (Abzug)", f"-{float(data.get('barentnahme', 0.0)):.2f}", notes.get("barentnahme", "")],
            ["Mitarbeiter Löhne/Vorschüsse", f"-{float(data['loehne_vorschuesse']):.2f}", notes.get("loehne_vorschuesse", "")],
            ["--- ZWISCHENSTAND ---", f"{float(data['zwischenstand']):.2f}", ""],
            ["Einzahlung an Bank", f"-{float(data['einzahlung_bank']):.2f}", notes.get("einzahlung_bank", "")],
            ["=== ENDSTAND (Kasse) ===", f"{float(data['endstand']):.2f}", ""]
        ]
        
        t = Table(table_data, colWidths=[220, 100, 180])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#333333")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('ALIGN', (2,0), (2,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0, 14), (-1, 14), colors.HexColor("#eeeeee")),
            ('BACKGROUND', (0, 16), (-1, 16), colors.HexColor("#dddddd")),
            ('FONTNAME', (0, 16), (-1, 16), 'Helvetica-Bold'),
        ]))
        elements.append(t)
        
        receipts = data.get("receipt_items", []) or []
        for rec in receipts:
            f_path = rec.get("path", "")
            if f_path and os.path.exists(f_path):
                elements.append(PageBreak())
                elements.append(Paragraph(f"<b>Beleg zu Tag {date_formatted}: {rec['name']} | Betrag: {float(rec['amount']):.2f} €</b>", styles['Heading2']))
                elements.append(Spacer(1, 10))
                try:
                    img = RLImage(f_path, width=400, height=520)
                    elements.append(img)
                except Exception as e:
                    elements.append(Paragraph(f"<i>[Bild konnte nicht geladen werden: {e}]</i>", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_datev_at_csv(period_df, user_val, berater_val, klient_val, start_d, end_d):
    """
    Erstellt einen DATEV-EXTF-Buchungsstapel mit der Spaltenstruktur der
    bereitgestellten Vorlage. Die Inhalte der vorhandenen ersten Kopfzeile
    bleiben unverändert; sie wird nur auf die 124 Spalten der Vorlage aufgefüllt.
    """
    start_str = start_d.strftime("%Y%m%d")
    end_str = end_d.strftime("%Y%m%d")
    wj_beginn = f"{start_d.year}0101"
    now_str = datetime.now().strftime("%Y%m%d%H%M%S")

    # Kopfzeile aus dem bisherigen Code: Werte nicht verändern.
    header_cols = [
        "EXTF", "510", "21", "Buchungsstapel", "12", now_str, "",
        user_val, "", "", berater_val, klient_val, wj_beginn, "",
        start_str, end_str, "1", "0", "0", "EUR"
    ]

    # Die Vorlage enthält insgesamt 124 Spalten. Leere Felder am Ende der
    # bestehenden Kopfzeile werden ergänzt, ohne ihre bisherigen Werte zu ändern.
    column_count = 124
    header_row = header_cols + [""] * (column_count - len(header_cols))

    # Zweite CSV-Zeile: Spaltenüberschriften exakt wie in der Vorlage.
    column_names = [
        "Umsatz (ohne Soll/Haben-Kz)", "Soll/Haben-Kennzeichen", "WKZ Umsatz",
        "Kurs", "Basis-Umsatz", "WKZ Basis-Umsatz", "Konto",
        "Gegenkonto (ohne BU-Schlüssel)", "BU-Schlüssel", "Belegdatum",
        "Belegfeld 1", "Belegfeld 2", "Skonto", "Buchungstext",
        "Postensperre", "Diverse Adressnummer", "Geschäftspartnerbank",
        "Sachverhalt", "Zinssperre", "Beleglink",
        "Beleginfo - Art 1", "Beleginfo - Inhalt 1", "Beleginfo - Art 2",
        "Beleginfo - Inhalt 2", "Beleginfo - Art 3", "Beleginfo - Inhalt 3",
        "Beleginfo - Art 4", "Beleginfo - Inhalt 4", "Beleginfo - Art 5",
        "Beleginfo - Inhalt 5", "Beleginfo - Art 6", "Beleginfo - Inhalt 6",
        "Beleginfo - Art 7", "Beleginfo - Inhalt 7", "Beleginfo - Art 8",
        "Beleginfo - Inhalt 8", "KOST1 - Kostenstelle", "KOST2 - Kostenstelle",
        "Kost-Menge", "EU-Land u. UStID", "EU-Steuersatz",
        "Abw. Versteuerungsart", "Sachverhalt L+L", "Funktionsergänzung L+L",
        "BU 49 Hauptfunktionstyp", "BU 49 Hauptfunktionsnummer",
        "BU 49 Funktionsergänzung", "Zusatzinformation - Art 1",
        "Zusatzinformation- Inhalt 1", "Zusatzinformation - Art 2",
        "Zusatzinformation- Inhalt 2", "Zusatzinformation - Art 3",
        "Zusatzinformation- Inhalt 3", "Zusatzinformation - Art 4",
        "Zusatzinformation- Inhalt 4", "Zusatzinformation - Art 5",
        "Zusatzinformation- Inhalt 5", "Zusatzinformation - Art 6",
        "Zusatzinformation- Inhalt 6", "Zusatzinformation - Art 7",
        "Zusatzinformation- Inhalt 7", "Zusatzinformation - Art 8",
        "Zusatzinformation- Inhalt 8", "Zusatzinformation - Art 9",
        "Zusatzinformation- Inhalt 9", "Zusatzinformation - Art 10",
        "Zusatzinformation- Inhalt 10", "Zusatzinformation - Art 11",
        "Zusatzinformation- Inhalt 11", "Zusatzinformation - Art 12",
        "Zusatzinformation- Inhalt 12", "Zusatzinformation - Art 13",
        "Zusatzinformation- Inhalt 13", "Zusatzinformation - Art 14",
        "Zusatzinformation- Inhalt 14", "Zusatzinformation - Art 15",
        "Zusatzinformation- Inhalt 15", "Zusatzinformation - Art 16",
        "Zusatzinformation- Inhalt 16", "Zusatzinformation - Art 17",
        "Zusatzinformation- Inhalt 17", "Zusatzinformation - Art 18",
        "Zusatzinformation- Inhalt 18", "Zusatzinformation - Art 19",
        "Zusatzinformation- Inhalt 19", "Zusatzinformation - Art 20",
        "Zusatzinformation- Inhalt 20", "Stück", "Gewicht", "Zahlweise",
        "Forderungsart", "Veranlagungsjahr", "Zugeordnete Fälligkeit",
        "Skontotyp", "Auftragsnummer", "Buchungstyp",
        "Ust-Schlüssel (Anzahlungen)", "EU-Land (Anzahlungen)",
        "Sachverhalt L+L (Anzahlungen)", "EU-Steuersatz (Anzahlungen)",
        "Erlöskonto (Anzahlungen)", "Herkunft-Kz", "Leerfeld", "KOST-Datum",
        "Mandatsreferenz", "Skontosperre", "Gesellschaftername",
        "Beteiligtennummer", "Identifikationsnummer", "Zeichnernummer",
        "Postensperre bis", "Bezeichnung SoBil-Sachverhalt",
        "Kennzeichen SoBil-Buchung", "Festschreibung", "Leistungsdatum",
        "Datum Zuord. Steuerperiode", "Fälligkeit", "Generalumkehr",
        "Steuersatz", "Land", "Abrechnungsreferenz",
        "BVV-Position (Betriebsvermögensvergleich)",
        "EU-Mitgliedstaat u. UStID (Ursprung)", "EU-Steuersatz (Ursprung)"
    ]
    if len(column_names) != column_count:
        raise ValueError(f"DATEV-Vorlage erwartet {column_count} Spalten, gefunden: {len(column_names)}")

    lines = [
        ";".join(header_row),
        ";".join(column_names)
    ]

    # Fixfelder aus der dritten Zeile der Vorlage (1-basierte Spaltennummern):
    # 5, 9, 13, 15, 19 und 114 müssen bei jedem Buchungssatz "0" enthalten.
    fixed_zero_columns = (5, 9, 13, 15, 19, 114)

    def add_booking(amount, sh, counter_account, booking_date, text):
        amount = float(amount or 0)
        if amount <= 0:
            return

        row = [""] * column_count
        row[0] = f"{amount:.2f}".replace(".", ",")  # Spalte 1: Umsatz
        row[1] = sh                                 # Spalte 2: Soll/Haben
        row[2] = "EUR"                              # Spalte 3: Währung
        row[6] = "2700"                             # Spalte 7: Konto immer 2700
        row[7] = str(counter_account)               # Spalte 8: Gegenkonto
        row[9] = pd.to_datetime(booking_date).strftime("%d%m")  # Spalte 10
        row[10] = str(booking_date).replace("-", "")            # Spalte 11
        row[13] = str(text)                         # Spalte 14: Buchungstext

        for col_num in fixed_zero_columns:
            row[col_num - 1] = "0"

        lines.append(";".join(row))

    for _, r in period_df.iterrows():
        datum = r["datum"]
        datum_text = str(datum)

        # Alle Buchungssätze verwenden im DATEV-Feld "Konto" immer 2700.
        # Die jeweiligen Gegenkonten werden im Feld "Gegenkonto" ausgegeben.
        add_booking(r.get("tageslosung", 0), "S", "2772",
                    datum, f"Tageslosung {datum_text}")
        add_booking(r.get("bareinlage", 0), "S", "9120",
                    datum, f"Bareinlage {datum_text}")

        # Diese beiden Eingabefelder bilden im DATEV-Export eine gemeinsame Zeile.
        bereits_boniert_gesamt = (
            float(r.get("bar_boniert", 0) or 0)
            + float(r.get("essensbons_ueberweisung", 0) or 0)
        )
        add_booking(
            bereits_boniert_gesamt, "H", "2881", datum,
            f"bar kassiert bereits bonierte Essensbons oder Überweisung {datum_text}"
        )

        # Abzüge / Ausgaben
        add_booking(r.get("bankomatkasse", 0), "H", "2882",
                    datum, f"Bankomatkasse {datum_text}")
        add_booking(r.get("unbar_ueberweisung", 0), "H", "2881",
                    datum, f"Unbare Überweisung {datum_text}")
        add_booking(r.get("essenbons", 0), "H", "2881",
                    datum, f"Essensbons {datum_text}")
        add_booking(r.get("trinkgeld_ma", 0), "H", "6710",
                    datum, f"Trinkgeld Mitarbeiter {datum_text}")
        add_booking(r.get("gaestereklamation", 0), "H", "7655",
                    datum, f"Gästereklamation {datum_text}")
        add_booking(r.get("einkauf", 0), "H", "2775",
                    datum, f"Einkauf / Barauslagen {datum_text}")
        add_booking(r.get("loehne_vorschuesse", 0), "H", "3745",
                    datum, f"Mitarbeiter Löhne/Vorschüsse {datum_text}")
        add_booking(r.get("einzahlung_bank", 0), "H", "2880",
                    datum, f"Einzahlung an Bank {datum_text}")

    return "\n".join(lines)

def generate_bmd_at_csv(period_df):
    rows = []
    for _, r in period_df.iterrows():
        datum_fmt = pd.to_datetime(r["datum"]).strftime("%d.%m.%Y")
        belegnum = str(r["datum"]).replace("-", "")
        if float(r["tageslosung"]) > 0:
            rows.append({
                "Belegdatum": datum_fmt, "Belegnummer": belegnum,
                "Sollkonto": "2700", "Habenkonto": "4000",
                "Betrag": f"{float(r['tageslosung']):.2f}".replace('.', ','), "Buchungstext": f"Tageslosung {r['datum']}"
            })
        if float(r.get("bareinlage", 0.0)) > 0:
            rows.append({
                "Belegdatum": datum_fmt, "Belegnummer": belegnum,
                "Sollkonto": "2700", "Habenkonto": "9000",
                "Betrag": f"{float(r['bareinlage']):.2f}".replace('.', ','), "Buchungstext": f"Bareinlage {r['datum']}"
            })
        if float(r["einkauf"]) > 0:
            rows.append({
                "Belegdatum": datum_fmt, "Belegnummer": belegnum,
                "Sollkonto": "5000", "Habenkonto": "2700",
                "Betrag": f"{float(r['einkauf']):.2f}".replace('.', ','), "Buchungstext": f"Einkauf / Barauslagen {r['datum']}"
            })
        if float(r.get("barentnahme", 0.0)) > 0:
            rows.append({
                "Belegdatum": datum_fmt, "Belegnummer": belegnum,
                "Sollkonto": "9000", "Habenkonto": "2700",
                "Betrag": f"{float(r['barentnahme']):.2f}".replace('.', ','), "Buchungstext": f"Barentnahme {r['datum']}"
            })
        if float(r["loehne_vorschuesse"]) > 0:
            rows.append({
                "Belegdatum": datum_fmt, "Belegnummer": belegnum, # Behoben: string conversion statt r["datum"].replace()
                "Sollkonto": "3700", "Habenkonto": "2700",
                "Betrag": f"{float(r['loehne_vorschuesse']):.2f}".replace('.', ','), "Buchungstext": f"Mitarbeiter Löhne/Vorschüsse {r['datum']}"
            })
        if float(r["einzahlung_bank"]) > 0:
            rows.append({
                "Belegdatum": datum_fmt, "Belegnummer": belegnum,
                "Sollkonto": "2800", "Habenkonto": "2700",
                "Betrag": f"{float(r['einzahlung_bank']):.2f}".replace('.', ','), "Buchungstext": f"Bank-Einzahlung {r['datum']}"
            })
    export_df = pd.DataFrame(rows)
    if export_df.empty:
        return ""
    return export_df.to_csv(index=False, sep=";", encoding="cp1252")


# --- SEITENLEISTE (MANDANTEN-LOGIN & NAVIGATION) ---
st.sidebar.title("🏢 Unternehmens-Login")

company_code_input = st.sidebar.text_input("🔑 Unternehmens-Code (Mandant)", value="", placeholder="z. B. FIRMA-101").strip().upper()

if not company_code_input:
    st.info("👈 Bitte gib links deinen Unternehmens-Code ein, um auf dein Kassabuch zuzugreifen.")
    st.stop()

# STAMMDATEN DES UNTERNEHMENS SICHER LADEN / ANLEGEN
profile_data = {}
if supabase:
    try:
        res = supabase.table("company_profiles").select("*").eq("company_code", company_code_input).execute()
        if res.data:
            profile_data = res.data[0]
        else:
            supabase.table("company_profiles").insert({
                "company_code": company_code_input,
                "company_name": company_code_input,
                "datev_user": "user",
                "datev_berater": "503865",
                "datev_klient": "10288"
            }).execute()
            profile_data = {
                "company_code": company_code_input,
                "company_name": company_code_input,
                "datev_user": "user",
                "datev_berater": "503865",
                "datev_klient": "10288"
            }
    except Exception as e:
        st.sidebar.error(f"Datenbankfehler: {e}")

st.sidebar.success(f"Angemeldet als: **{company_code_input}**")

# Prüfen ob Administrator eingeloggt ist
is_admin = (company_code_input == "KASSABUCH-ADMIN")

# --- ADMIN BEREICH ---
if is_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("👑 Admin-Bereich")
    admin_action = st.sidebar.radio("Modus wählen:", ["Tageskassabuch", "Neue Firma / Mandanten anlegen"])
    
    if admin_action == "Neue Firma / Mandanten anlegen":
        st.title("➕ Neue Firma / Mandanten anlegen")
        st.write("Erstelle hier einen neuen Firmen-Code für deine Kunden.")
        
        with st.form("new_company_form"):
            new_code = st.text_input("Neuer Unternehmens-Code (z.B. RESTAURANT-XY)").strip().upper()
            new_name = st.text_input("Firmenname / Anzeigename")
            d_user_new = st.text_input("DATEV Benutzer", value="user")
            d_berater_new = st.text_input("Beraternummer", value="503865")
            d_klient_new = st.text_input("Mandantennummer", value="10288")
            
            submit_new = st.form_submit_button("Firma in Datenbank anlegen")
            
            if submit_new:
                if not new_code or not new_name:
                    st.error("Bitte Code und Firmenname ausfüllen!")
                else:
                    if supabase:
                        try:
                            supabase.table("company_profiles").insert({
                                "company_code": new_code,
                                "company_name": new_name,
                                "datev_user": d_user_new,
                                "datev_berater": d_berater_new,
                                "datev_klient": d_klient_new
                            }).execute()
                            st.success(f"Mandant '{new_code}' ({new_name}) wurde erfolgreich angelegt!")
                        except Exception as e:
                            st.error(f"Fehler beim Anlegen: {e}")
        st.stop()

if "selected_edit_date" not in st.session_state:
    st.session_state.selected_edit_date = None

if st.session_state.selected_edit_date:
    default_date_val = datetime.strptime(st.session_state.selected_edit_date, "%Y-%m-%d").date()
    st.session_state.selected_edit_date = None
else:
    default_date_val = datetime.today()

selected_date = st.sidebar.date_input("📅 Datum wählen", value=default_date_val)
date_str = selected_date.strftime("%Y-%m-%d")

# DATEN FÜR DIESEN MANDANTEN AUS SUPABASE LADEN
if "daily_sheets" not in st.session_state or st.session_state.get("active_company") != company_code_input:
    st.session_state.active_company = company_code_input
    st.session_state.daily_sheets = {}
    if supabase:
        try:
            sheets_res = supabase.table("daily_sheets").select("*").eq("company_code", company_code_input).execute()
            for row in sheets_res.data:
                st.session_state.daily_sheets[str(row["datum"])] = row
        except Exception:
            pass

prev_date_str = (selected_date - timedelta(days=1)).strftime("%Y-%m-%d")
auto_anfangsstand = 0.0
if prev_date_str in st.session_state.daily_sheets:
    auto_anfangsstand = float(st.session_state.daily_sheets[prev_date_str]["endstand"])

if st.session_state.get("current_date_str") != date_str:
    st.session_state.current_date_str = date_str
    if date_str in st.session_state.daily_sheets:
        saved = st.session_state.daily_sheets[date_str]
        st.session_state.inp_anfangsstand = float(saved.get("anfangsstand", 0.0))
        st.session_state.inp_tageslosung = float(saved.get("tageslosung", 0.0))
        st.session_state.inp_bareinlage = float(saved.get("bareinlage", 0.0))
        # Alte Tagesblätter hatten zwei Felder. Für die neue einzelne Eingabe
        # werden beide vorhandenen Beträge addiert.
        st.session_state.inp_bar_boniert_gesamt = (
            float(saved.get("bar_boniert", 0.0) or 0.0)
            + float(saved.get("essensbons_ueberweisung", 0.0) or 0.0)
        )
        st.session_state.inp_bankomatkasse = float(saved.get("bankomatkasse", 0.0))
        st.session_state.inp_unbar_ueb = float(saved.get("unbar_ueberweisung", 0.0))
        st.session_state.inp_essenbons = float(saved.get("essenbons", 0.0))
        st.session_state.inp_trinkgeld_ma = float(saved.get("trinkgeld_ma", 0.0))
        st.session_state.inp_gaestereklamation = float(saved.get("gaestereklamation", 0.0))
        st.session_state.inp_barentnahme = float(saved.get("barentnahme", 0.0))
        st.session_state.inp_loehne_vorschuesse = float(saved.get("loehne_vorschuesse", 0.0))
        st.session_state.inp_einzahlung_bank = float(saved.get("einzahlung_bank", 0.0))
        st.session_state.inp_notes_dict = saved.get("notes", {}) or {}
    else:
        st.session_state.inp_anfangsstand = float(auto_anfangsstand)
        st.session_state.inp_tageslosung = 0.0
        st.session_state.inp_bareinlage = 0.0
        st.session_state.inp_bar_boniert_gesamt = 0.0
        st.session_state.inp_bankomatkasse = 0.0
        st.session_state.inp_unbar_ueb = 0.0
        st.session_state.inp_essenbons = 0.0
        st.session_state.inp_trinkgeld_ma = 0.0
        st.session_state.inp_gaestereklamation = 0.0
        st.session_state.inp_barentnahme = 0.0
        st.session_state.inp_loehne_vorschuesse = 0.0
        st.session_state.inp_einzahlung_bank = 0.0
        st.session_state.inp_notes_dict = {}

if "temp_receipts" not in st.session_state:
    st.session_state.temp_receipts = {}

if date_str not in st.session_state.temp_receipts:
    existing_saved = st.session_state.daily_sheets.get(date_str, {})
    st.session_state.temp_receipts[date_str] = existing_saved.get("receipt_items", []) or []

st.sidebar.divider()

# --- FIRMEN-STAMMDATEN ---
with st.sidebar.expander("⚙️ Steuerberater-Stammdaten (DATEV/BMD)"):
    p_name = st.text_input("Firmenname", value=profile_data.get("company_name", company_code_input))
    d_user = st.text_input("DATEV Benutzer", value=profile_data.get("datev_user", "user"))
    d_berater = st.text_input("Beraternummer", value=profile_data.get("datev_berater", "503865"))
    d_klient = st.text_input("Mandantennummer", value=profile_data.get("datev_klient", "10288"))
    
    if st.button("💾 Stammdaten dauerhaft speichern"):
        if supabase:
            try:
                supabase.table("company_profiles").update({
                    "company_name": p_name,
                    "datev_user": d_user,
                    "datev_berater": d_berater,
                    "datev_klient": d_klient
                }).eq("company_code", company_code_input).execute()
                st.success("Stammdaten in Datenbank gesichert!")
                st.rerun()
            except Exception as e:
                st.error(f"Fehler beim Speichern: {e}")

# ERFASSTE TAGESBLÄTTER
with st.sidebar.expander("📁 Erfasste Tagesblätter (Bearbeiten)"):
    if len(st.session_state.daily_sheets) > 0:
        df_side = pd.DataFrame(list(st.session_state.daily_sheets.values()))
        df_side["Datum_Obj"] = pd.to_datetime(df_side["datum"])
        df_side = df_side.sort_values("Datum_Obj", ascending=False).reset_index(drop=True)
        
        for _, r in df_side.iterrows():
            d_val = str(r["datum"])
            end_val = float(r["endstand"])
            col_d_txt, col_d_btn = st.columns([2, 1])
            col_d_txt.text(f"{d_val} ({end_val:.2f}€)")
            if col_d_btn.button("✏️", key=f"edit_btn_{d_val}"):
                st.session_state.selected_edit_date = d_val
                st.rerun()
    else:
        st.info("Noch keine Daten erfasst.")

# STEUERBERATER-SCHNITTSTELLE & EXPORTE
with st.sidebar.expander("📊 Steuerberater-Schnittstelle & Exporte"):
    if len(st.session_state.daily_sheets) > 0:
        df_sb = pd.DataFrame(list(st.session_state.daily_sheets.values()))
        df_sb["Datum_Obj"] = pd.to_datetime(df_sb["datum"])
        df_sb = df_sb.sort_values("Datum_Obj").reset_index(drop=True)
        
        pdf_mode = st.radio("PDF-Typ:", ["Einzel-Tag", "Zeitraum"], horizontal=True)
        if pdf_mode == "Einzel-Tag":
            chosen_date_pdf = st.selectbox("Datum", df_sb["datum"].tolist(), key="sb_pdf_single")
            if chosen_date_pdf:
                sub_df = df_sb[df_sb["datum"] == chosen_date_pdf]
                pdf_buf = generate_multi_day_pdf(sub_df)
                st.download_button("📥 Tages-PDF laden", pdf_buf, file_name=f"Tageskassabuch_{chosen_date_pdf}.pdf", mime="application/pdf")
        else:
            col_p1, col_p2 = st.columns(2)
            p_start = col_p1.date_input("Von", value=df_sb["Datum_Obj"].min().date(), key="sb_p_start")
            p_end = col_p2.date_input("Bis", value=df_sb["Datum_Obj"].max().date(), key="sb_p_end")
            mask_pdf = (df_sb["Datum_Obj"].dt.date >= p_start) & (df_sb["Datum_Obj"].dt.date <= p_end)
            period_pdf_df = df_sb.loc[mask_pdf]
            if not period_pdf_df.empty:
                period_pdf_buffer = generate_multi_day_pdf(period_pdf_df)
                st.download_button(f"📥 Zeitraum-PDF laden", period_pdf_buffer, file_name=f"Kassabuch_{company_code_input}_{p_start}_bis_{p_end}.pdf", mime="application/pdf")

    st.markdown("---")
    if len(st.session_state.daily_sheets) > 0:
        col_s1, col_s2 = st.columns(2)
        e_start = col_s1.date_input("Von", value=df_sb["Datum_Obj"].min().date(), key="sb_e_start")
        e_end = col_s2.date_input("Bis", value=df_sb["Datum_Obj"].max().date(), key="sb_e_end")
        
        mask_exp = (df_sb["Datum_Obj"].dt.date >= e_start) & (df_sb["Datum_Obj"].dt.date <= e_end)
        df_exp_p = df_sb.loc[mask_exp]
        
        if not df_exp_p.empty:
            datev_txt = generate_datev_at_csv(df_exp_p, d_user, d_berater, d_klient, e_start, e_end)
            st.download_button("📥 DATEV EXTF (.csv)", datev_txt.encode("cp1252", errors="replace"), file_name=f"EXTF_{company_code_input}.csv", mime="text/csv")
            
            bmd_txt = generate_bmd_at_csv(df_exp_p)
            if bmd_txt:
                st.download_button("📥 BMD Export (.csv)", bmd_txt, file_name=f"BMD_{company_code_input}.csv", mime="text/csv")

# BELEG-UPLOAD
with st.sidebar.expander("📸 Einkaufsbelege hochladen"):
    uploaded_single_file = st.file_uploader("Beleg auswählen (PNG, JPG)", type=["png", "jpg", "jpeg"], key=f"uploader_key_{date_str}")

    if uploaded_single_file is not None:
        pil_img = Image.open(uploaded_single_file).convert('RGB')
        st.image(pil_img, caption=uploaded_single_file.name, use_container_width=True)
        input_beleg_betrag = st.number_input("Rechnungsbetrag (€)", value=0.0, step=5.0, format="%.2f", key=f"amt_{uploaded_single_file.name}")
        col_btn1, col_btn2 = st.columns(2)
        if col_btn1.button("✅ Ablegen"):
            file_path = os.path.join(UPLOAD_DIR, f"{company_code_input}_{date_str}_{datetime.now().strftime('%H%M%S')}_{uploaded_single_file.name}")
            pil_img.save(file_path)
            st.session_state.temp_receipts[date_str].append({
                "path": file_path, "amount": input_beleg_betrag, "name": uploaded_single_file.name
            })
            st.success("Beleg gespeichert!")
            st.rerun()
        if col_btn2.button("❌ Verwerfen"):
            st.rerun()

    current_receipts = st.session_state.temp_receipts.get(date_str, [])
    calculated_total_einkauf = sum(float(r["amount"]) for r in current_receipts)

    if current_receipts:
        for idx, rec in enumerate(current_receipts):
            c_txt, c_del = st.columns([3, 1])
            c_txt.text(f"• {rec['name']} ({float(rec['amount']):.2f} €)")
            if c_del.button("🗑️", key=f"del_{date_str}_{idx}"):
                current_receipts.pop(idx)
                st.rerun()

# --- HAUPTBEREICH: DIREKTE ECHTZEIT-EINGABEMASKE ---
st.title(f"💶 Tages-Kassabuch: {profile_data.get('company_name', company_code_input)}")
st.markdown(f"### Tagesblatt für den **{selected_date.strftime('%d.%m.%Y')}**")

saved_einkauf = st.session_state.daily_sheets.get(date_str, {}).get("einkauf", 0.0)
final_einkauf = calculated_total_einkauf if calculated_total_einkauf > 0 else float(saved_einkauf)

header_container = st.container()

anfangsstand = float(st.session_state.get("inp_anfangsstand", auto_anfangsstand))
tageslosung = float(st.session_state.get("inp_tageslosung", 0.0))
bareinlage = float(st.session_state.get("inp_bareinlage", 0.0))
bar_boniert_gesamt = float(st.session_state.get("inp_bar_boniert_gesamt", 0.0))

bankomatkasse = float(st.session_state.get("inp_bankomatkasse", 0.0))
unbar_ueb = float(st.session_state.get("inp_unbar_ueb", 0.0))
essenbons = float(st.session_state.get("inp_essenbons", 0.0))
trinkgeld_ma = float(st.session_state.get("inp_trinkgeld_ma", 0.0))
gaestereklamation = float(st.session_state.get("inp_gaestereklamation", 0.0))
einkauf = final_einkauf
barentnahme = float(st.session_state.get("inp_barentnahme", 0.0))
loehne_vorschuesse = float(st.session_state.get("inp_loehne_vorschuesse", 0.0))
einzahlung_bank = float(st.session_state.get("inp_einzahlung_bank", 0.0))

live_zwischenstand = (anfangsstand + tageslosung + bareinlage + bar_boniert_gesamt
                     - bankomatkasse - unbar_ueb - essenbons - trinkgeld_ma 
                     - gaestereklamation - einkauf - barentnahme - loehne_vorschuesse)
live_endstand = live_zwischenstand - einzahlung_bank

with header_container:
    st.markdown('<div class="sticky-header-marker"></div>', unsafe_allow_html=True)
    m_col1, m_col2, m_col3, btn_col = st.columns([1, 1, 1, 1.2])
    
    m_col1.metric("Anfangsstand", f"{anfangsstand:.2f} €")
    m_col2.metric("Zwischenstand", f"{live_zwischenstand:.2f} €")
    m_col3.metric("🔴 LIVE-KASSENSTAND", f"{live_endstand:.2f} €", delta=f"{live_endstand - anfangsstand:.2f} €")
    
    with btn_col:
        st.write("")
        save_trigger = st.button("💾 Tagesblatt in Cloud speichern", type="primary", use_container_width=True)

st.markdown("---")
st.markdown("#### 1. Einnahmen & Hinzurechnungen")

col1, col2 = st.columns([1, 1])
with col1:
    anfangsstand = st.number_input("Anfangsstand - Übertrag v. Vortag (€)", key="inp_anfangsstand", step=10.0)
with col2:
    note_anfangsstand = st.text_input("Bemerkung zu Anfangsstand", value=st.session_state.inp_notes_dict.get("anfangsstand", ""), key="note_anfangsstand")

col1, col2 = st.columns([1, 1])
with col1:
    tageslosung = st.number_input("Tageslosung (Brutto) (€)", key="inp_tageslosung", step=10.0)
with col2:
    note_tageslosung = st.text_input("Bemerkung zu Tageslosung", value=st.session_state.inp_notes_dict.get("tageslosung", ""), key="note_tageslosung")

col1, col2 = st.columns([1, 1])
with col1:
    bareinlage = st.number_input("Bareinlage (➕ Hinzurechnung) (€)", key="inp_bareinlage", step=10.0)
with col2:
    note_bareinlage = st.text_input("Bemerkung / Grund für Bareinlage", value=st.session_state.inp_notes_dict.get("bareinlage", ""), key="note_bareinlage")

col1, col2 = st.columns([1, 1])
with col1:
    bar_boniert_gesamt = st.number_input(
        "bar kassiert bereits bonierte Essensbons oder Überweisung (€)",
        key="inp_bar_boniert_gesamt", step=10.0
    )
with col2:
    alte_bemerkung = (
        st.session_state.inp_notes_dict.get("bar_boniert_essensbons_ueberweisung", "")
        or st.session_state.inp_notes_dict.get("bar_boniert", "")
        or st.session_state.inp_notes_dict.get("essensbons_ueb", "")
    )
    note_bar_boniert_gesamt = st.text_input(
        "Bemerkung zu bar kassiert / Essensbons / Überweisung",
        value=alte_bemerkung, key="note_bar_boniert_gesamt"
    )

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
        "bar_boniert_essensbons_ueberweisung": note_bar_boniert_gesamt,
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
        "bar_boniert": bar_boniert_gesamt,
        "essensbons_ueberweisung": 0.0,
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