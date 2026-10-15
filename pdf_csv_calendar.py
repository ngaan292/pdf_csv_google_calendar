"""
Programme de conversion de planning de vol PDF vers CSV Calendrier (Google Calendar, Outlook).
Combine l'extraction de tableau (pdf2excel) et la transformation de planning (csv_calendar).
"""

import os
import re
import csv
import json
import calendar
from datetime import datetime, timedelta
import pytz
import pdfplumber
import pandas as pd

# =====================================================================
# Configuration par défaut
# =====================================================================
colonne_max = 5        # nombre de colonne + 1 a traiter
mois = '10'            # mois ('10', ou None / 'auto' pour détection automatique)
annee = '2026'         # année ('2026', ou None / 'auto' pour détection automatique)
personne = '_Hung'     # '' ou '_Hung' - utilisé pour les dossiers et nom de sortie
fuseau_source = 'UTC'
fuseau_cible = 'Asia/Bangkok'

calendar_titre = [
    'Subject', 'Start Date', 'Start Time', 'End Date', 'End Time',
    'All Day Event', 'Description', 'Location', 'Private'
]

# Cache pour les codes IATA afin d'éviter des lectures disque répétées
_airports_cache = None


def charger_airports(json_path='IATAlocationcodes.json'):
    """Charge en mémoire la base de données des aéroports IATA."""
    global _airports_cache
    if _airports_cache is None:
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as file:
                    _airports_cache = json.load(file)
            except Exception as e:
                print(f"[!] Erreur de lecture de {json_path}: {e}")
                _airports_cache = {}
        else:
            # Recherche relative au dossier du script si besoin
            script_dir = os.path.dirname(os.path.abspath(__file__))
            alt_path = os.path.join(script_dir, json_path)
            if os.path.exists(alt_path):
                try:
                    with open(alt_path, 'r', encoding='utf-8') as file:
                        _airports_cache = json.load(file)
                except Exception as e:
                    print(f"[!] Erreur de lecture de {alt_path}: {e}")
                    _airports_cache = {}
            else:
                _airports_cache = {}
    return _airports_cache


def airport_name(airport_code, json_path='IATAlocationcodes.json'):
    """
    Convertit un code IATA en nom complet (ex: HAN -> 'Noi Bai Intl Hanoi').
    Si inconnu, retourne le code IATA pour éviter toute erreur.
    """
    airports = charger_airports(json_path)
    info = airports.get(airport_code)
    if info:
        location = info.get('location', '')
        city = info.get('city', '')
        nom = f"{location} {city}".strip()
        if nom:
            return nom
    return airport_code


def recuperer_mois_annee(pdf_path=None, mois_manuel=None, annee_manuel=None):
    """
    Récupère le mois et l'année soit :
    1. Depuis les paramètres manuels si fournis (non None et non 'auto').
    2. Depuis le nom du fichier PDF (ex: MonthPlan10_2026.pdf).
    3. Depuis la date de modification/upload du PDF.
    4. Depuis la date actuelle par défaut.
    """
    # 1. Manuel
    if mois_manuel and str(mois_manuel).lower() != 'auto' and annee_manuel and str(annee_manuel).lower() != 'auto':
        m_str = str(mois_manuel).strip().replace("'", "").replace('"', "").zfill(2)
        y_str = str(annee_manuel).strip().replace("'", "").replace('"', "")
        return m_str, y_str, "manuel"

    # 2. Nom du fichier PDF
    if pdf_path:
        nom_fichier = getattr(pdf_path, 'name', None) or (os.path.basename(pdf_path) if isinstance(pdf_path, str) else '')
        if nom_fichier:
            match = re.search(r'(\d{1,2})_(\d{4})', nom_fichier)
            if match:
                return match.group(1).zfill(2), match.group(2), "nom de fichier"
            match_alt = re.search(r'(\d{4})[-_](\d{1,2})', nom_fichier)
            if match_alt:
                return match_alt.group(2).zfill(2), match_alt.group(1), "nom de fichier"

        # 3. Moment de l'upload / dernière modification du fichier PDF (si fichier sur disque)
        if isinstance(pdf_path, str) and os.path.exists(pdf_path):
            mtime = os.path.getmtime(pdf_path)
            dt_upload = datetime.fromtimestamp(mtime)
            return dt_upload.strftime('%m'), dt_upload.strftime('%Y'), "date upload/fichier"

    # 4. Date actuelle
    now = datetime.now()
    return now.strftime('%m'), now.strftime('%Y'), "date actuelle"


