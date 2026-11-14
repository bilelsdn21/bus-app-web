# -*- coding: utf-8 -*-
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SP = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Cahier_des_charges_Bestimetravel.docx")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

NAVY = RGBColor(0x1A, 0x3A, 0x5C)
GOLD = RGBColor(0xB4, 0x53, 0x09)
SLATE = RGBColor(0x47, 0x55, 0x69)
GREEN = RGBColor(0x04, 0x78, 0x57)
AMBER = RGBColor(0xB4, 0x53, 0x09)
ROSE = RGBColor(0xBE, 0x12, 0x3C)

doc = Document()

# ------------------------------------------------------------------ page + styles
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.2)
sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)


def set_font(style, name="Calibri", size=None, bold=None, color=None):
    style.font.name = name
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), name)
    if size: style.font.size = Pt(size)
    if bold is not None: style.font.bold = bold
    if color is not None: style.font.color.rgb = color


set_font(doc.styles["Normal"], size=10.5)
doc.styles["Normal"].paragraph_format.space_after = Pt(5)
doc.styles["Normal"].paragraph_format.line_spacing = 1.12
for name, size, before, after in (("Heading 1", 18, 20, 8), ("Heading 2", 13.5, 14, 5), ("Heading 3", 11.5, 10, 3)):
    st = doc.styles[name]
    set_font(st, size=size, bold=True, color=NAVY)
    st.paragraph_format.space_before = Pt(before)
    st.paragraph_format.space_after = Pt(after)
    st.paragraph_format.keep_with_next = True
set_font(doc.styles["List Bullet"], size=10.5)
set_font(doc.styles["List Number"], size=10.5)
doc.styles["List Bullet"].paragraph_format.space_after = Pt(2)


# ------------------------------------------------------------------ helpers
def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def cell_margins(cell, top=60, bottom=60, left=90, right=90):
    tcPr = cell._tc.get_or_add_tcPr()
    m = OxmlElement("w:tcMar")
    for k, v in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        e = OxmlElement(f"w:{k}"); e.set(qn("w:w"), str(v)); e.set(qn("w:type"), "dxa"); m.append(e)
    tcPr.append(m)


def table_borders(table, color="CBD5E1", sz=4):
    tblPr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(sz)); e.set(qn("w:space"), "0"); e.set(qn("w:color"), color)
        b.append(e)
    tblPr.append(b)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    h = OxmlElement("w:tblHeader"); h.set(qn("w:val"), "true"); trPr.append(h)


def no_split(row):
    trPr = row._tr.get_or_add_trPr()
    c = OxmlElement("w:cantSplit"); c.set(qn("w:val"), "true"); trPr.append(c)


def add_runs(par, text, size=None, color=None, bold=None):
    """**bold** segments supported."""
    parts = text.split("**")
    for i, part in enumerate(parts):
        if not part:
            continue
        r = par.add_run(part)
        r.bold = True if (i % 2 == 1) else bold
        if size: r.font.size = Pt(size)
        if color is not None: r.font.color.rgb = color
    return par


def P(text="", size=None, color=None, bold=None, align=None, after=None, italic=False):
    p = doc.add_paragraph()
    add_runs(p, text, size, color, bold)
    if italic:
        for r in p.runs: r.italic = True
    if align: p.alignment = align
    if after is not None: p.paragraph_format.space_after = Pt(after)
    return p


def B(text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    add_runs(p, text)
    if level: p.paragraph_format.left_indent = Cm(0.63 + 0.6 * level)
    return p


def N(text):
    p = doc.add_paragraph(style="List Number")
    add_runs(p, text)
    p.paragraph_format.space_after = Pt(2)
    return p


def H1(t): return doc.add_heading(t, 1)
def H2(t): return doc.add_heading(t, 2)
def H3(t): return doc.add_heading(t, 3)


STATUS_COL = {"Réalisé": GREEN, "Partiel": AMBER, "Prévu": SLATE, "Must": ROSE, "Should": AMBER, "Could": SLATE}


def T(headers, rows, widths, size=9, zebra=True, bold_first=False, hdr="1A3A5C", status_cols=()):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    table_borders(t)
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.width = Cm(widths[i]); shade(c, hdr); cell_margins(c)
        c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(0); p.paragraph_format.keep_with_next = True
        r = p.add_run(h); r.bold = True; r.font.size = Pt(size); r.font.color.rgb = RGBColor(255, 255, 255)
    repeat_header(t.rows[0])
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        no_split(t.rows[-1])
        for i, val in enumerate(row):
            c = cells[i]; c.width = Cm(widths[i]); cell_margins(c)
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            if zebra and ri % 2 == 1: shade(c, "F1F5F9")
            lines = str(val).split("\n")
            for li, line in enumerate(lines):
                p = c.paragraphs[0] if li == 0 else c.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                if ri == 0: p.paragraph_format.keep_with_next = True
                col = STATUS_COL.get(line.strip()) if i in status_cols else None
                add_runs(p, line, size=size, color=col, bold=True if (col is not None or (bold_first and i == 0)) else None)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def callout(text, fill="FEF3C7", bar="F59E0B", title=None):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    c = t.rows[0].cells[0]; c.width = Cm(16.6); shade(c, fill); cell_margins(c, 110, 110, 160, 140)
    tcPr = c._tc.get_or_add_tcPr()
    b = OxmlElement("w:tcBorders")
    e = OxmlElement("w:left"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "36"); e.set(qn("w:space"), "0"); e.set(qn("w:color"), bar)
    b.append(e); tcPr.append(b)
    p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(2)
    if title:
        r = p.add_run(title); r.bold = True; r.font.size = Pt(10.5); r.font.color.rgb = NAVY
        p = c.add_paragraph(); p.paragraph_format.space_after = Pt(0)
    add_runs(p, text, size=10)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def img(name, width_cm=16.2, caption=None):
    doc.add_picture(os.path.join(SP, name), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption:
        P(caption, size=9, color=SLATE, align=WD_ALIGN_PARAGRAPH.CENTER, italic=True)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def field(run, instr):
    for kind, text in (("begin", None), (None, instr), ("end", None)):
        if kind:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), kind); run._r.append(e)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = text; run._r.append(e)


# ------------------------------------------------------------------ footer
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = fp.add_run("Cahier des charges — Bestimetravel · Gestion des Bus · v1.0      Page ")
r.font.size = Pt(8.5); r.font.color.rgb = SLATE
r2 = fp.add_run(); r2.font.size = Pt(8.5); r2.font.color.rgb = SLATE; field(r2, "PAGE")

