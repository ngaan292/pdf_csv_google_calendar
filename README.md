# ✈️ Mom Calendar - Convertisseur de Planning PDF vers CSV

Application Streamlit permettant de convertir automatiquement les plannings de vol mensuels (PDF) en fichiers CSV directement compatibles avec **Google Calendar**, **Outlook** et **Apple Calendar**.

---

## 🌟 Fonctionnalités

- 📂 **Import simple** de fichier PDF par glisser-déposer.
- 🔍 **Détection automatique** du mois et de l'année (depuis le nom du fichier ou date d'upload).
- 🏷️ **Nom personnalisable** de la personne pour l'organisation et le nommage des fichiers.
- 🛫 **Résolution automatique des aéroports IATA** (ex: `HAN` ➔ `Noi Bai Intl Hanoi`).
- ⏱️ **Conversion de fuseau horaire** (de l'UTC vers `Asia/Bangkok` UTC+7 ou autre fuseau sélectionné).
- 📅 **Gestion complète des activités** :
  - Vols réguliers et vols de continuation / escale.
  - Jours de repos (`Dayoff`, `Reserve day`).
  - Standbys et journées de service au sol / départements.
- 📥 **Téléchargement direct** du CSV prêt à importer dans Google Calendar.
- 📊 **Téléchargement optionnel** du tableau brut extrait (format Excel/CSV).

---

## 🚀 Utilisation en local

### 1. Cloner ou télécharger le dépôt
```bash
git clone https://github.com/votre-nom-utilisateur/mom_calendar.git
cd mom_calendar
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Lancer l'application Streamlit
```bash
streamlit run app.py
```
L'application s'ouvrira automatiquement dans votre navigateur à l'adresse `http://localhost:8501`.

---

## ☁️ Déploiement gratuit sur Streamlit Cloud

Pour rendre l'application accessible en ligne à tout moment depuis un PC, une tablette ou un smartphone :

1. **Créer un dépôt GitHub** :
   - Rendez-vous sur [GitHub](https://github.com/) et créez un nouveau dépôt public (ex: `mom_calendar`).
   - Poussez les fichiers suivants sur GitHub :
     ```bash
     git init
     git add app.py pdf_csv_calendar.py requirements.txt IATAlocationcodes.json .gitignore README.md
     git commit -m "Initial commit - Mom Calendar Streamlit App"
     git branch -M main
     git remote add origin https://github.com/VOTRE_PSEUDO/mom_calendar.git
     git push -u origin main
     ```

2. **Déployer sur Streamlit Cloud** :
   - Rendez-vous sur [share.streamlit.io](https://share.streamlit.io/) et connectez-vous avec votre compte GitHub.
   - Cliquez sur **"New app"**.
   - Sélectionnez votre dépôt `mom_calendar`, la branche `main`, et spécifiez le fichier principal : **`app.py`**.
   - Cliquez sur **"Deploy!"**.

En moins de 2 minutes, votre application sera en ligne avec une URL partageable (ex: `https://mom-calendar.streamlit.app`).

---

## 📖 Comment importer dans Google Calendar ?

1. Rendez-vous sur [Google Calendar](https://calendar.google.com/).
2. Cliquez sur l'icône **Paramètres (roue dentée)** en haut à droite > **Paramètres**.
3. Dans le menu de gauche, cliquez sur **Importer et exporter**.
4. Cliquez sur **Sélectionner un fichier sur votre ordinateur** et choisissez le fichier CSV téléchargé.
5. Sélectionnez l'agenda cible (nous recommandons de créer un agenda dédié *Planning* ou *Vols*).
6. Cliquez sur **Importer**. Tous vos vols et repos apparaissent avec leurs horaires précis !

---

## 📁 Structure du projet

```
mom_calendar/
├── app.py                  # Interface web interactive Streamlit
├── pdf_csv_calendar.py     # Script autonome CLI & moteur de conversion
├── requirements.txt        # Dépendances Python nécessaires
├── IATAlocationcodes.json  # Base de données des codes et villes d'aéroports
├── .gitignore              # Fichiers à exclure de git
└── README.md               # Guide d'utilisation et de déploiement
```