def extraire_plus_grand_tableau(pdf_source):
    """
    Parcourt le PDF (chemin fichier ou objet BytesIO), extrait tous les tableaux,
    et retourne le plus grand sous la forme d'un DataFrame Pandas nettoyé.
    """
    all_tables = []
    source_label = getattr(pdf_source, 'name', None) or (pdf_source if isinstance(pdf_source, str) else "Flux mémoire")
    print(f"[*] Analyse du PDF : {source_label}")

    with pdfplumber.open(pdf_source) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                if table:
                    df = pd.DataFrame(table)
                    # Nettoyage des cellules
                    df = df.map(lambda x: str(x).strip().replace('\n', ' ') if x is not None else '')
                    score_taille = len(df) * len(df.columns)
                    all_tables.append((df, score_taille, page_idx + 1))

    if not all_tables:
        raise ValueError(f"Aucun tableau trouvé dans le document PDF ({source_label})")

    plus_grand_df, score, page_origine = max(all_tables, key=lambda x: x[1])
    print(f"[+] Tableau principal detecte : {plus_grand_df.shape[0]} lignes x {plus_grand_df.shape[1]} colonnes (page {page_origine}).")
    return plus_grand_df


def fin_mois_avant(mois_val, annee_val):
    """Calcule le dernier jour, le mois et l'année du mois précédent."""
    m = int(str(mois_val).strip().replace("'", "").replace('"', ""))
    y = int(str(annee_val).strip().replace("'", "").replace('"', ""))
    if m == 1:
        mois_avant = '12'
        annee_avant = str(y - 1)
    else:
        mois_avant = f"{m - 1:02d}"
        annee_avant = str(y)
    jour_fin = str(calendar.monthrange(int(annee_avant), int(mois_avant))[1])
    return jour_fin, mois_avant, annee_avant


def build_calendar_date(year, month, day):
    """Construit une date au format YYYY-MM-DD avec validation."""
    y = int(str(year).strip().replace("'", "").replace('"', ""))
    m = int(str(month).strip().replace("'", "").replace('"', ""))
    d = int(str(day).strip().replace("'", "").replace('"', ""))
    last_day = calendar.monthrange(y, m)[1]
    if d < 1 or d > last_day:
        raise ValueError(f"Jour {d} hors limites (1..{last_day}) pour {m:02d}/{y}")
    return f"{y:04d}-{m:02d}-{d:02d}"


def data_extract(day_num, ligne, month, year):
    """
    Transforme une case de vol/activité brute en ligne d'événement de calendrier.
    """
    try:
        date_value = build_calendar_date(year, month, day_num)
    except ValueError as e:
        print(f"[!] Date invalide '{year}-{month}-{day_num}' : {e}")
        return ['', '', '', '', '', '', '', '', '']

    data_ligne = ['', '', '', '', '', '', '', '', '']
    ligne = str(ligne).strip()

    if len(ligne) > 4:
        if ligne[0] == '-':
            # Jour de congé / Reserve day
            data_ligne[0] = ligne[4:].strip()
            data_ligne[1] = date_value
            data_ligne[3] = date_value
            data_ligne[5] = True
            data_ligne[8] = False

        elif len(ligne) > 22 and isinstance(ligne[0], str) and ligne[0] != 'S' and ligne[5] != '-' and ligne[0] != '.' and ligne[0] != 'I':
            # Vol régulier : ex "0010 HAN ==> 0135 VCL VN1641"
            data_ligne[2] = ligne[0:2] + ':' + ligne[2:4]
            data_ligne[1] = date_value
            data_ligne[3] = date_value

            if ligne[17] != '.':
                data_ligne[0] = airport_name(ligne[5:8]) + '-' + airport_name(ligne[18:21])
                data_ligne[4] = ligne[13:15] + ':' + ligne[15:17]
                data_ligne[6] = airport_name(ligne[5:8]) + '-' + airport_name(ligne[18:21]) + "\n" + ligne[22:].strip()
            else:
                data_ligne[4] = '23:59'
                data_ligne[0] = airport_name(ligne[5:8]) + '-' + airport_name(ligne[13:16])
                data_ligne[6] = airport_name(ligne[5:8]) + '-' + airport_name(ligne[13:16]) + "\n" + ligne[21:].strip()

            data_ligne[5] = False
            data_ligne[8] = False

        elif len(ligne) > 22 and ligne[0:7] == 'Standby':
            # Standby
            data_ligne[0] = ligne[0:9].strip()
            data_ligne[1] = date_value
            data_ligne[3] = date_value
            if ligne[12] != '.' and ligne[20] != '.':
                data_ligne[2] = ligne[11:13] + ':' + ligne[13:15]
                data_ligne[4] = ligne[19:21] + ':' + ligne[21:23]
            elif ligne[19] == '.':
                data_ligne[2] = ligne[11:13] + ':' + ligne[13:15]
                data_ligne[4] = '23:59'
            else:
                data_ligne[2] = '00:00'
                data_ligne[4] = ligne[18:20] + ':' + ligne[20:22]
            data_ligne[5] = False
            data_ligne[8] = False

        elif len(ligne) > 12 and ligne[5] == '-':
            # Service au sol : ex "0100 -- 1000 Working for Cabin Crew's Departments"
            data_ligne[0] = ligne[12:].strip()
            data_ligne[1] = date_value
            data_ligne[3] = date_value
            data_ligne[2] = ligne[0:2] + ':' + ligne[2:4]
            data_ligne[4] = ligne[8:10] + ':' + ligne[10:12]
            data_ligne[5] = False
            data_ligne[8] = False

        elif len(ligne) > 21 and ligne[0] == '.':
            # Vol de continuation : ex "... MNL ==> 0035 HAN VN0646"
            data_ligne[0] = ligne[4:7] + ' ' + ligne[17:20]
            data_ligne[1] = date_value
            data_ligne[3] = date_value
            data_ligne[2] = "00:00"
            data_ligne[4] = ligne[12:14] + ':' + ligne[14:16]
            data_ligne[5] = False
            data_ligne[6] = ligne[21:].strip()
            data_ligne[8] = False

        elif ligne[0] == 'I':
            pass

    elif ligne == 'Stay':
        data_ligne[0] = ligne
        data_ligne[1] = date_value
        data_ligne[3] = date_value
        data_ligne[5] = True
        data_ligne[8] = False

    return data_ligne