# ================================================================== COVER
band = doc.add_table(rows=1, cols=1); band.alignment = WD_TABLE_ALIGNMENT.CENTER; band.autofit = False
c = band.rows[0].cells[0]; c.width = Cm(16.6); shade(c, "1A3A5C"); cell_margins(c, 700, 700, 400, 400)
p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(6)
r = p.add_run("CAHIER DES CHARGES"); r.bold = True; r.font.size = Pt(30); r.font.color.rgb = RGBColor(255, 255, 255)
p = c.add_paragraph(); p.paragraph_format.space_after = Pt(0)
r = p.add_run("Application web de gestion de flotte de bus"); r.font.size = Pt(15); r.font.color.rgb = RGBColor(0xFC, 0xD3, 0x4D)
doc.add_paragraph().paragraph_format.space_after = Pt(30)

P("Bestimetravel — Gestion des Bus", size=22, color=NAVY, bold=True, after=2)
P("Suivi des véhicules, des contrats, du carburant et de la rentabilité, sur téléphone comme sur ordinateur", size=12, color=SLATE, after=26)

T(["", ""], [
    ["Projet", "Bestimetravel · Gestion des Bus (application web progressive, PWA)"],
    ["Version", "1.0 — Novembre 2026"],
    ["Réalisé par", "Bilel"],
    ["Application en ligne", "https://bus-app-web-lemon.vercel.app"],
    ["Code source", "https://github.com/bilelsdn21/bus-app-web"],
    ["Technologies", "React · TailwindCSS · FastAPI (Python) · PostgreSQL (Supabase) · Vercel · Render"],
], [4.2, 12.4], size=10, zebra=False, bold_first=True, hdr="FFFFFF")
_cover = doc.tables[-1]
_cover._tbl.remove(_cover.rows[0]._tr)
page_break()

# ================================================================== SOMMAIRE
H1("Sommaire")
for n, t_ in [
    ("1", "Présentation du projet"), ("2", "Expression des besoins"), ("3", "Conception et architecture technique"),
    ("4", "Interface et ergonomie (mobile d'abord)"), ("5", "Qualité, tests et recette"), ("6", "Planning et organisation"),
    ("7", "Budget et hébergement"), ("8", "Risques et limites connues"), ("9", "Évolutions prévues"),
    ("10", "Livrables et conditions de recette"),
    ("A", "Annexe — Glossaire"), ("B", "Annexe — Guide rapide utilisateur"), ("C", "Annexe — Configuration et installation"),
    ("D", "Annexe — Trame de soutenance et scénario de démonstration"),
]:
    p = P(f"**{n}.**  {t_}", after=3)
    p.paragraph_format.left_indent = Cm(0.4)
page_break()

# ================================================================== 1
H1("1. Présentation du projet")
callout("**23 fonctions sur 25** livrées (2 prévues) · **3 rôles** d'accès · **10 exports** Excel · **24 tests** automatiques · "
        "calendrier chargé avec **8 requêtes au lieu de 52** · hébergement à **0 TND par mois** · installable sur téléphone (PWA).",
        fill="E0F2FE", bar="1A3A5C", title="L'essentiel en une phrase")
H2("1.1 Contexte")
P("Bestimetravel exploite une flotte de bus, minibus et autocars (types **MICRO**, **OTOKAR** et **BUS**) répartie sur plusieurs "
  "régions de Tunisie, notamment **Sousse** et **Djerba**. Chaque véhicule est exploité dans le cadre d'un **contrat** assorti d'un "
  "loyer. Les **sorties** (excursions, transferts) que le véhicule effectue génèrent le chiffre d'affaires ; le carburant constitue "
  "la principale charge variable.")
P("Jusqu'ici, ce suivi reposait sur un classeur Excel avec des macros VBA, puis sur un prototype Streamlit. L'application décrite "
  "dans ce document remplace ce fonctionnement par un véritable système d'information accessible en ligne.")
H2("1.2 Problématique")
T(["Limite de l'ancien fonctionnement", "Conséquence"], [
    ["Rattachement d'une sortie à un véhicule par son **nom** (texte)", "Une simple différence de nom a mal affecté des recettes : **1 440 TND perdus** lors d'un incident réel"],
    ["Macros VBA fragiles (erreurs de compilation, sécurité des macros)", "Fichier parfois inutilisable, dépendance à un poste unique"],
    ["Aucun accès fiable depuis le terrain (téléphone)", "Saisie différée, oublis, informations obsolètes"],
    ["Carburant saisi par mois civil alors que les contrats ont des dates libres", "Calcul manuel du résultat réel d'un contrat, source d'erreurs"],
    ["Aucune traçabilité des modifications", "Impossible de savoir qui a changé quoi, et quand"],
    ["Véhicules qui changent de région en cours de mois", "Chiffres attribués à la mauvaise région, totaux incohérents"],
], [8.3, 8.3])
H2("1.3 Objectifs")
T(["N°", "Objectif", "Indicateur de réussite"], [
    ["O1", "Fiabiliser tous les calculs (source unique de vérité, intégrité des données)", "Aucune erreur d'affectation possible (clés étrangères) ; 24 tests automatiques au vert"],
    ["O2", "Rendre l'outil utilisable partout, surtout sur téléphone", "Application installable, vue « cartes » mobile, saisie d'un jour en quelques touchers"],
    ["O3", "Donner la rentabilité par véhicule, contrat et région, en temps réel", "Net, pourcentage et totaux régionaux affichés dès le chargement du calendrier"],
    ["O4", "Assurer la traçabilité et le contrôle des accès", "Journal d'activité complet ; trois niveaux de droits"],
    ["O5", "Être rapide", "Calendrier du mois affiché en environ 1 à 2 secondes en régime normal"],
    ["O6", "Faciliter la communication avec l'équipe", "Notifications push (résumé du mois, annonces)"],
], [1.2, 8.2, 7.2])
H2("1.4 Périmètre")
T(["Inclus dans le projet", "Hors périmètre (évolutions possibles)"], [
    ["Gestion des véhicules, contrats, carburant, destinations et tarifs\n"
     "Calendrier mensuel et saisie des sorties\n"
     "Régions datées et changements de région ou de contrat en cours de mois\n"
     "Véhicules loués en renfort et vérification d'alternative\n"
     "Analyse mensuelle (occupation, couverture du loyer)\n"
     "Exports Excel, journal d'audit, notifications push\n"
     "Application installable (PWA), vue mobile",
     "Facturation client et émission de factures PDF\n"
     "Comptabilité générale, paie des chauffeurs\n"
     "Suivi GPS / télématique des véhicules\n"
     "Paiement en ligne, portail client\n"
     "Application native publiée sur les magasins d'applications\n"
     "Gestion des comptes utilisateurs depuis l'interface (les comptes sont aujourd'hui définis côté serveur)"],
], [8.3, 8.3], zebra=False)
H2("1.5 Utilisateurs et rôles")
T(["Rôle", "Qui", "Droits"], [
    ["**Propriétaire** (owner)", "Direction", "Tous les droits de l'administrateur, plus la supervision : journal complet incluant les connexions et déconnexions"],
    ["**Administrateur** (admin)", "Gestionnaires, exploitation", "Lecture et écriture : saisie des sorties, contrats, carburant, véhicules, tarifs, régions ; analyse ; exports ; envoi d'annonces ; journal des modifications"],
    ["**Lecture seule** (viewer)", "Équipe, consultation", "Consultation du calendrier, des contrats, des véhicules loués et des paramètres. Aucune modification possible (refusée aussi côté serveur)"],
], [3.9, 3.7, 9.0])

