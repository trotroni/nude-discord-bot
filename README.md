# Bot Discord – Gestion de Dettes & Tickets (COMPTA)

Bot Discord permettant de gérer simplement des **dettes entre utilisateurs**, via un système de **tickets**, avec calcul automatique des soldes, historique et remboursements.

---

## I - Fonctionnalités principales

* Création de tickets de dettes (P2P ou groupe)
* ID de ticket généré automatiquement
* Calcul intelligent des montants (partage équitable, gestion des centimes)
* Consultation du solde d’un utilisateur
* Remboursement partiel ou total
* Suppression / archivage des tickets
* Logs automatiques
* Stockage JSON (léger, lisible, versionnable)

---

## II - Arborescence du projet

```text
.
├── bot.py
├── setup.py
├── var.env
├── README.md
├── storage.py
├── tickets.py
├── utils.py
├── data
│   ├── tickets.json
│   ├── archives.json
│   └── events.log
├── logs
│   └── debug.log
└── __pycache__
```

---

## III - Configuration et installation

### 1 - Prérequis

* Python **3.10+**
* Un bot Discord (Discord Developer Portal)
* Permissions activées :

  * `applications.commands`
  * `Send Messages`
  * `Embed Links`

---

### 2 - Installation des dépendances

```bash
pip install -r requirements.txt
```

---

### 3 - Initialisation automatique du projet (obligatoire)

Avant **tout premier lancement**, exécute :

```bash
python setup.py
```

Ce script :

* crée automatiquement les dossiers :

  * `data/`
  * `logs/`
* crée les fichiers requis :

  * `data/tickets.json`
  * `data/archives.json`
  * `data/events.log`
  * `logs/debug.log`
* évite toute erreur liée à des fichiers manquants

Le script peut être relancé sans risque (aucune suppression).

---

### 4 - Configuration du bot

Une fois `setup.py` executé, `var.env` apparait à la racine :

```env
TOKEN=VOTRE_TOKEN_DISCORD
GUILD_ID=ID_DU_SERVEUR
LOG_CHANNEL_ID=ID_DU_CHANNEL_LOGS
```

| Variable       | Description                    |
|----------- |--------------------------- |
| TOKEN          | Token du bot Discord           |
| GUILD_ID       | ID du serveur                  |
| LOG_CHANNEL_ID | Salon où sont envoyés les logs |

---

### 5 - Lancer le bot

```bash
python bot.py
```

Le bot :

* synchronise automatiquement les commandes slash
* devient immédiatement utilisable

---

## IV - Lien d’invitation du bot

```
https://discord.com/oauth2/authorize?client_id=1449158700852842607
```

---

## V - Commandes disponibles

---

### `/new_ticket`

Créer un nouveau ticket de dette.

#### ➤ Cas 1 : Dette simple (P2P)

```text
/new_ticket @utilisateur_qui_doit montant @utilisateur_qui_reçoit motif
```

**Exemple :**

> `/new_ticket @Alice 20 @Bob Cinéma`

**Résultat :**

> Alice doit 20€ à Bob pour Cinéma

* ID généré automatiquement
* ID commence par **`a`** (ticket P2P)

---

#### ➤ Cas 2 : Plusieurs débiteurs

```text
/new_ticket @user1 @user2 montant @crediteur motif
```

**Calcul :**

* Montant divisé équitablement entre les débiteurs

* Si centime impair :

  * le centime supplémentaire est attribué à l’utilisateur ayant **le moins de dettes**
  * un message d’information est affiché

* ID commence par **`b`** (ticket groupe)

---

### `/solde [@utilisateur]`

Afficher le solde d’un utilisateur.

**Affiche :**

* Ce que **les autres lui doivent**
* Ce qu’**il doit aux autres**
* Le **total net cumulé**

Sans argument → affiche ton propre solde.

---

### `/rembourse montant @utilisateur`

Rembourse une partie ou la totalité d’une dette.

* Soustrait le montant du ticket concerné
* Met à jour automatiquement le solde

---

### `/del_ticket id`

Supprime un ticket actif.

* Le ticket est retiré des tickets actifs
* Les données sont archivées

---

### `/edit_ticket id`

Permet de modifier un ticket existant
(montant, motif, utilisateurs concernés).

---

### `/list`

Liste **tous les tickets actifs**.

Pour chaque ticket :

* débiteurs
* créditeur
* montant restant
* motif

---

## VI - Logique interne

* Tous les montants sont stockés en **centimes**
* Les tickets actifs sont dans `data/tickets.json`
* Les tickets supprimés sont archivés dans `data/archives.json`
* Tous les événements sont tracés dans `events.log`

---

## VII - Technologies utilisées

* Python
* discord.py (app_commands)
* JSON (stockage)
* dotenv

---

## VIII - Notes

* Le bot est conçu pour être **simple, transparent et robuste**
* Aucun système de base de données requis
* Idéal pour groupes d’amis, colocations