def convertir_fuseau_horaire(temps_str, gmt_a='UTC', gmt_b='Asia/Bangkok'):
    """Convertit une chaîne 'YYYY-MM-DD HH:MM' d'un fuseau à un autre."""
    try:
        dt_naive = datetime.strptime(temps_str, "%Y-%m-%d %H:%M")
    except ValueError as e:
        print(f"[!] Avertissement format date '{temps_str}' : {e}")
        parts = temps_str.split(' ')
        return parts[0], parts[1] if len(parts) > 1 else "00:00"

    tz_a = pytz.timezone(gmt_a)
    tz_b = pytz.timezone(gmt_b)

    dt_a = tz_a.localize(dt_naive)
    dt_b = dt_a.astimezone(tz_b)

    return dt_b.strftime("%Y-%m-%d"), dt_b.strftime("%H:%M")


def maj_fuseau_horaire(data, gmt_a='UTC', gmt_b='Asia/Bangkok'):
    """Met à jour les dates et heures de début et fin selon le fuseau horaire."""
    data = list(data)
    temp_str_start = data[1] + ' ' + data[2]
    temp_str_end = data[3] + ' ' + data[4]
    data[1], data[2] = convertir_fuseau_horaire(temp_str_start, gmt_a, gmt_b)
    data[3], data[4] = convertir_fuseau_horaire(temp_str_end, gmt_a, gmt_b)
    return data


def extraire_donnees_calendrier(table_rows, mois_val, annee_val, col_max=5):
    """
    Extrait les événements du calendrier à partir des lignes du tableau PDF.
    - La ligne 0 correspond au dernier jour du mois précédent.
    - Les lignes 1..N correspondent aux jours du mois en cours.
    """
    jour_fin, mois_avant, annee_avant = fin_mois_avant(mois_val, annee_val)

    nb_cols = len(table_rows[0]) if table_rows else 0
    max_j = min(col_max, nb_cols)

    data_events = []

    # 1. Traitement de la ligne 0 (fin du mois précédent)
    for j in range(1, max_j):
        event = data_extract(jour_fin, table_rows[0][j], mois_avant, annee_avant)
        if event[0] != '':
            data_events.append(event)

    # 2. Traitement des lignes suivantes (jours du mois en cours)
    for i in range(1, len(table_rows)):
        # Récupère le numéro du jour (soit depuis la première colonne '1.', '2.', soit i)
        raw_day = str(table_rows[i][0]).replace('.', '').strip()
        day_num = int(raw_day) if raw_day.isdigit() else i

        for j in range(1, min(col_max, len(table_rows[i]))):
            event = data_extract(day_num, table_rows[i][j], mois_val, annee_val)
            if event[0] != '':
                data_events.append(event)

    return data_events


def ecrire_csv_final(file_path, data_list):
    """Écrit la liste des événements dans le fichier CSV final."""
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',')
        for row in data_list:
            csv_writer.writerow(row)
    print(f"[+] Fichier CSV final genere : {file_path}")