# ================================================================== 2
H1("2. Expression des besoins")
H2("2.1 Besoins fonctionnels")
P("Priorité selon la méthode MoSCoW (**Must** = indispensable, **Should** = important, **Could** = souhaitable). "
  "L'état correspond à la version 1.0 livrée.", size=10)
F = [
 ["F01", "Authentification", "Connexion par identifiant et mot de passe ; jeton signé avec expiration ; déconnexion", "Must", "Réalisé"],
 ["F02", "Rôles et droits", "Trois rôles (propriétaire, administrateur, lecture seule) ; toute écriture est contrôlée côté serveur", "Must", "Réalisé"],
 ["F03", "Calendrier mensuel", "Grille véhicules × jours avec pastilles de couleur, net du mois, pourcentage, regroupement par région, totaux", "Must", "Réalisé"],
 ["F04", "Vue « cartes » mobile", "Une carte par véhicule avec mini-calendrier du mois ; bascule Cartes / Tableau ; ouverture sur aujourd'hui", "Should", "Réalisé"],
 ["F05", "Saisie d'un jour", "Ajout, modification, suppression des sorties d'un véhicule pour un jour : catégorie, destination, heures, client, passagers, prix calculé automatiquement", "Must", "Réalisé"],
 ["F06", "Sorties sur plusieurs jours", "Une excursion peut couvrir une période ; le jour apparaît « réservé »", "Must", "Réalisé"],
 ["F07", "Indisponibilités", "Entretien, Libre, Repos chauffeur : le véhicule est marqué indisponible ou libre", "Must", "Réalisé"],
 ["F08", "Contrôle de couverture", "Impossible de saisir une sortie un jour non couvert par un contrat", "Must", "Réalisé"],
 ["F09", "Contrats", "Période libre (dates quelconques), loyer, libellé ; résultat du contrat (recette − loyer − carburant)", "Must", "Réalisé"],
 ["F10", "Carburant", "Carburant mensuel par véhicule : estimé, puis réel ; réparti au prorata des jours du contrat", "Must", "Réalisé"],
 ["F11", "Véhicules", "Création, modification, suppression protégée ; type, plaque, région, distance, ordre d'affichage", "Must", "Réalisé"],
 ["F12", "Régions datées", "Historique de région par véhicule ; enregistrement d'un déplacement à une date sans modifier le passé", "Must", "Réalisé"],
 ["F13", "Changement en cours de mois", "Un véhicule qui change de région ou de contrat au milieu du mois apparaît une fois par région, avec ses propres jours et son propre résultat (Calendrier et Analyse)", "Must", "Réalisé"],
 ["F14", "Destinations et tarifs", "Catalogue de destinations avec prix par type de véhicule (MICRO, OTOKAR, BUS)", "Must", "Réalisé"],
 ["F15", "Périodes de prix", "Prix historiques par période, appliqués automatiquement selon la date de la sortie", "Should", "Réalisé"],
 ["F16", "Véhicules loués en renfort", "Location externe avec coût réparti au prorata sur les mois concernés ; total informatif sur le calendrier", "Should", "Réalisé"],
 ["F17", "Vérification d'alternative", "Pour une location, indique jour par jour si un véhicule propre du même type était libre dans la région", "Could", "Réalisé"],
 ["F18", "Analyse mensuelle", "Par véhicule : couverture du loyer, jours travaillés, taux d'occupation, heures d'activité ; même découpage que le calendrier en cas de changement de contrat ou de région", "Should", "Réalisé"],
 ["F19", "Exports Excel", "Calendrier, contrats, véhicules, destinations, régions, prix, locations, analyse, journal", "Must", "Réalisé"],
 ["F20", "Journal d'activité", "Qui a ajouté, modifié ou supprimé quoi, et quand ; connexions visibles du propriétaire uniquement", "Should", "Réalisé"],
 ["F21", "Notifications push", "Abonnement par téléphone ; annonces envoyées par un administrateur ; résumé du mois", "Should", "Réalisé"],
 ["F22", "Application installable", "PWA : icône sur l'écran d'accueil, plein écran, consultation hors ligne des dernières données", "Should", "Réalisé"],
 ["F23", "Paramètres", "Seuils horaires matin / soir / nuit (13 h et 22 h par défaut), date d'application des prix actuels", "Should", "Réalisé"],
 ["F24", "Gestion des comptes", "Création et modification des utilisateurs depuis l'interface", "Could", "Prévu"],
 ["F25", "Sauvegarde automatique", "Sauvegarde planifiée de la base (un script manuel existe)", "Should", "Prévu"],
]
T(["Réf.", "Fonction", "Description", "Priorité", "État"], F, [1.1, 3.0, 8.6, 1.7, 1.6], size=8.5, status_cols=(3, 4))


H2("2.2 Règles de gestion")
H3("R1 — Résultat d'un contrat")
P("**Résultat = recettes − loyer − carburant.** Les recettes sont la somme des sorties payantes dont la date tombe dans la période du contrat. "
  "Le pourcentage est le résultat divisé par le loyer.")
H3("R2 — Carburant réparti au prorata des jours")
P("Le carburant est saisi par **mois civil**, alors que les contrats ont des dates libres. Chaque mois contribue au prorata du nombre de jours "
  "qu'il partage avec le contrat. On utilise le montant **réel** s'il existe, sinon l'**estimation** ; le résultat est alors marqué « estimé ».")
callout("Contrat du 15 mai au 14 juin, loyer 5 000 TND. Carburant de mai (réel) 2 000 TND, de juin (estimé) 1 200 TND. Recettes : 12 270 TND.\n"
        "Carburant = 17/31 × 2 000 + 14/30 × 1 200 = 1 096,77 + 560,00 = **1 656,77 TND**\n"
        "Résultat = 12 270 − 5 000 − 1 656,77 = **5 613,23 TND (estimé)**",
        fill="E0F2FE", bar="1A3A5C", title="Exemple chiffré (vérifié par un test automatique)")
