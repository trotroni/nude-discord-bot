# setup.py
import os
import json

# Arborescence à créer
folders = [
    "data",
    "logs",
    "__pycache__"
]

files = {
    "data/tickets.json": {},
    "data/archives.json": {},
    "data/events.log": "",
    "logs/debug.log": "",
    "var.env": """TOKEN=VOTRE_TOKEN_DISCORD
GUILD_ID=ID_DU_SERVEUR
LOG_CHANNEL_ID=ID_DU_CHANNEL_LOGS"""
}

# Création des dossiers
for folder in folders:
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"Dossier créé : {folder}")

# Création des fichiers
for file_path, default_content in files.items():
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            if isinstance(default_content, dict):
                json.dump(default_content, f, indent=2, ensure_ascii=False)
            else:
                f.write(default_content)
        print(f"Fichier créé : {file_path}")

print("Configuration initiale terminée !")