def convertir_pdf_en_csv(
    pdf_path=None,
    sortie_csv=None,
    mois_param=mois,
    annee_param=annee,
    personne_param=personne,
    colonne_max_param=colonne_max,
    sauvegarder_csv_intermediaire=True,
    trier_chronologique=True
):
    """
    Fonction principale qui reçoit un PDF en entrée et génère le CSV final.
    """
    # Détermination du nom de la personne
    nom_pers_clean = str(personne_param).strip()
    if nom_pers_clean and not nom_pers_clean.startswith('_'):
        dossier_pers = f"_{nom_pers_clean}"
    else:
        dossier_pers = nom_pers_clean

    # Détection du mois et de l'année (manuel, nom fichier, date upload PDF)
    m_detect, y_detect, source_date = recuperer_mois_annee(pdf_path, mois_param, annee_param)
    print(f"[*] Periode : Mois = {m_detect}, Annee = {y_detect} (source : {source_date})")

    # Si aucun PDF n'est spécifié, on recherche le chemin par défaut
    if not pdf_path:
        pdf_path = f"data{dossier_pers}/pdf/MonthPlan{m_detect}_{y_detect}.pdf"
        if not os.path.exists(pdf_path):
            # Essai sans suffixe personne
            alt_pdf = f"data/pdf/MonthPlan{m_detect}_{y_detect}.pdf"
            if os.path.exists(alt_pdf):
                pdf_path = alt_pdf

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Fichier PDF introuvable : {pdf_path}")

    # Étape 1 : Extraction du tableau PDF (pdf2excel)
    df_table = extraire_plus_grand_tableau(pdf_path)

    # Sauvegarde facultative du CSV intermédiaire brut (comme pdf2excel.py)
    if sauvegarder_csv_intermediaire:
        csv_intermediaire = f"data{dossier_pers}/pdf2excel/MonthPlan{m_detect}_{y_detect}.csv"
        os.makedirs(os.path.dirname(os.path.abspath(csv_intermediaire)), exist_ok=True)
        df_table.to_csv(csv_intermediaire, index=False, header=False, sep=';', encoding='utf-8-sig')
        print(f"[+] Tableau brut sauvegarde : {csv_intermediaire}")

    table_rows = df_table.values.tolist()

    # Étape 2 : Extraction et structuration des événements (csv_calendar)
    events = extraire_donnees_calendrier(table_rows, m_detect, y_detect, col_max=colonne_max_param)

    # Étape 3 : Conversion du fuseau horaire vers Asia/Bangkok (UTC+7)
    events_gmt = []
    for ev in events:
        if not ev[5]:  # Pas un All Day Event -> convertir fuseau horaire
            events_gmt.append(maj_fuseau_horaire(ev, fuseau_source, fuseau_cible))
        else:
            events_gmt.append(ev)

    # Étape 4 : Option de tri chronologique (par date puis heure)
    if trier_chronologique:
        # Tri par Start Date, puis All Day en premier ou heure de début
        events_gmt.sort(key=lambda x: (x[1], x[2] if x[2] else '00:00'))

    # Préparation du CSV final avec en-tête
    donnees_finales = [calendar_titre] + events_gmt

    # Étape 5 : Écriture du CSV final
    if not sortie_csv:
        sortie_csv = f"data{dossier_pers}/excel_final/Calendar{m_detect}_{y_detect}.csv"

    ecrire_csv_final(sortie_csv, donnees_finales)
    print(f"[+] Traitement termine avec succes ! ({len(events_gmt)} evenements exportes)")
    return sortie_csv


# =====================================================================
# Point d'entrée exécutable / Ligne de commande
# =====================================================================
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Convertit un planning de vol PDF en CSV Google Calendar."
    )
    parser.add_argument(
        'pdf',
        nargs='?',
        default=None,
        help="Chemin vers le fichier PDF (ex: data_Hung/pdf/MonthPlan10_2026.pdf)"
    )
    parser.add_argument(
        '--mois', '-m',
        default=mois,
        help="Mois a traiter (ex: 10). Laisser vide pour auto-detecter depuis l'upload/fichier."
    )
    parser.add_argument(
        '--annee', '-y',
        default=annee,
        help="Annee a traiter (ex: 2026). Laisser vide pour auto-detecter depuis l'upload/fichier."
    )
    parser.add_argument(
        '--personne', '-p',
        nargs='?',
        default=personne,
        const='',
        help="Nom ou suffixe de la personne (ex: '_Hung', 'Hung', ou '' pour defaut)"
    )
    parser.add_argument(
        '--colonne-max', '-c',
        type=int,
        default=colonne_max,
        help="Nombre de colonnes + 1 a traiter (par defaut: 5)"
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help="Chemin du fichier CSV de sortie final (optionnel)"
    )

    args = parser.parse_args()

    convertir_pdf_en_csv(
        pdf_path=args.pdf,
        sortie_csv=args.output,
        mois_param=args.mois,
        annee_param=args.annee,
        personne_param=args.personne,
        colonne_max_param=args.colonne_max
    )