H3("R3 — Présence d'un véhicule au calendrier")
P("Un véhicule n'apparaît sur le calendrier d'un mois que si **au moins un contrat chevauche ce mois**. Les jours hors contrat sont grisés et ne peuvent pas recevoir de saisie.")
H3("R4 — Couleur d'un jour")
P("La couleur dépend de la **période de la journée** touchée par les sorties, d'après leurs heures de début et de fin. "
  "Les seuils (13 h et 22 h par défaut) sont modifiables dans les paramètres.")
col = doc.add_table(rows=1, cols=3); col.alignment = WD_TABLE_ALIGNMENT.CENTER; col.autofit = False; table_borders(col)
for i, (h, w) in enumerate((("Couleur", 3.2), ("Signification", 6.0), ("Condition", 7.4))):
    c = col.rows[0].cells[i]; c.width = Cm(w); shade(c, "1A3A5C"); cell_margins(c)
    r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(9); r.font.color.rgb = RGBColor(255, 255, 255)
for name, fill, sig, cond in [
    ("Jaune", "FBBF24", "Matin", "Sorties uniquement avant 13 h"),
    ("Orange", "F97316", "Soir", "Sorties entre 13 h et 22 h"),
    ("Violet", "8B5CF6", "Nuit", "Sorties après 22 h"),
    ("Vert", "10B981", "Réservé", "Excursion sur plusieurs jours, ou sorties couvrant plusieurs périodes de la journée"),
    ("Rouge", "F43F5E", "Indisponible", "Entretien ou repos chauffeur (sans sortie payante)"),
]:
    cells = col.add_row().cells
    for i, (txt, w) in enumerate(((name, 3.2), (sig, 6.0), (cond, 7.4))):
        cells[i].width = Cm(w); cell_margins(cells[i])
        rr = cells[i].paragraphs[0].add_run(txt); rr.font.size = Pt(9)
        cells[i].paragraphs[0].paragraph_format.space_after = Pt(0)
        if i == 0:
            shade(cells[i], fill); rr.bold = True; rr.font.color.rgb = RGBColor(255, 255, 255)
doc.add_paragraph().paragraph_format.space_after = Pt(2)
H3("R5 — Recette affectée à la date exacte")
P("Chaque sortie compte dans la région où se trouvait le véhicule **le jour de la sortie**. Rien n'est jamais déplacé rétroactivement.")
H3("R6 — Véhicule qui change de région dans un contrat")
P("Le contrat est découpé en tronçons d'une seule région. La **recette** de chaque tronçon est exacte ; le **loyer** et le **carburant** sont répartis "
  "au prorata des jours (ligne marquée « part »). Les tronçons additionnés redonnent exactement le total du contrat, au centime près.")
H3("R7 — Véhicule qui change de contrat en cours de mois")
P("Si les contrats du mois sont dans des régions différentes (par exemple contrat A à Sousse jusqu'au 12, contrat B à Djerba à partir du 13), "
  "le véhicule apparaît **une ligne par contrat, dans le bloc de sa région**. Chaque ligne a ses jours et son résultat ; les jours entre deux contrats restent grisés. "
  "Les totaux régionaux additionnent correctement tous les loyers.")
H3("R8 — Véhicule loué en renfort")
P("Le coût total d'une location est réparti **au prorata des jours** sur chaque mois qu'elle traverse. Il est affiché à titre d'information et n'est pas déduit du net de la flotte.")
H3("R9 — Noms de région normalisés")
P("« Djerba », « djerba » ou « Djerba » avec un espace en trop désignent la même région : les noms sont ramenés à une écriture unique à chaque lecture et à chaque enregistrement. "
  "Une région ne peut donc plus apparaître en double sur le calendrier.")

H2("2.3 Besoins non fonctionnels")
T(["Domaine", "Exigence", "Mise en œuvre / mesure"], [
    ["**Performance**", "Calendrier du mois affiché en 1 à 2 s en régime normal", "Chargement groupé : 52 requêtes SQL ramenées à 8 ; cache serveur ; réponses compressées ; cache navigateur avec affichage immédiat"],
    ["**Disponibilité**", "Application accessible 24 h / 24", "Hébergement gratuit avec mise en veille après 15 min : atténuée par une surveillance toutes les 5 min ; relances automatiques côté application"],
    ["**Sécurité**", "Accès contrôlé, données protégées", "Jeton signé et expirant, rôles contrôlés côté serveur, limitation des tentatives de connexion, HTTPS, en-têtes de sécurité, RLS sur la base (voir § 3.6)"],
    ["**Ergonomie mobile**", "Utilisable d'une main sur téléphone", "Barre d'onglets en bas, cartes par véhicule, boutons principaux d'au moins 44 px, zoom autorisé, champs en 16 px (pas de zoom automatique sur iPhone)"],
    ["**Compatibilité**", "Navigateurs et téléphones récents", "Chrome, Edge, Firefox, Safari récents ; Android ; iPhone (iOS 16.4 ou plus) pour les notifications, après ajout à l'écran d'accueil"],
    ["**Maintenabilité**", "Code lisible et testé", "Architecture en couches (MVC), un seul module de calcul, 24 tests automatiques, documentation (README, guide de déploiement)"],
    ["**Traçabilité**", "Savoir qui a fait quoi", "Journal d'activité de chaque ajout, modification, suppression, avec utilisateur et heure"],
    ["**Sobriété**", "Chargement léger sur réseau mobile", "Environ 75 Ko de code (compressé) ; aucune bibliothèque lourde"],
    ["**Portabilité**", "Développement local simple", "SQLite en local, PostgreSQL en production : même code, une variable d'environnement"],
], [3.0, 5.2, 8.4], size=8.8)

# ================================================================== 3
H1("3. Conception et architecture technique")
H2("3.1 Vue d'ensemble")
img("architecture.png", 15.2, "Figure 1 — Architecture technique")
P("L'utilisateur accède à une application **React** servie par Vercel. Celle-ci dialogue en HTTPS avec une **API FastAPI** hébergée à Francfort, "
  "qui lit et écrit dans une base **PostgreSQL** (Supabase, Stockholm). Les notifications passent par le service Push du navigateur. "
  "Un service de surveillance interroge régulièrement l'API pour qu'elle reste éveillée.")
