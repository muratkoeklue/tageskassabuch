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
            ["bar kassiert bereits bonierte", f"{float(data['bar_boniert']):.2f}", notes.get("bar_boniert", "")],
            ["Essensbons oder Überweisung", f"{float(data['essensbons_ueberweisung']):.2f}", notes.get("essensbons_ueb", "")],
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
    start_str = start_d.strftime("%Y%m%d")
    end_str = end_d.strftime("%Y%m%d")
    wj_beginn = f"{start_d.year}0101"
    now_str = datetime.now().strftime("%Y%m%d%H%M%S")
    
    header_cols = [
        "EXTF", "510", "21", "Buchungsstapel", "12", now_str, "", 
        user_val, "", "", berater_val, klient_val, wj_beginn, "", 
        start_str, end_str, "1", "0", "0", "EUR"
    ]
    lines = [";".join(header_cols)]
    
    for _, r in period_df.iterrows():
        datum_fmt = pd.to_datetime(r["datum"]).strftime("%d%m")
        belegfeld = str(r["datum"]).replace("-", "")
        
        if float(r["tageslosung"]) > 0:
            val_str = f"{float(r['tageslosung']):.2f}".replace('.', ',')
            lines.append(f"{val_str};S;EUR;;{datum_fmt};;{belegfeld};Tageslosung {r['datum']};4000;2700")
            
        if float(r.get("bareinlage", 0.0)) > 0:
            val_str = f"{float(r['bareinlage']):.2f}".replace('.', ',')
            lines.append(f"{val_str};S;EUR;;{datum_fmt};;{belegfeld};Bareinlage {r['datum']};9000;2700")

        if float(r["einkauf"]) > 0:
            val_str = f"{float(r['einkauf']):.2f}".replace('.', ',')
            lines.append(f"{val_str};H;EUR;;{datum_fmt};;{belegfeld};Einkauf / Barauslagen {r['datum']};5000;2700")
            
        if float(r.get("barentnahme", 0.0)) > 0:
            val_str = f"{float(r['barentnahme']):.2f}".replace('.', ',')
            lines.append(f"{val_str};H;EUR;;{datum_fmt};;{belegfeld};Barentnahme {r['datum']};9000;2700")

        if float(r["loehne_vorschuesse"]) > 0:
            val_str = f"{float(r['loehne_vorschuesse']):.2f}".replace('.', ',')
            lines.append(f"{val_str};H;EUR;;{datum_fmt};;{belegfeld};Mitarbeiter Löhne/Vorschüsse {r['datum']};3700;2700")
            
        if float(r["einzahlung_bank"]) > 0:
            val_str = f"{float(r['einzahlung_bank']):.2f}".replace('.', ',')
            lines.append(f"{val_str};H;EUR;;{datum_fmt};;{belegfeld};Bank-Einzahlung {r['datum']};2800;2700")
            
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
                "Belegdatum": datum_fmt, "Belegnummer": r["datum"].replace("-", ""),
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

# Prüfen ob eingeloggter Nutzer Administrator ist
is_admin = (company_code_input == "KASSABUCH-ADMIN")

# --- ADMIN BEREICH (WENN ADMIN EINGELOGGT) ---
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
        st.stop() # Stoppt die normale Kassa-Ansicht, damit der Admin komfortabel anlegen kann

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
        st.session_state.inp_bar_boniert = float(saved.get("bar_boniert", 0.0))
        st.session_state.inp_essensbons_ueb = float(saved.get("essensbons_ueberweisung", 0.0))
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
        st.session_state.inp_bar_boniert = 0.0
        st.session_state.inp_essensbons_ueb = 0.0
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
    st.caption("Einmalig eingeben – bleibt dauerhaft für diesen Unternehmens-Code gespeichert!")
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

# ERFASSTE TAGESBLÄTTER (BEARBEITEN)
with st.sidebar.expander("📁 Erfasste Tagesblätter (Bearbeiten)"):
    if len(st.session_state.daily_sheets) > 0:
        df_side = pd.DataFrame(list(st.session_state.daily_sheets.values()))
        df_side["Datum_Obj"] = pd.to_datetime(df_side["datum"])
        df_side = df_side.sort_values("Datum_Obj", ascending=False).reset_index(drop=True)
        
        st.markdown("Wähle einen Tag zum Bearbeiten:")
        for _, r in df_side.iterrows():
            d_val = str(r["datum"])
            end_val = float(r["endstand"])
            col_d_txt, col_d_btn = st.columns([2, 1])
            col_d_txt.text(f"{d_val} ({end_val:.2f}€)")
            if col_d_btn.button("✏️ Laden", key=f"edit_btn_{d_val}"):
                st.session_state.selected_edit_date = d_val
                st.rerun()
    else:
        st.info("Noch keine Daten erfasst.")

