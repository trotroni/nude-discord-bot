#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Discord complet avec commandes CSV, multilingue, modération et logs
Synchronisation uniquement locale (sur la guilde)
Nécessite: discord.py 2.x, python-dotenv
Installation: pip install discord.py python-dotenv
"""

# ========================================
# IMPORTS
# ========================================
import os
import csv
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

#lancement chrono 
start = time.perf_counter()

# ========================================
# CHEMINS DES FICHIERS
# ========================================
BASE_DIR = Path(__file__).parent
COMMANDS_CSV = BASE_DIR / "commands.csv"
LOGS_DIR = BASE_DIR / "logs"
LANG_DIR = BASE_DIR / "languages"
WARN_FILE = BASE_DIR / "warns.csv"

# Création des dossiers/fichiers si nécessaire
LOGS_DIR.mkdir(exist_ok=True)
LANG_DIR.mkdir(exist_ok=True)
COMMANDS_CSV.touch(exist_ok=True)
WARN_FILE.touch(exist_ok=True)

VERSION = "v.6.1.0-test - 2025-11-11"
AUTOR = "Trotroni"

start_time = time.perf_counter()
custom_commands = {}

# ========================================
# LOGGING
# ========================================
log_filename = LOGS_DIR / f"bot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DiscordBot")

# ========================================
# CONFIGURATION
# ========================================
load_dotenv("../var.env")
load_dotenv("token.env", override=True)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
#GUILD_ID = int(os.getenv("GUILD_ID", 0))
GUILD_ID=1417564002896314533
CHANNEL_ID_NOTIF = int(os.getenv("CHANNEL_ID_NOTIF", 0))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 0))
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "fr")
EPHEMERAL_GLOBAL = os.getenv("EPHEMERAL_GLOBAL", "true").lower() == "true"

for var_name, value in [("DISCORD_TOKEN", DISCORD_TOKEN), ("GUILD_ID", GUILD_ID),
                        ("CHANNEL_ID_NOTIF", CHANNEL_ID_NOTIF), ("ADMIN_ROLE_ID", ADMIN_ROLE_ID)]:
    if not value:
        logger.error(f"❌ {var_name} manquant")
        raise ValueError(f"{var_name} manquant")

logger.info(f"✅ Config OK | GUILD_ID={GUILD_ID} | EPHEMERAL={EPHEMERAL_GLOBAL} | CHANNEL_ID_NOTIF={CHANNEL_ID_NOTIF} | ADMIN_ROLE_ID={ADMIN_ROLE_ID}")

# ========================================
# GESTION DES LANGUES
# ========================================
class LanguageManager:
    def __init__(self):
        self.translations = {}
        self.available_languages = []
        self.user_preferences = {}

    def load_languages(self):
        self.translations.clear()
        self.available_languages.clear()
        files = list(LANG_DIR.glob("*.json"))
        if not files:
            raise FileNotFoundError(f"Aucun fichier langue dans {LANG_DIR}")
        for file in files:
            lang_code = file.stem
            with open(file, encoding="utf-8") as f:
                self.translations[lang_code] = json.load(f)
                self.available_languages.append(lang_code)
                logger.info(f"✅ Langue chargée : {lang_code}")

    def get(self, key, user_id=None, **kwargs):
        lang = self.user_preferences.get(user_id, DEFAULT_LANGUAGE)
        if lang not in self.translations:
            lang = DEFAULT_LANGUAGE
        translation = self.translations.get(lang, {}).get(key, f"[{key}]")
        try:
            return translation.format(**kwargs)
        except KeyError:
            return translation

lang_manager = LanguageManager()
def t(key, interaction=None, **kwargs):
    user_id = interaction.user.id if interaction else None
    return lang_manager.get(key, user_id, **kwargs)

# ========================================
# BOT ET INTENTS
# ========================================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

# ========================================
# COMMANDES CSV
# ========================================
from discord import app_commands
import discord

def load_custom_commands():
    global custom_commands
    custom_commands.clear()
    if not COMMANDS_CSV.exists():
        return
    try:
        with open(COMMANDS_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row['name']
                cmd_id = int(row['id'])
                reponse = row['reponse']
                custom_commands[name] = {'id': cmd_id, 'reponse': reponse}
        logger.info(f"✅ {len(custom_commands)} commandes CSV chargées")
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement des commandes CSV : {e}")

def save_custom_commands():
    try:
        with open(COMMANDS_CSV, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['id', 'name', 'reponse']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for name, data in custom_commands.items():
                writer.writerow({'id': data['id'], 'name': name, 'reponse': data['reponse']})
        logger.info(f"💾 {len(custom_commands)} commandes CSV sauvegardées")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la sauvegarde des commandes CSV : {e}")

# ========================================
# ÉVÉNEMENTS
# ========================================
@bot.event
async def on_ready():
    logger.info(f"✅ Bot connecté en tant que {bot.user}")

    # Charger langues, commandes CSV et warns
    lang_manager.load_languages()
    load_custom_commands()
    load_warns()

    # Récupération fiable de la guilde
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        try:
            guild = await bot.fetch_guild(GUILD_ID)
            logger.info(f"✅ Guilde récupérée depuis l'API : {guild.name}")
        except Exception as e:
            logger.error(f"❌ Impossible de récupérer la guilde {GUILD_ID} : {e}")
            return  # On quitte ici si la guilde est introuvable

    # Supprimer toutes les commandes locales existantes
    try:
        existing_commands = await bot.tree.fetch_commands(guild=guild)
        for cmd in existing_commands:
            await bot.tree.remove_command(cmd.name, type=app_commands.AppCommandType.chat_input, guild=guild)
        logger.info(f"🗑️ {len(existing_commands)} commandes locales supprimées")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la suppression des commandes locales : {e}")

    # Synchroniser les nouvelles commandes
    try:
        await bot.tree.sync(guild=guild)
        logger.info(f"✅ Commandes synchronisées sur la guilde : {guild.name} (ID : {guild.id})")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la synchronisation des commandes : {e}")

    # Message de notification dans un salon (optionnel)
    if CHANNEL_ID_NOTIF:
        try:
            channel = bot.get_channel(CHANNEL_ID_NOTIF)
            if channel:
                embed = discord.Embed(
                    title=lang_manager.get("bot_online_title"),
                    description=lang_manager.get("bot_online_description"),
                    color=discord.Color.pink()
                )
                embed.add_field(name="Date", value=datetime.now().strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="Heure", value=datetime.now().strftime("%H:%M:%S"), inline=True)
                embed.add_field(name="Version", value=VERSION, inline=True)
                embed.set_footer(text=lang_manager.get("bot_online_footer", end=time.perf_counter() - start))
                await channel.send(embed=embed)
                logger.info(f"✅ Message envoyé dans le salon : {channel} (ID : {CHANNEL_ID_NOTIF})")
            else:
                logger.warning("⚠️ CHANNEL_ID_NOTIF introuvable ou non valide.")
        except Exception as e:
            logger.error(f"❌ Impossible d'envoyer la notification de démarrage : {e}")

# ========================================
# Groupe CSV
# ========================================
class CSVCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="csv", description="Gestion des commandes CSV")

    def _get_next_id(self):
        if not custom_commands:
            return 1
        return max(data["id"] for data in custom_commands.values()) + 1

    @app_commands.command(name="create", description="Créer une nouvelle commande")
    @app_commands.describe(name="Nom de la commande", reponse="Réponse de la commande")
    async def create(self, interaction: discord.Interaction, name: str, reponse: str):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        if name in custom_commands:
            await interaction.response.send_message(f"⚠️ La commande `{name}` existe déjà", ephemeral=True)
            return
        cmd_id = self._get_next_id()
        custom_commands[name] = {"id": cmd_id, "reponse": reponse}
        save_custom_commands()
        await interaction.response.send_message(f"✅ Commande `{name}` créée avec ID {cmd_id}", ephemeral=True)

    @app_commands.command(name="edit", description="Modifier une commande existante")
    @app_commands.describe(name="Nom de la commande", reponse="Nouvelle réponse")
    async def edit(self, interaction: discord.Interaction, name: str, reponse: str):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        if name not in custom_commands:
            await interaction.response.send_message(f"⚠️ La commande `{name}` n'existe pas", ephemeral=True)
            return
        custom_commands[name]["reponse"] = reponse
        save_custom_commands()
        await interaction.response.send_message(f"✅ Commande `{name}` mise à jour !", ephemeral=True)

    @app_commands.command(name="delete", description="Supprimer une commande")
    @app_commands.describe(name="Nom de la commande")
    async def delete(self, interaction: discord.Interaction, name: str):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        if name not in custom_commands:
            await interaction.response.send_message(f"⚠️ La commande `{name}` n'existe pas", ephemeral=True)
            return
        del custom_commands[name]
        save_custom_commands()
        await interaction.response.send_message(f"✅ Commande `{name}` supprimée !", ephemeral=True)

    @app_commands.command(name="list", description="Lister toutes les commandes")
    async def list_cmds(self, interaction: discord.Interaction):
        if not custom_commands:
            await interaction.response.send_message("📄 Aucune commande personnalisée", ephemeral=True)
            return
        cmds = "\n".join([f"- ID {data['id']} : `{name}` → {data['reponse']}" for name, data in custom_commands.items()])
        await interaction.response.send_message(f"📄 Commandes personnalisées :\n{cmds}", ephemeral=True)

    @app_commands.command(name="reload", description="Recharger les commandes depuis le CSV")
    async def reload(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        load_custom_commands()
        await interaction.response.send_message(f"🔄 {len(custom_commands)} commandes rechargées depuis le CSV", ephemeral=True)

# ========================================
# Ajouter le groupe au bot
# ========================================
bot.tree.add_command(CSVCommands())


# ========================================
# MODÉRATION
# ========================================
WARN_LIMIT = 2
KICK_DURATION = 30
warns_data = {}

def load_warns():
    global warns_data
    warns_data.clear()
    try:
        with open(WARN_FILE, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    warns_data[int(row[0])] = {"count": int(row[1]), "reasons": json.loads(row[2])}
    except Exception:
        pass

def save_warns():
    with open(WARN_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for uid, data in warns_data.items():
            writer.writerow([uid, data["count"], json.dumps(data["reasons"])])

def is_admin(interaction):
    if interaction.user.guild_permissions.administrator:
        return True
    return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)

# ========================================
# COMMANDES SLASH
# ========================================
@bot.tree.command(name="ping", description="Teste la réactivité du bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        t("ping_response", interaction, time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ephemeral=EPHEMERAL_GLOBAL
    )

# Commande de modération warn
@bot.tree.command(name="warn", description="Met un warn à un utilisateur")
@app_commands.describe(user="Utilisateur", reason="Raison")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_admin(interaction):
        await interaction.response.send_message("permission_denied", ephemeral=EPHEMERAL_GLOBAL)
        return
    uid = user.id
    warns_data.setdefault(uid, {"count": 0, "reasons": []})
    warns_data[uid]["count"] += 1
    warns_data[uid]["reasons"].append(reason)
    save_warns()
    await interaction.response.send_message(f"{user.mention} reçoit un warn ({reason}). Total: {warns_data[uid]['count']}", ephemeral=EPHEMERAL_GLOBAL)
    if warns_data[uid]["count"] >= WARN_LIMIT:
        await interaction.channel.send(f"{user.mention} kick temporaire ({KICK_DURATION}s)")
        try:
            await user.edit(communication_disabled_until=datetime.utcnow() + timedelta(seconds=KICK_DURATION))
        except Exception as e:
            logger.error(f"Erreur kick temporaire: {e}")

# ========================================
# LANCEMENT DU BOT
# ========================================
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