H2("3.2 Choix techniques")
T(["Couche", "Technologie", "Justification"], [
    ["Interface", "React 18, Vite, TailwindCSS", "Composants réutilisables, build rapide, interface responsive sans CSS lourd"],
    ["API", "FastAPI (Python), Pydantic", "Validation automatique, documentation interactive (/docs), performances"],
    ["Accès aux données", "SQLAlchemy (ORM)", "Requêtes paramétrées (pas d'injection SQL), mêmes modèles en SQLite et PostgreSQL"],
    ["Base de données", "PostgreSQL (Supabase)", "Base relationnelle fiable, clés étrangères, hébergement gratuit"],
    ["Hébergement", "Vercel (interface), Render (API), Supabase (base)", "Déploiement automatique à chaque envoi sur GitHub ; coût nul"],
    ["Notifications", "Web Push (VAPID), pywebpush", "Standard ouvert, sans application native"],
    ["Exports", "openpyxl", "Fichiers Excel natifs, fidèles à l'habitude des utilisateurs"],
], [3.0, 5.6, 8.0], size=8.8)
H2("3.3 Architecture de l'API (MVC)")
T(["Couche", "Dossier", "Rôle"], [
    ["Modèle", "models.py", "Tables et relations (SQLAlchemy)"],
    ["Vue", "schemas.py", "Format des requêtes et réponses (Pydantic)"],
    ["Contrôleurs", "controllers/", "Un routeur par ressource : fines couches HTTP"],
    ["Services", "services/", "Logique métier : calc.py (calculs purs), calendar.py, contracts.py, analytics.py, lookups.py, rentals.py, push.py"],
    ["Cœur", "core/", "Base de données, sécurité et jetons, configuration, cache"],
], [3.0, 3.6, 10.0], size=8.8)
P("Le fichier **calc.py** est l'unique source des règles de calcul (net, pourcentage, prorata du carburant, couleurs) : aucune formule n'est dupliquée.")
H2("3.4 Modèle de données")
img("modele_donnees.png", 15.2, "Figure 2 — Modèle de données (simplifié)")
T(["Table", "Contenu", "Remarque"], [
    ["buses", "Véhicules : nom, plaque, type, région actuelle, distance, ordre", "Le nom est unique"],
    ["bookings", "Sorties et indisponibilités : date, fin, destination, client, passagers, prix, heures", "Liée au véhicule par **clé étrangère** (jamais par le nom)"],
    ["contracts", "Contrats : dates libres, loyer, libellé", "Plusieurs contrats possibles par véhicule"],
    ["fuel_months", "Carburant par véhicule et par mois : estimé, réel", "Unicité véhicule + année + mois"],
    ["region_periods", "Historique des régions : région, du … au …", "Les chevauchements sont refusés"],
    ["destinations / price_periods", "Catalogue et prix historiques par type de véhicule", "Prix retenu selon la date de la sortie"],
    ["rented_vehicles", "Locations externes de renfort", "Hors flotte : sans lien avec buses"],
    ["config", "Seuils horaires, date d'application des prix", "Ligne unique"],
    ["audit_log, push_subscriptions", "Journal des actions ; téléphones abonnés aux notifications", "—"],
], [4.2, 7.4, 5.0], size=8.8)
P("Données initiales migrées depuis l'ancien classeur : **23 véhicules**, **944 sorties**, **120 destinations**, ainsi que les contrats et le carburant.", size=10)
H2("3.5 Interface de programmation (API)")
T(["Groupe", "Principales routes", "Accès"], [
    ["Authentification", "POST /api/login · POST /api/logout", "Public (connexion) / connecté"],
    ["Calendrier et jours", "GET /api/calendar/{année}/{mois} · GET /api/day/… · POST /api/day · /api/excursions", "Lecture : connecté · Écriture : administrateur"],
    ["Véhicules et régions", "/api/buses · /api/buses/overview · /api/region-periods (+ /move)", "Lecture : connecté · Écriture : administrateur"],
    ["Contrats et carburant", "/api/contracts · /api/fuel", "Lecture : connecté · Écriture : administrateur"],
    ["Destinations et prix", "/api/destinations · /api/price-periods · /api/config", "Lecture : connecté · Écriture : administrateur"],
    ["Locations de renfort", "/api/rented-vehicles · /api/rented-vehicles/alternatives", "Lecture : connecté · Écriture : administrateur"],
    ["Analyse", "GET /api/analytics/{année}/{mois}", "Administrateur"],
    ["Exports", "GET /api/export/… (dix exports Excel)", "Connecté / administrateur"],
    ["Journal", "GET /api/audit (complet) · GET /api/audit/changes", "Propriétaire / administrateur"],
    ["Notifications", "/api/push/… · POST /api/notify/announce · /api/notify/test", "Connecté / administrateur"],
    ["Supervision", "GET /api/health · GET /api/health/db", "Public (état du service)"],
], [3.4, 8.6, 4.6], size=8.8)
H2("3.6 Sécurité")
T(["Mesure", "Détail"], [
    ["Authentification", "Jeton signé (HMAC-SHA256) contenant l'utilisateur et la date d'expiration ; invalidé automatiquement si le mot de passe change"],
    ["Contrôle des droits", "Vérifié **côté serveur** à chaque requête (lecture seule, administrateur, propriétaire) ; l'interface ne fait que refléter ces droits"],
    ["Protection contre les essais répétés", "6 échecs de connexion par adresse en 5 minutes, puis blocage temporaire ; les échecs sont journalisés"],
    ["Secrets", "Mots de passe, clés et adresse de la base uniquement dans des variables d'environnement, jamais dans le code"],
    ["Base de données", "Sécurité au niveau des lignes (RLS) activée sur toutes les tables ; connexion chiffrée ; requêtes paramétrées via l'ORM"],
    ["Transport et navigateur", "HTTPS partout ; origines autorisées limitées (CORS) ; en-têtes de sécurité (nosniff, anti-framing, pas de référent)"],
    ["Erreurs", "Les erreurs inattendues renvoient un message lisible sans exposer d'adresse, d'identifiant ou de mot de passe"],
    ["Traçabilité", "Journal de chaque ajout, modification, suppression et des connexions (visibles du propriétaire)"],
], [4.6, 12.0], size=8.8)
callout("Les comptes sont définis dans une variable d'environnement du serveur et les mots de passe n'y sont pas hachés. C'est acceptable pour une petite équipe, "
        "mais l'étape suivante est une table d'utilisateurs avec mots de passe hachés et une page de gestion (F24).", title="Amélioration de sécurité prévue")
