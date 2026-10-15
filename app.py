"""
Interface Streamlit pour Mom Calendar.
Permet d'uploader un planning de vol PDF, de configurer les métadonnées
(mois, année, personne, fuseau) et de télécharger le CSV prêt pour Google Calendar / Outlook.
Compatible pour un déploiement local et en ligne sur Streamlit Cloud.
"""

import io
import os
import re
import csv
import pandas as pd
import streamlit as st
from datetime import datetime

# Import de la logique métier depuis pdf_csv_calendar
from pdf_csv_calendar import (
    extraire_plus_grand_tableau,
    extraire_donnees_calendrier,
    maj_fuseau_horaire,
    recuperer_mois_annee,
    calendar_titre,
    fuseau_source as DEFAULT_FUSEAU_SOURCE,
    fuseau_cible as DEFAULT_FUSEAU_CIBLE
)

# Configuration de la page
st.set_page_config(
    page_title="Mom Calendar - PDF vers CSV Calendrier",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles CSS personnalisés pour une interface moderne
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F3F4F6;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        border-left: 4px solid #3B82F6;
    }
</style>
""", unsafe_allow_html=True)

# En-tête
st.markdown('<div class="main-title">✈️ Calendar - Convertisseur de Planning</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Transformez votre planning de vol PDF en fichier CSV directement importable dans <b>Google Calendar</b>, <b>Outlook</b> et <b>Apple Calendar</b>.</div>', unsafe_allow_html=True)

# Barre latérale : Paramètres globaux
with st.sidebar:
    st.header("⚙️ Paramètres")
    personne_input = st.text_input(
        "Nom / Préfixe personne",
        value="_Hung",
        help="Utilisé pour nommer le fichier exporté (ex: '_Hung' donnera Calendar_Hung_10_2026.csv)"
    )

    colonne_max = st.number_input(
        "Colonnes max à traiter",
        min_value=2,
        max_value=10,
        value=5,
        help="Nombre de colonnes + 1 du tableau PDF à inspecter (défaut: 5)"
    )

    fuseau_cible = st.selectbox(
        "Fuseau horaire d'arrivée",
        options=["Asia/Bangkok", "Asia/Ho_Chi_Minh", "Europe/Paris", "UTC"],
        index=0,
        help="Les horaires du planning (en UTC) seront convertis dans ce fuseau horaire."
    )

    trier_chrono = st.checkbox(
        "Trier chronologiquement",
        value=True,
        help="Trie les événements par date et heure de début pour un affichage parfait dans l'agenda."
    )

    st.markdown("---")
    st.markdown("### ℹ️ À propos")
    st.caption("Ce projet extrait automatiquement le tableau principal du PDF avec **pdfplumber**, résout les codes IATA et convertit les horaires UTC en heure locale.")

# Zone principale
col_upload, col_settings = st.columns([1.2, 1])

with col_upload:
    uploaded_file = st.file_uploader(
        "📄 Déposez votre planning mensuel (format PDF)",
        type=["pdf"],
        help="Sélectionnez ou glissez-déposez le fichier PDF du mois."
    )

# Détection automatique du mois et de l'année
default_mois = "10"
default_annee = "2026"
source_detectee = "par défaut"

if uploaded_file is not None:
    # Tentative d'auto-détection depuis le nom du fichier PDF uploadé
    m_auto, y_auto, src = recuperer_mois_annee(uploaded_file, mois_manuel=None, annee_manuel=None)
    default_mois = m_auto
    default_annee = y_auto
    source_detectee = src

with col_settings:
    st.subheader("📅 Période du planning")
    c_m, c_y = st.columns(2)
    with c_m:
        mois_val = st.text_input("Mois (01-12)", value=default_mois)
    with c_y:
        annee_val = st.text_input("Année", value=default_annee)

    if uploaded_file is not None:
        st.info(f"💡 Détection automatique : Mois **{default_mois}**, Année **{default_annee}** *(source : {source_detectee})*")

# Traitement du fichier
if uploaded_file is not None:
    st.markdown("---")
    btn_convertir = st.button("🚀 Générer le fichier CSV Calendrier", type="primary", use_container_width=True)

    if btn_convertir:
        with st.spinner("Analyse du PDF et extraction des vols en cours..."):
            try:
                # Lecture des octets du PDF uploadé
                pdf_bytes = io.BytesIO(uploaded_file.getvalue())
                pdf_bytes.name = uploaded_file.name

                # 1. Extraction du tableau
                df_brut = extraire_plus_grand_tableau(pdf_bytes)
                table_rows = df_brut.values.tolist()

                # 2. Extraction des événements
                events = extraire_donnees_calendrier(
                    table_rows,
                    mois_val=mois_val,
                    annee_val=annee_val,
                    col_max=int(colonne_max)
                )

                if not events:
                    st.warning("⚠️ Aucun événement n'a pu être extrait du document.")
                else:
                    # 3. Conversion de fuseau horaire
                    events_final = []
                    for ev in events:
                        if not ev[5]:  # Événement avec horaires (vol, standby, travail)
                            events_final.append(maj_fuseau_horaire(ev, DEFAULT_FUSEAU_SOURCE, fuseau_cible))
                        else:
                            events_final.append(ev)

                    # 4. Tri chronologique optionnel
                    if trier_chrono:
                        events_final.sort(key=lambda x: (x[1], x[2] if x[2] else '00:00'))

                    # DataFrame pour affichage et export
                    df_final = pd.DataFrame(events_final, columns=calendar_titre)

                    # Statistiques
                    nb_total = len(events_final)
                    nb_vols = sum(1 for e in events_final if not e[5] and '-' in e[0])
                    nb_conges = sum(1 for e in events_final if e[5] or 'Dayoff' in e[0] or 'Reserve' in e[0])
                    nb_autres = nb_total - nb_vols - nb_conges

                    st.success(f"✅ Conversion réussie ! **{nb_total} événements** générés pour **{mois_val}/{annee_val}**.")

                    # Affichage des métriques
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total événements", nb_total)
                    m2.metric("Vols identifiés", nb_vols)
                    m3.metric("Repos / Réserves", nb_conges)
                    m4.metric("Services / Standby", max(0, nb_autres))

                    # Préparation du CSV en mémoire
                    csv_buffer = io.StringIO()
                    # Export avec BOM utf-8-sig pour Excel et compatibilité Google Calendar
                    df_final.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                    csv_data = csv_buffer.getvalue().encode('utf-8-sig')

                    # Nom de fichier personnalisé
                    pers_suffix = personne_input if personne_input.startswith('_') or not personne_input else f"_{personne_input}"
                    nom_csv = f"Calendar{pers_suffix}_{mois_val}_{annee_val}.csv"

                    # Bouton de téléchargement
                    st.download_button(
                        label=f"📥 Télécharger le CSV Google Calendar ({nom_csv})",
                        data=csv_data,
                        file_name=nom_csv,
                        mime="text/csv",
                        type="primary"
                    )

                    # Téléchargement optionnel du tableau brut
                    raw_buffer = io.StringIO()
                    df_brut.to_csv(raw_buffer, index=False, header=False, sep=';', encoding='utf-8-sig')
                    raw_csv_data = raw_buffer.getvalue().encode('utf-8-sig')
                    nom_raw_csv = f"MonthPlan{pers_suffix}_{mois_val}_{annee_val}.csv"

                    st.download_button(
                        label=f"📊 Télécharger le tableau brut extrait ({nom_raw_csv})",
                        data=raw_csv_data,
                        file_name=nom_raw_csv,
                        mime="text/csv"
                    )

                    # Aperçu du calendrier
                    st.subheader("👀 Aperçu des événements extraits")
                    st.dataframe(df_final, use_container_width=True)

                    # Guide d'importation
                    with st.expander("📖 Comment importer ce fichier dans Google Calendar ?"):
                        st.markdown("""
                        1. Ouvrez [Google Calendar](https://calendar.google.com/).
                        2. Cliquez sur l'icône **Paramètres (roue dentée)** en haut à droite > **Paramètres**.
                        3. Dans le menu de gauche, cliquez sur **Importer et exporter**.
                        4. Cliquez sur **Sélectionner un fichier sur votre ordinateur** et choisissez le fichier CSV téléchargé.
                        5. Choisissez l'agenda cible (nous conseillons de créer un agenda dédié 'Vols' ou 'Planning').
                        6. Cliquez sur **Importer**. Tous vos vols et repos apparaissent instantanément !
                        """)

            except Exception as e:
                st.error(f"❌ Une erreur est survenue lors du traitement : {e}")
                st.exception(e)
else:
    st.info("👆 Veuillez importer un fichier PDF ci-dessus pour commencer.")

    # Exemple interactif pour prévisualiser
    with st.expander("💡 Vous n'avez pas de PDF sous la main ?"):
        st.write("Le programme traitera le document PDF mensuel contenant le tableau de vols (lignes = jours du mois, colonnes = vols successifs de la journée).")
