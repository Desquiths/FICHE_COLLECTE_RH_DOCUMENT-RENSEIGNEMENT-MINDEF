# SYSGEND - Fiche collecte RH
# Deploiement Render (gratuit)
# https://render.com

## Étape 1 : Créer un compte
- Aller sur https://render.com
- Sign up (gratuit, carte bancaire demandée mais gratuit 75$/mois)

## Étape 2 : Créer un repo GitHub
- Pousser le dossier /home/phantom/app sur un repo public
- Fichiers importants : app.py, columns.json, templates/, static/, requirements.txt

## Étape 3 : Sur Render
- New Web Service
- Connecter le repo GitHub
- Nom : sysgend
- Region : Oregon (ou proche de vous)
- Build command : pip install -r requirements.txt
- Start command : gunicorn app:app
- Environment : Python 3.11

## Étape 4 : Accès
- Render fournit https://sysgend.onrender.com (ou le nom que vous choisissez)

## Notes
- SQLite stocke data.db dans le disque Render (éphémayer, perdu au redéploiement).
- Pour persistence, migrer vers PostgreSQL (Render gratuit inclut 25 Mois de base).
- Authentification admin : admin/admin (changer en prod !)