H2("3.7 Déploiement et exploitation")
T(["Élément", "Service", "Détail"], [
    ["Interface", "Vercel", "Construit et publié automatiquement à chaque envoi sur la branche principale ; variable VITE_API_URL"],
    ["API", "Render (région Francfort)", "Python 3 ; démarrage : uvicorn app.main:app ; variables : DATABASE_URL, BUS_USERS, BUS_SECRET, CORS_ORIGINS, clés VAPID"],
    ["Base", "Supabase (Stockholm)", "PostgreSQL ; connexion par le pooler SSL ; tables créées au démarrage de l'API"],
    ["Surveillance", "UptimeRobot", "Appel de /api/health toutes les 5 minutes ; /api/health/db vérifie l'accès à la base"],
    ["Code", "GitHub", "Dépôt unique ; chaque envoi déclenche les déploiements"],
], [3.0, 4.2, 9.4], size=8.8)
H2("3.8 Performance — mesures")
T(["Mesure", "Avant", "Après"], [
    ["Requêtes SQL pour afficher le calendrier d'un mois", "52", "**8**"],
    ["Requêtes SQL pour la page Analyse", "50", "**6**"],
    ["Requêtes SQL pour la liste des contrats", "76", "**2**"],
    ["Taille de la réponse du calendrier", "17 Ko", "**1,8 Ko** (compressée)"],
    ["Latence API → base de données", "—", "environ 0,1 s (Francfort → Stockholm)"],
    ["Réponse de l'API en régime chaud", "—", "environ 0,3 s"],
    ["Mois déjà consulté", "chargement complet", "affichage **immédiat** puis actualisation silencieuse"],
], [8.2, 3.9, 4.5], size=8.8)
P("**Limite connue :** sur l'offre gratuite de l'hébergeur, l'API se met en veille après 15 minutes d'inactivité et met 30 à 60 secondes à redémarrer. "
  "La surveillance régulière l'évite ; un abonnement payant la supprime.", size=10)

# ================================================================== 4
H1("4. Interface et ergonomie (mobile d'abord)")
H2("4.1 Principes")
B("**Le pouce d'abord** : navigation en barre d'onglets en bas de l'écran sur téléphone, fiche d'un jour qui glisse depuis le bas, principaux boutons d'au moins 44 px.")
B("**L'essentiel en premier** : les totaux par région et le net du mois sont affichés au-dessus des véhicules.")
B("**Aujourd'hui toujours visible** : la colonne du jour est mise en évidence et le tableau s'ouvre positionné dessus.")
B("**Deux affichages au choix** : « Cartes » (une carte par véhicule, adaptée au téléphone) ou « Tableau » (vue d'ensemble sur grand écran) ; le choix est mémorisé.")
B("**Tableaux lisibles sur téléphone** : chaque ligne des tableaux (véhicules, destinations, prix, régions, locations, journal) devient une carte étiquetée ; les formulaires s'ouvrent en bas d'écran ; les sous-onglets des paramètres défilent.")
B("**Retours clairs** : squelettes de chargement, messages d'erreur lisibles, indication « estimé » quand le carburant n'est pas définitif.")
B("**Accessibilité** : zoom autorisé, étiquettes pour les boutons-icônes, contrastes élevés, champs de saisie en 16 px.")
B("**Application installable** : invitation à l'installation sur Android, consigne d'ajout à l'écran d'accueil sur iPhone.")
H2("4.2 Écrans")
T(["Écran", "Rôle", "Contenu"], [
    ["Connexion", "Tous", "Identifiant et mot de passe, affichage du mot de passe, message d'erreur clair"],
    ["📊 Calendrier", "Tous", "Net du mois, totaux par région, cartes ou tableau des véhicules, pastilles de couleur, export Excel"],
    ["Fiche d'un jour", "Tous (écriture : admin)", "Sorties du jour d'un véhicule, ajout / modification, calcul automatique du prix, contrôle de couverture"],
    ["📄 Contrats", "Tous (écriture : admin)", "Contrats par véhicule, résultat détaillé, carburant mensuel estimé / réel"],
    ["🚐 Loués", "Tous (écriture : admin)", "Véhicules de renfort, coût réparti, vérification d'alternative"],
    ["📈 Analyse", "Administrateur", "Couverture du loyer, occupation, heures d'activité par véhicule"],
    ["⚙️ Paramètres", "Tous (écriture : admin)", "Véhicules, destinations, prix, régions par saison, seuils horaires"],
    ["🧾 Journal", "Administrateur", "Historique des modifications ; envoi d'une annonce à tous les téléphones"],
], [3.2, 3.6, 9.8], size=8.8)

# ================================================================== 5
H1("5. Qualité, tests et recette")
H2("5.1 Tests automatiques")
P("**24 tests** s'exécutent en moins de 3 secondes sur une base temporaire (la vraie base n'est jamais touchée). Commande : **pytest** dans le dossier backend.")
T(["Fichier", "Tests", "Ce qui est vérifié"], [
    ["test_calc.py", "6", "Carburant au prorata (exemple du § 2.2 au centime près), résultat estimé ou réel, recettes limitées au contrat, pourcentage, location sur deux mois, couleurs des jours"],
    ["test_regions.py", "11", "Écriture unique des noms de région, véhicule qui ne bouge pas, découpage exact au jour du déplacement, absence de faux déplacement dû à une faute de frappe"],
    ["test_calendar.py", "4", "Un seul bloc par région, une ligne par contrat en cas de changement de région, totaux régionaux = somme des loyers, véhicule sans contrat absent"],
    ["test_analytics.py", "2", "La page Analyse découpe le mois exactement comme le calendrier : mêmes lignes, mêmes montants (recette, loyer, carburant, net)"],
    ["test_cache.py", "1", "Le cache est vidé dès qu'une écriture a lieu : jamais de donnée périmée"],
], [3.4, 1.5, 11.7], size=8.8)
H2("5.2 Cahier de recette (tests manuels)")
T(["N°", "Scénario", "Résultat attendu"], [
    ["R01", "Se connecter avec un compte administrateur", "Accès au calendrier du mois en cours, six onglets visibles"],
    ["R02", "Saisir un mauvais mot de passe", "Message « Identifiants incorrects » ; après 6 essais, blocage temporaire"],
    ["R03", "Ouvrir le calendrier sur téléphone", "Vue cartes, totaux en haut, jour d'aujourd'hui entouré, barre d'onglets en bas"],
    ["R04", "Toucher un jour d'un véhicule, ajouter une sortie", "Fiche en bas d'écran ; prix calculé ; pastille colorée après enregistrement"],
    ["R05", "Toucher un jour hors contrat", "Case grisée, saisie impossible"],
    ["R06", "Créer un contrat et saisir le carburant (exemple du § 2.2)", "Résultat 5 613,23 TND, marqué « estimé » tant que juin n'est pas réel"],
    ["R07", "Déplacer un véhicule vers une autre région au milieu du mois", "Le véhicule apparaît dans les deux régions, avec ses propres jours"],
    ["R08", "Deux contrats consécutifs dans deux régions", "Deux lignes (une par contrat) ; totaux régionaux corrects"],
    ["R09", "Se connecter avec un compte lecture seule", "Consultation possible, boutons de modification absents ou refusés"],
    ["R10", "Exporter le calendrier en Excel", "Fichier .xlsx identique à l'écran, avec le découpage par région"],
    ["R11", "Consulter le journal après une modification", "Ligne avec utilisateur, heure et détail exact"],
    ["R12", "Activer la cloche, puis envoyer une annonce (Journal)", "Notification reçue sur le téléphone"],
    ["R13", "Installer l'application, couper le réseau, rouvrir", "L'application s'ouvre et affiche les dernières données"],
    ["R14", "Changer de mois avec les flèches", "Mois voisins affichés instantanément"],
    ["R15", "Ouvrir Paramètres > Véhicules et Loués sur téléphone", "Une carte étiquetée par ligne, sans défilement horizontal ; formulaire en bas d'écran"],
], [1.2, 7.8, 7.6], size=8.8)

