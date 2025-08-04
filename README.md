```markdown

# Application System-ST

## Remarque importante :

L'application peut ne pas fonctionner immédiatement après le clonage du dépôt, en raison d'un paramétrage volontairement incomplet dans le fichier :

services/odoo_client.py

Pour des raisons de confidentialité, les paramètres de connexion à la base de données Odoo ont été retirés.

Veuillez adapter les variables d’environnement suivantes selon votre propre instance Odoo :

ODOO_URL : Lien vers votre serveur Odoo (ex. https://votre-instance.odoo.com)

ODOO_DB : Nom de votre base de données Odoo

ODOO_USERNAME : Nom d'utilisateur Odoo (souvent une adresse e-mail)

ODOO_PASSWORD : Mot de passe associé

## Résumé

**System-ST** est une application de gestion de services. À l’instar des plateformes de freelance, son objectif est de **mettre en relation des prestataires de services (consultants)** avec des **clients (entrepreneurs)** via un système de demandes, d’offres et de collaboration encadrée.

---

## Étapes après un `git clone`

### 1. Créer et activer un environnement virtuel (optionnel mais recommandé)

```bash
python -m venv venv
source venv/bin/activate      # Sur Mac/Linux
venv\Scripts\activate         # Sur Windows

### 2. Installer les dépendances

pip install -r requirements.txt

Si le fichier requirements.txt est manquant, tu peux le générer depuis une machine où le projet fonctionne avec :

pip freeze > requirements.txt

### 3. Créer les fichiers de base de données

a. Appliquer les migrations

python manage.py migrate

Cela va :

* créer le fichier db.sqlite3,
* générer toutes les tables nécessaires à l'application.

b. À noter :
Si vous voyez ce message :

No migrations to apply.

=> C’est normal si toutes les migrations ont déjà été appliquées.

### 4. Lancer le serveur

a. Lancer le backend (Django)
Dans le terminal, placez-vous dans le dossier :

system-st/backend

Puis lancez :

python manage.py runserver

b. Lancer le frontend (React)
Ouvre un deuxième terminal, placez-vous dans :

system-st/frontend

Puis lancez :

npm install
npm start

L'interface s’ouvrira automatiquement dans ton navigateur à l’adresse http://localhost:3000.

## Comptes de test

### Administrateur
* Rôle : Gère les utilisateurs, leurs rôles et les demandes.
* Identifiant : Admin1
* Mot de passe : User123!

### Entrepreneur (client)
* Rôle : Soumet des demandes de services.
* Identifiant : Entrepreneur1
* Mot de passe : User123!

### Consultant (prestataire)
* Rôle : Soumet des offres en réponse aux demandes.
* Identifiant : Prestataire1
* Mot de passe : User123!

Vous pouvez également créer de nouveaux utilisateurs pour tester votre propre base de données.

## Technologies principales
* Backend : Django 4.2 + Django REST Framework
* Frontend : React + Axios
* Base de données : SQLite (par défaut)
* Authentification : JWT
* Intégration Odoo : XML-RPC pour création de partenaires et bons de commande