# STEUERBERATER-SCHNITTSTELLE & EXPORTE
with st.sidebar.expander("📊 Steuerberater-Schnittstelle & Exporte"):
    st.markdown("##### 📄 PDF-Protokolle erstellen")
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
                st.download_button(f"📥 Zeitraum-PDF laden ({len(period_pdf_df)} Tage)", period_pdf_buffer, file_name=f"Kassabuch_{company_code_input}_{p_start}_bis_{p_end}.pdf", mime="application/pdf")
    else:
        st.info("Keine Daten vorhanden.")

    st.markdown("---")
    st.markdown("##### 📊 DATEV & BMD Exporte")
    if len(st.session_state.daily_sheets) > 0:
        col_s1, col_s2 = st.columns(2)
        e_start = col_s1.date_input("Von", value=df_sb["Datum_Obj"].min().date(), key="sb_e_start")
        e_end = col_s2.date_input("Bis", value=df_sb["Datum_Obj"].max().date(), key="sb_e_end")
        
        mask_exp = (df_sb["Datum_Obj"].dt.date >= e_start) & (df_sb["Datum_Obj"].dt.date <= e_end)
        df_exp_p = df_sb.loc[mask_exp]
        
        if not df_exp_p.empty:
            datev_txt = generate_datev_at_csv(df_exp_p, d_user, d_berater, d_klient, e_start, e_end)
            st.download_button("📥 DATEV EXTF (.csv)", datev_txt.encode("cp1252", errors="replace"), file_name=f"EXTF_Kassabuch_{company_code_input}_{e_start}_bis_{e_end}.csv", mime="text/csv")
            
            bmd_txt = generate_bmd_at_csv(df_exp_p)
            if bmd_txt:
                st.download_button("📥 BMD Export (.csv)", bmd_txt, file_name=f"BMD_Kassabuch_{company_code_input}_{e_start}_bis_{e_end}.csv", mime="text/csv")
    else:
        st.info("Keine Daten vorhanden.")

# BELEG-UPLOAD
with st.sidebar.expander("📸 Einkaufsbelege hochladen"):
    uploaded_single_file = st.file_uploader(
        "Beleg auswählen (PNG, JPG)", 
        type=["png", "jpg", "jpeg"],
        key=f"uploader_key_{date_str}"
    )

    if uploaded_single_file is not None:
        pil_img = Image.open(uploaded_single_file).convert('RGB')
        st.image(pil_img, caption=uploaded_single_file.name, use_container_width=True)
        input_beleg_betrag = st.number_input(
            "Rechnungsbetrag (€)", 
            value=0.0, step=5.0, format="%.2f",
            key=f"amt_{uploaded_single_file.name}"
        )
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
        st.markdown(f"**Belege des Tages ({len(current_receipts)}):**")
        for idx, rec in enumerate(current_receipts):
            c_txt, c_del = st.columns([3, 1])
            c_txt.text(f"• {rec['name']} ({float(rec['amount']):.2f} €)")
            if c_del.button("🗑️", key=f"del_{date_str}_{idx}"):
                current_receipts.pop(idx)
                st.rerun()

    st.markdown(f"👉 **Gesamteinkauf: {calculated_total_einkauf:.2f} €**")

# E-MAIL VERSAND
with st.sidebar.expander("✉️ E-Mail Versand"):
    if len(st.session_state.daily_sheets) > 0:
        df_m_all = pd.DataFrame(list(st.session_state.daily_sheets.values()))
        df_m_all["Datum_Obj"] = pd.to_datetime(df_m_all["datum"])
        
        m_start = st.date_input("Von", value=df_m_all["Datum_Obj"].min().date(), key="m_s")
        m_end = st.date_input("Bis", value=df_m_all["Datum_Obj"].max().date(), key="m_e")
        f_type = st.selectbox("Anhang:", ["Gesamt-PDF", "DATEV EXTF", "BMD CSV"])
        
        rec_mail = st.text_input("Empfänger E-Mail", value="")
        e_subj = st.text_input("Betreff", value=f"Kassabuch Export {company_code_input} ({m_start.strftime('%d.%m.%Y')} - {m_end.strftime('%d.%m.%Y')})")
        e_body = st.text_area("Text", value="Sehr geehrte Damen und Herren,\n\nanbei übersende ich das digitale Tageskassabuch.\n\nMit freundlichen Grüßen")

        st.markdown("--- *SMTP Server* ---")
        s_server = st.text_input("Server", value="smtp.gmail.com")
        s_port = st.number_input("Port", value=587)
        s_mail = st.text_input("Deine E-Mail", value="")
        s_pass = st.text_input("Passwort", type="password")

        if st.button("🚀 E-Mail senden"):
            if not rec_mail or not s_mail or not s_pass:
                st.error("Fehlende Zugangsdaten.")
            else:
                mask_m = (df_m_all["Datum_Obj"].dt.date >= m_start) & (df_m_all["Datum_Obj"].dt.date <= m_end)
                df_m_p = df_m_all.loc[mask_m]
                if not df_m_p.empty:
                    try:
                        msg = MIMEMultipart()
                        msg['From'] = s_mail
                        msg['To'] = rec_mail
                        msg['Subject'] = e_subj
                        msg.attach(MIMEText(e_body, 'plain'))

                        f_data, f_name = None, ""
                        if f_type == "Gesamt-PDF":
                            f_data = generate_multi_day_pdf(df_m_p).getvalue()
                            f_name = f"Kassabuch_{company_code_input}_{m_start}_bis_{m_end}.pdf"
                        elif f_type == "DATEV EXTF":
                            f_data = generate_datev_at_csv(df_m_p, d_user, d_berater, d_klient, m_start, m_end).encode("cp1252", errors="replace")
                            f_name = f"EXTF_Kassabuch_{company_code_input}_{m_start}_bis_{m