# ================================================================== 6
H1("6. Planning et organisation")
T(["Phase", "Contenu", "État"], [
    ["1 — Analyse", "Étude de l'ancien classeur, identification des erreurs, règles de gestion, migration des données (23 véhicules, 944 sorties, 120 destinations)", "Réalisé"],
    ["2 — Conception et API", "Modèle de données, règles de calcul centralisées, API sécurisée avec rôles et journal", "Réalisé"],
    ["3 — Interface", "Calendrier, saisie d'un jour, contrats, carburant, paramètres, analyse, exports", "Réalisé"],
    ["4 — Mise en ligne", "Base Supabase, API Render, interface Vercel, notifications push, application installable", "Réalisé"],
    ["5 — Optimisation", "Réduction des requêtes, cache, compression, déplacement de l'API à Francfort, robustesse aux réveils du serveur", "Réalisé"],
    ["6 — Mobile et finitions", "Barre d'onglets, vue cartes, tableaux en cartes, formulaires en bas d'écran, notifications accessibles, invitation à l'installation", "Réalisé"],
    ["7 — Recette et documentation", "24 tests automatiques, cahier de recette, ce cahier des charges, guide de déploiement", "Réalisé"],
    ["8 — Évolutions", "Voir § 9", "Prévu"],
], [3.6, 10.6, 2.4], size=8.8, status_cols=(2,))

# ================================================================== 7
H1("7. Budget et hébergement")
T(["Service", "Offre actuelle", "Coût mensuel", "Limites à connaître"], [
    ["Vercel (interface)", "Hobby", "0", "Usage personnel / non commercial selon les conditions du service"],
    ["Render (API)", "Gratuite", "0", "Mise en veille après 15 min ; 512 Mo de mémoire"],
    ["Supabase (base)", "Gratuite", "0", "500 Mo ; projet mis en pause après une semaine sans activité"],
    ["UptimeRobot", "Gratuite", "0", "Contrôle toutes les 5 minutes"],
    ["GitHub", "Gratuite", "0", "—"],
    ["**Total**", "", "**0 TND**", ""],
], [3.6, 3.0, 2.6, 7.4], size=8.8)
P("**Option production** (tarifs indicatifs, à vérifier auprès des fournisseurs) : l'offre Starter de Render (environ 7 USD par mois) supprime la mise en veille ; "
  "Supabase Pro (environ 25 USD par mois) ajoute les sauvegardes quotidiennes ; un nom de domaine propre coûte environ 12 USD par an.", size=10)

# ================================================================== 8
H1("8. Risques et limites connues")
T(["Risque", "Probabilité", "Impact", "Parade"], [
    ["Mise en veille de l'API (démarrage à froid de 30 à 60 s)", "Moyenne", "Moyen", "Surveillance toutes les 5 min ; relances automatiques ; offre payante possible"],
    ["Projet Supabase gratuit mis en pause après inactivité", "Faible", "Fort", "Usage régulier ; réactivation en un clic ; sauvegarde à automatiser (F25)"],
    ["Perte de données", "Faible", "Fort", "Script de sauvegarde existant ; sauvegardes automatiques planifiées (F25) ou offre payante"],
    ["Comptes et mots de passe gérés côté serveur sans hachage", "Faible", "Moyen", "Passage à des comptes en base avec mots de passe hachés (F24)"],
    ["Mise à jour d'une dépendance qui casse le démarrage (déjà rencontré avec le pilote PostgreSQL)", "Moyenne", "Moyen", "Pilote désormais nommé explicitement ; tests automatiques ; versions à figer"],
    ["Saisie erronée d'une région, d'un prix ou d'une date", "Moyenne", "Moyen", "Noms de région normalisés, contrôle de couverture, journal des modifications"],
    ["Absence de tests de bout en bout dans le navigateur", "Moyenne", "Faible", "Tests de l'interface à ajouter ; recette manuelle documentée (§ 5.2)"],
], [6.0, 2.2, 1.8, 6.6], size=8.8)

# ================================================================== 9
H1("9. Évolutions prévues")
T(["Horizon", "Évolution", "Bénéfice"], [
    ["Court terme\n(1 mois)", "Sauvegarde automatique quotidienne de la base\nFigement des versions des dépendances", "Cohérence des chiffres ; sécurité des données ; stabilité"],
    ["Moyen terme\n(3 mois)", "Gestion des utilisateurs dans l'interface, mots de passe hachés\nTests automatiques de l'interface (bout en bout) et déploiement contrôlé\nTableau de bord de direction (évolution du net sur 12 mois)\nSaisie plus rapide sur téléphone (suggestions, raccourcis)", "Autonomie de l'administration ; qualité ; pilotage ; confort mobile"],
    ["Long terme\n(6 mois et plus)", "Facturation client et factures PDF\nInterface en arabe et en français\nSuivi des kilomètres et de la maintenance (alertes d'entretien)\nSaisie hors ligne avec synchronisation\nSuivi GPS des véhicules", "Couverture complète du métier ; accessibilité ; exploitation terrain"],
], [2.8, 9.2, 4.6], size=8.8)

# ================================================================== 10
H1("10. Livrables et conditions de recette")
H2("10.1 Livrables")
B("Application en ligne : https://bus-app-web-lemon.vercel.app")
B("Code source complet (interface, API, tests) : https://github.com/bilelsdn21/bus-app-web")
B("Documentation : README (règles de calcul, architecture), guide de déploiement, ce cahier des charges")
B("Suite de 24 tests automatiques et cahier de recette manuel (§ 5.2)")
B("Exports Excel équivalents à l'ancien classeur")
H2("10.2 Critères d'acceptation")
B("Les 15 scénarios de recette (§ 5.2) sont validés")
B("Les 24 tests automatiques passent")
B("Les totaux du calendrier, de l'export Excel et des cartes régionales concordent")
B("Un utilisateur en lecture seule ne peut rien modifier, y compris en appelant l'API directement")
B("Le calendrier d'un mois s'affiche en moins de 3 secondes sur une connexion mobile ordinaire (hors réveil du serveur)")

# ================================================================== ANNEXES
page_break()
H1("Annexe A — Glossaire")
T(["Terme", "Définition"], [
    ["Contrat", "Période d'exploitation d'un véhicule, aux dates libres, avec un loyer"],
    ["Loyer", "Montant payé pour le véhicule sur la période d'un contrat"],
    ["Sortie / excursion", "Trajet payant d'un véhicule : destination, heures, client, prix"],
    ["Net", "Recettes − loyer − carburant"],
    ["Prorata", "Répartition d'un montant au nombre de jours concernés"],
    ["Estimé / réel", "Carburant prévisionnel, remplacé par le montant réel le mois suivant"],
    ["Région", "Zone d'exploitation (Sousse, Djerba…) ; un véhicule peut en changer à une date donnée"],
    ["Tronçon", "Partie d'un contrat passée dans une seule région"],
    ["Véhicule loué (renfort)", "Véhicule externe loué temporairement, hors flotte"],
    ["PWA", "Application web installable sur l'écran d'accueil, utilisable en plein écran"],
    ["Notification push", "Message affiché sur le téléphone même quand l'application est fermée"],
    ["RLS", "Sécurité au niveau des lignes de la base de données"],
    ["API", "Interface par laquelle l'application échange des données avec le serveur"],
], [4.2, 12.4], size=9)

H1("Annexe B — Guide rapide utilisateur")
H3("Premier démarrage sur téléphone")
B("Ouvrir l'adresse de l'application dans le navigateur, se connecter.")
B("**Android :** accepter l'invitation « Installer l'application ». **iPhone :** bouton Partager, puis « Sur l'écran d'accueil ».")
B("Toucher **Activer** dans la carte « Restez informé » pour recevoir les notifications.")
H3("Au quotidien")
B("**Voir le mois :** onglet Calendrier ; flèches pour changer de mois ; bascule Cartes / Tableau.")
B("**Saisir une sortie :** toucher un jour d'un véhicule ; choisir la destination et les heures ; Enregistrer.")
B("**Lire une carte :** nom du véhicule, net du mois en couleur, jours colorés selon la période de la journée, jour d'aujourd'hui entouré.")
B("**Voir un contrat :** toucher le nom du véhicule.")
B("**Exporter :** bouton « Exporter Excel » en haut du calendrier.")
H3("Administrateur")
B("**Envoyer une annonce :** onglet Journal, rubrique « Envoyer une notification à tous ».")
B("**Déplacer un véhicule de région :** Paramètres, régions par saison, « Déplacer », avec la date du changement.")

H1("Annexe C — Configuration et installation")
H3("Variables d'environnement")
T(["Variable", "Où", "Rôle"], [
    ["DATABASE_URL", "API", "Adresse de la base PostgreSQL ; absente = SQLite local"],
    ["BUS_USERS", "API", "Comptes au format utilisateur:motdepasse:rôle, séparés par des virgules"],
    ["BUS_SECRET", "API", "Clé de signature des jetons (longue, aléatoire)"],
    ["CORS_ORIGINS", "API", "Adresses autorisées à appeler l'API"],
    ["VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT", "API", "Clés des notifications push"],
    ["NOTIFY_SECRET", "API", "Secret du déclencheur hebdomadaire de notifications"],
    ["TOKEN_TTL_HOURS", "API", "Durée de validité des jetons (365 jours par défaut)"],
    ["VITE_API_URL", "Interface", "Adresse de l'API (variable normale, pas un secret)"],
], [6.2, 2.2, 8.2], size=8.8)
H3("Installation locale")
P("**API :** dans le dossier backend, créer un environnement virtuel, installer requirements.txt, lancer « python -m app.seed » puis « uvicorn app.main:app --reload --port 8000 ».", size=10)
P("**Interface :** dans le dossier frontend, « npm install » puis « npm run dev » (http://localhost:5173).", size=10)
P("**Tests :** dans le dossier backend, installer requirements-dev.txt puis lancer « pytest ».", size=10)

H1("Annexe D — Trame de soutenance et scénario de démonstration")
H2("Durée conseillée : 10 à 12 minutes")
T(["Minutes", "Séquence", "Message clé"], [
    ["0 – 1", "Contexte et problème : l'ancien classeur, l'erreur de 1 440 TND", "Un vrai problème métier, mesurable"],
    ["1 – 2", "Objectifs et périmètre", "Fiabilité, mobilité, rentabilité, traçabilité"],
    ["2 – 4", "Règles de gestion : prorata du carburant (exemple chiffré), régions datées", "La partie difficile est résolue et testée"],
    ["4 – 5", "Architecture : une image, trois services, coût nul", "Choix techniques justifiés"],
    ["5 – 9", "**Démonstration en direct** (scénario ci-dessous)", "L'outil fonctionne, sur téléphone aussi"],
    ["9 – 10", "Qualité : 24 tests, sécurité, journal, mesures de performance (52 → 8 requêtes)", "Un projet fiable et rapide"],
    ["10 – 11", "Limites honnêtes et évolutions", "Maîtrise du sujet, vision"],
    ["11 – 12", "Conclusion et questions", "Valeur apportée"],
], [2.0, 8.4, 6.2], size=8.8)
H2("Scénario de démonstration")
N("Sur téléphone : ouvrir l'application, montrer le calendrier en cartes, les totaux par région et le jour d'aujourd'hui entouré.")
N("Toucher un jour, ajouter une sortie : le prix se calcule seul, la pastille change de couleur.")
N("Ouvrir un contrat : montrer le résultat avec le carburant au prorata et la mention « estimé ».")
N("Montrer un véhicule qui change de région en cours de mois : une ligne par région, des totaux justes.")
N("Compte en lecture seule : les modifications sont refusées.")
N("Journal : la modification qui vient d'être faite apparaît avec son auteur.")
N("Envoyer une annonce : la notification arrive sur le téléphone, devant le jury.")
N("Exporter en Excel : montrer l'équivalence avec l'ancien classeur.")
callout("• **Réveiller le serveur 5 minutes avant** en ouvrant l'application (le premier chargement après une longue veille peut durer jusqu'à une minute).\n"
        "• Vérifier la connexion Internet de la salle ; prévoir le partage de connexion du téléphone.\n"
        "• Tester les comptes (administrateur et lecture seule) et la notification la veille.\n"
        "• Préparer des captures d'écran et une courte vidéo de secours.\n"
        "• Choisir un mois contenant un véhicule qui change de région pour la démonstration.",
        title="Checklist avant la présentation")

doc.save(OUT)
print("saved", OUT)
