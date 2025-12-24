#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Discord complet avec commandes CSV, multilingue, modération et logs
Nécessite: discord.py 2.x, python-dotenv
Installation: pip install discord.py python-dotenv
"""

# ========================================
# IMPORTS
# ========================================
import os
import sys
import csv
import json
import logging
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


# Chemins des fichiers
BASE_DIR = Path(__file__).parent
COMMANDS_CSV = BASE_DIR / "commands.csv"
LOGS_DIR = BASE_DIR / "logs"
LANG_DIR = BASE_DIR / "languages"
WARN_FILE = BASE_DIR / "warns.csv"

# Créer les dossiers/fichiers si nécessaires
LOGS_DIR.mkdir(exist_ok=True)
LANG_DIR.mkdir(exist_ok=True)
COMMANDS_CSV.touch(exist_ok=True)
WARN_FILE.touch(exist_ok=True)

#lancement chrono 
start = time.perf_counter()

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
# CONFIGURATION ET INITIALISATION
# ========================================

load_dotenv(dotenv_path="../var.env")

NUDE_CORE_TOKEN = os.getenv("NUDE_CORE_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
CHANNEL_ID_NOTIF = os.getenv("CHANNEL_ID_NOTIF")
ADMIN_ROLE_ID = os.getenv("ADMIN_ROLE_ID")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "fr")
ephemeral_env = os.getenv("EPHEMERAL_GLOBAL", "true").lower()
EPHEMERAL_GLOBAL = ephemeral_env == "true"
VERSION = os.getenv("VERSION")

if not NUDE_CORE_TOKEN:
    logger.error("❌ DISCORD_TOKEN manquant dans les fichiers .env")
    raise ValueError("❌ DISCORD_TOKEN manquant dans les fichiers .env")
elif not GUILD_ID:
    logger.error("❌ GUILD_ID manquant dans les fichiers .env")
    raise ValueError("❌ GUILD_ID manquant dans les fichiers .env")
elif not CHANNEL_ID_NOTIF:
    logger.error("❌ CHANNEL_ID_NOTIF manquant dans les fichiers .env")
    raise ValueError("❌ CHANNEL_ID_NOTIF manquant dans les fichiers .env")
elif not ADMIN_ROLE_ID:
    logger.error("❌ ADMIN_ROLE_ID manquant dans les fichiers .env")
    raise ValueError("❌ ADMIN_ROLE_ID manquant dans les fichiers .env")
elif not DEFAULT_LANGUAGE:
    logger.error("❌ DEFAULT_LANGUAGE manquant dans les fichiers .env")
    raise ValueError("❌ DEFAULT_LANGUAGE manquant dans les fichiers .env")
elif ephemeral_env not in ["true", "false"]:
    logger.error("❌ EPHEMERAL_GLOBAL doit être 'true' ou 'false'") 
    raise ValueError("❌ EPHEMERAL_GLOBAL doit être 'true' ou 'false'")

logger.info(f"✅ Configuration chargée: GUILD_ID={GUILD_ID}, CHANNEL_ID_NOTIF={CHANNEL_ID_NOTIF}, ADMIN_ROLE_ID={ADMIN_ROLE_ID}, DEFAULT_LANGUAGE={DEFAULT_LANGUAGE}, EPHEMERAL_GLOBAL={EPHEMERAL_GLOBAL}")

# ========================================
# GESTION DES LANGUES
# ========================================
class LanguageManager:
    """Gestionnaire de traductions multilingues"""
    def __init__(self):
        self.translations = {}
        self.available_languages = []
        self.user_preferences = {}

    def load_languages(self):
        self.translations.clear()
        self.available_languages.clear()
        files = list(LANG_DIR.glob("*.json"))
        if not files:
            logger.error(f"❌ Aucun fichier de langue dans {LANG_DIR}")
            raise FileNotFoundError("Aucun fichier de traduction")
        for file in files:
            lang_code = file.stem
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                    self.available_languages.append(lang_code)
                logger.info(f"✅ Langue chargée : {lang_code}")
            except Exception as e:
                logger.error(f"❌ Erreur chargement {file}: {e}")
        if not self.available_languages:
            raise ValueError("Aucune langue valide chargée")

    def get(self, key: str, user_id: int = None, **kwargs) -> str:
        lang = self.user_preferences.get(user_id, DEFAULT_LANGUAGE)
        if lang not in self.translations:
            lang = DEFAULT_LANGUAGE
        translation = self.translations.get(lang, {}).get(key, f"[{key}]")
        try:
            return translation.format(**kwargs)
        except KeyError as e:
            logger.warning(f"⚠️ Variable manquante pour '{key}': {e}")
            return translation

    def set_user_language(self, user_id: int, language: str) -> bool:
        if language in self.available_languages:
            self.user_preferences[user_id] = language
            return True
        return False

    def get_language_name(self, lang_code: str) -> str:
        return self.translations.get(lang_code, {}).get("language_name", lang_code)

lang_manager = LanguageManager()

# ========================================
# INITIALISATION DU BOT
# ========================================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
custom_commands = {}
command_cooldowns = defaultdict(lambda: 0)
COMMAND_COOLDOWN = 3

# ========================================
# UTILITAIRES
# ========================================
def t(key: str, interaction: discord.Interaction = None, **kwargs) -> str:
    user_id = interaction.user.id if interaction else None
    return lang_manager.get(key, user_id, **kwargs)

def is_admin(interaction: discord.Interaction) -> bool:
    if not ADMIN_ROLE_ID:
        logger.warning("⚠️ ADMIN_ROLE_ID non défini")
        return False
    try:
        admin_role_id = int(ADMIN_ROLE_ID)
        if interaction.user.guild_permissions.administrator:
            return True
        return any(role.id == admin_role_id for role in interaction.user.roles)
    except ValueError:
        logger.error(f"❌ ADMIN_ROLE_ID invalide : {ADMIN_ROLE_ID}")
        return False

async def check_command_cooldown(user_id: int, channel) -> bool:
    now = time.time()
    if now < command_cooldowns[user_id]:
        remaining = int(command_cooldowns[user_id] - now)  # Convertir en int
        await channel.send(f"⏱️ Cooldown actif ({remaining}s restant)", delete_after=3)
        return False
    command_cooldowns[user_id] = now + COMMAND_COOLDOWN
    return True

def get_ephemeral(interaction: discord.Interaction, default: bool = True) -> bool:
    """Renvoie True si le message doit être éphémère."""
    return EPHEMERAL_GLOBAL if interaction else default

# ========================================
# COMMANDES CSV
# ========================================
def load_custom_commands():
    global custom_commands
    custom_commands.clear()
    if not COMMANDS_CSV.exists():
        COMMANDS_CSV.touch()
        return
    try:
        with open(COMMANDS_CSV, 'r', encoding='utf-8', newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    custom_commands[row[0].strip().lower()] = row[1].strip()
        logger.info(f"✅ {len(custom_commands)} commandes personnalisées chargées")
    except Exception as e:
        logger.error(f"❌ Erreur chargement CSV : {e}")

def save_custom_commands():
    try:
        with open(COMMANDS_CSV, 'w', encoding='utf-8', newline="") as f:
            writer = csv.writer(f)
            for name, resp in custom_commands.items():
                writer.writerow([name, resp])
        return True
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde CSV : {e}")
        return False

# ========================================
# MODÉRATION
# ========================================
WARN_LIMIT = 2
KICK_DURATION = 30

def load_warns():
    warns = {}
    try:
        with open(WARN_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    warns[int(row[0])] = {"count": int(row[1]), "reasons": json.loads(row[2])}
    except Exception as e:
        logger.error(f"Erreur chargement warns: {e}")
    return warns

def save_warns(warns):
    try:
        with open(WARN_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for uid, data in warns.items():
                writer.writerow([uid, data["count"], json.dumps(data["reasons"])])
    except Exception as e:
        logger.error(f"Erreur sauvegarde warns: {e}")

warns_data = load_warns()

# ========================================
# ÉVÉNEMENTS
# ========================================

@bot.event
async def on_ready():
    logger.info(f"✅ Bot connecté en tant que {bot.user}")

    try:
        lang_manager.load_languages()
    except Exception as e:
        logger.critical(f"Impossible de charger les langues : {e}")
        await bot.close()
        return

    load_custom_commands()

    try:
        if GUILD_ID:
            guild_id = int(GUILD_ID)

            # Attendre que le bot soit prêt pour accéder au cache
            await bot.wait_until_ready()

            # Tente de récupérer la guilde depuis le cache
            guild_obj = bot.get_guild(guild_id)

            # Si la guilde n’est pas encore dans le cache, la récupérer depuis l’API
            if guild_obj is None:
                try:
                    guild_obj = await bot.fetch_guild(guild_id)
                    logger.debug(f"Guilde récupérée depuis l’API : {guild_obj.name}")
                except Exception as e:
                    logger.warning(f"Impossible de récupérer la guilde {guild_id} : {e}")
                    guild_obj = discord.Object(id=guild_id)

            # Suppression des anciennes commandes
            await bot.tree.sync(guild=guild_obj)
            logger.info(f"✅ Commandes synchronisées sur la guilde {guild_obj.name} ({GUILD_ID})")

            # Synchronisation des commandes pour la guilde
            await bot.tree.sync(guild=guild_obj)
            guild_name = getattr(guild_obj, "name", "Inconnue")
            logger.info(f"✅ Commandes synchronisées sur la guilde : {guild_name} | ID: {GUILD_ID}")

        else:
            # Synchronisation globale (aucune guilde définie)
            await bot.tree.sync()
            logger.info("✅ Commandes globales synchronisées")

    except Exception as e:
        logger.error(f"Erreur synchronisation commandes : {e}")

    if CHANNEL_ID_NOTIF:
        try:
            channel = bot.get_channel(int(CHANNEL_ID_NOTIF))
            if channel:
                embed = discord.Embed(
                    title=lang_manager.get("bot_online_title"),
                    description=lang_manager.get("bot_online_description"),
                    color=discord.Color.pink()
                )

                embed.add_field(name="Date", value=datetime.now().strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="Heure", value=datetime.now().strftime("%H:%M:%S"), inline=True)
                embed.add_field(name="Version", value=VERSION, inline=True)
                
                embed.set_footer(text=lang_manager.get("bot_online_footer", end = time.perf_counter() - start))

                await channel.send(embed=embed)
                logger.info(f"✅ Message envoyé dans le salon: {channel} | ID: {CHANNEL_ID_NOTIF}")
            else:
                logger.warning("⚠️ CHANNEL_ID_NOTIF introuvable ou non valide.")
        except Exception as e:
            logger.error(f"❌ Impossible d'envoyer la notification de démarrage : {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # DEBUG
    logger.debug("Message raw repr: %r", message.content)
    logger.debug("startswith('/') -> %s", message.content.startswith('/'))

    # Ne traiter que si le premier caractère est '/'
    if message.content and message.content[0] == '/':
        tokens = message.content.split()
        if not tokens:
            return
        command_name = tokens[0].lstrip('/').lower()
        logger.info("Commande détectée en on_message: %s", command_name)

        if command_name in custom_commands:
            await message.channel.send(custom_commands[command_name])
            return

        # vérifier si c'est une commande slash connue — si non informer en DM
        known = [cmd.name for cmd in bot.tree.walk_commands()]
        if command_name not in known:
            try:
                await message.channel.send(t("don_t_understand", command_name=command_name))
            except Exception as e:
                logger.error(f"Erreur en envoyant le message: {e}")
            finally:
                logger.info(f"Commande inconnue: {command_name}")
    await bot.process_commands(message)


# ========================================
# COMMANDES SLASH
# ========================================

# --------- Ping / Info / Help ---------
@bot.tree.command(name="ping", description="Teste la réactivité du bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        t(
            "ping_response",
            interaction,
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        ephemeral=EPHEMERAL_GLOBAL
    )

@bot.tree.command(name="info", description="Info sur le bot")
async def info(interaction: discord.Interaction):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    await interaction.response.send_message(
        t(
            "info_response",
            interaction,
            version=VERSION
        ),
        ephemeral=EPHEMERAL_GLOBAL
)

@bot.tree.command(name="help", description="Affiche toutes les commandes disponibles")
async def help_command(interaction: discord.Interaction):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    embed = discord.Embed(title=t("help_title", interaction), color=discord.Color.blue())
    embed.add_field(name=t("help_system", interaction),
                    value=f"🟢 `/ping`\n🟡 `/reboot`\n🟡 `/upgrade`\n🟡 `/bot_update`",
                    inline=False)
    embed.add_field(name=t("help_csv", interaction),
                    value=f"🟢 `/create`\n🟢 `/modif`\n🟢 `/delete`\n🟢 `/list`\n🟢 `/reload_commands`",
                    inline=False)
    embed.add_field(name="⚠️ Modération",
                    value=f"🟠 `/warn`\n🟠 `/warns`\n🟠 `/unwarn`",
                    inline=False)
    embed.add_field(name="📜 Logs",
                    value=f"🔵 `/logs`\n🔵 `/systemlog`",
                    inline=False)
    embed.add_field(name=t("help_lang", interaction),
                    value=f"🟢 `/language`", inline=False)
    embed.set_footer(text=t("help_footer", interaction))
    await interaction.response.send_message(embed=embed, ephemeral=EPHEMERAL_GLOBAL
)

# --------- Language ---------
@bot.tree.command(name="language", description="Change la langue du bot")
@app_commands.describe(lang="Code de la langue (ex: fr, en)")
async def language_command(interaction: discord.Interaction, lang: str = None):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    if lang is None:
        embed = discord.Embed(title=t("language_title", interaction), color=discord.Color.blue())
        current_lang = lang_manager.user_preferences.get(interaction.user.id, DEFAULT_LANGUAGE)
        embed.description = t("language_current", interaction, language=lang_manager.get_language_name(current_lang)) + "\n\n"
        embed.description += t("language_available", interaction) + "\n"
        for lang_code in sorted(lang_manager.available_languages):
            embed.description += f"• `{lang_code}` - {lang_manager.get_language_name(lang_code)}\n"
        embed.set_footer(text=t("language_usage", interaction))
        await interaction.response.send_message(embed=embed, ephemeral=EPHEMERAL_GLOBAL
)
    else:
        lang = lang.lower().strip()
        if lang_manager.set_user_language(interaction.user.id, lang):
            await interaction.response.send_message(t("language_changed", interaction, language=lang_manager.get_language_name(lang)), ephemeral=EPHEMERAL_GLOBAL
)
        else:
            await interaction.response.send_message(t("language_invalid", interaction, lang=lang), ephemeral=EPHEMERAL_GLOBAL
)

# --------- CSV Commands ---------
@bot.tree.command(name="list", description="Liste toutes les commandes personnalisées")
async def list_commands(interaction: discord.Interaction):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    if not custom_commands:
        await interaction.response.send_message(t("list_empty", interaction), ephemeral=EPHEMERAL_GLOBAL
)
        return
    embed = discord.Embed(title=t("list_title", interaction), color=discord.Color.green())
    embed.description = "\n".join([f"• `/{name}`" for name in sorted(custom_commands.keys())])
    embed.set_footer(text=t("list_footer", interaction, count=len(custom_commands)))
    await interaction.response.send_message(embed=embed, ephemeral=EPHEMERAL_GLOBAL
)

@bot.tree.command(name="create", description="Crée une nouvelle commande personnalisée")
@app_commands.describe(name="Nom de la commande", response="Réponse du bot")
async def create_command(interaction: discord.Interaction, name: str, response: str):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    name_lower = name.lower().strip()
    if name_lower in custom_commands:
        await interaction.response.send_message(t("create_exists", interaction, name=name_lower), ephemeral=EPHEMERAL_GLOBAL
)
        return
    custom_commands[name_lower] = response.strip()
    if save_custom_commands():
        await interaction.response.send_message(t("create_success", interaction, name=name_lower), ephemeral=EPHEMERAL_GLOBAL
)
    else:
        await interaction.response.send_message(t("create_error", interaction), ephemeral=EPHEMERAL_GLOBAL
)

@bot.tree.command(name="modif", description="Modifie le nom et/ou la réponse d'une commande personnalisée")
@app_commands.describe(
    old_name="Nom actuel de la commande à modifier",
    new_name="Nouveau nom de la commande (optionnel)",
    new_response="Nouvelle réponse du bot (optionnel)"
)
async def modify_command(
    interaction: discord.Interaction,
    old_name: str,
    new_name: Optional[str] = None,
    new_response: Optional[str] = None
):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    old_name_lower = old_name.lower().strip()

    # Vérifie si la commande existe
    if old_name_lower not in custom_commands:
        await interaction.response.send_message(
            t("modif_not_found", interaction, name=old_name_lower),
            ephemeral=EPHEMERAL_GLOBAL
        )
        return

    # Aucun changement fourni
    if not new_name and not new_response:
        await interaction.response.send_message(
            t("modif_no_change", interaction, name=old_name_lower),
            ephemeral=EPHEMERAL_GLOBAL
        )
        return

    # Sauvegarde de la commande originale
    old_response = custom_commands[old_name_lower]
    success = False

    try:
        # Si un nouveau nom est fourni
        if new_name:
            new_name_lower = new_name.lower().strip()
            # Empêche d'écraser une autre commande existante
            if new_name_lower != old_name_lower and new_name_lower in custom_commands:
                await interaction.response.send_message(
                    t("modif_name_exists", interaction, name=new_name_lower),
                    ephemeral=EPHEMERAL_GLOBAL
                )
                return
            # Déplace la commande
            custom_commands[new_name_lower] = custom_commands.pop(old_name_lower)
            old_name_lower = new_name_lower  # met à jour la clé

        # Si une nouvelle réponse est donnée
        if new_response:
            custom_commands[old_name_lower] = new_response.strip()

        # Sauvegarde
        success = save_custom_commands()

    except Exception as e:
        logger.error(f"Erreur lors de la modification d'une commande : {e}")
        success = False

    if success:
        await interaction.response.send_message(
            t("modif_success", interaction, name=old_name_lower),
            ephemeral=EPHEMERAL_GLOBAL
        )
    else:
        await interaction.response.send_message(
            t("modif_error", interaction, name=old_name_lower),
            ephemeral=EPHEMERAL_GLOBAL
        )

@bot.tree.command(name="delete", description="Supprime une commande personnalisée existante")
@app_commands.describe(name="Nom de la commande à supprimer")
async def delete_command(interaction: discord.Interaction, name: str):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    name_lower = name.lower().strip()

    # Vérifie si la commande existe
    if name_lower not in custom_commands:
        await interaction.response.send_message(
            t("delete_not_found", interaction, name=name_lower),
            ephemeral=EPHEMERAL_GLOBAL
        )
        return

    # Supprime la commande
    try:
        del custom_commands[name_lower]

        # Sauvegarde les changements
        if save_custom_commands():
            await interaction.response.send_message(
                t("delete_success", interaction, name=name_lower),
                ephemeral=EPHEMERAL_GLOBAL
            )
        else:
            await interaction.response.send_message(
                t("delete_error", interaction, name=name_lower),
                ephemeral=EPHEMERAL_GLOBAL
            )

    except Exception as e:
        logger.error(f"Erreur lors de la suppression d'une commande : {e}")
        await interaction.response.send_message(
            t("delete_exception", interaction, name=name_lower),
            ephemeral=EPHEMERAL_GLOBAL
        )

# --------- Modération ---------
@bot.tree.command(name="warn", description="Met un warn à un utilisateur")
@app_commands.describe(user="Utilisateur", reason="Raison")
async def warn_command(interaction: discord.Interaction, user: discord.Member, reason: str):
    cmd_user = interaction.user
    cmd_name = interaction.command.name
    logger.info(f"L'utilisateur {cmd_user} a exécuté la commande {cmd_name}")

    if not is_admin(interaction):
        await interaction.response.send_message(
            t("permission_denied", interaction),
            ephemeral=EPHEMERAL_GLOBAL
        )
        return

    uid = user.id
    warns_data.setdefault(uid, {"count": 0, "reasons": []})
    warns_data[uid]["count"] += 1
    warns_data[uid]["reasons"].append(reason)
    save_warns(warns_data)

    await interaction.response.send_message(
        f"{user.mention} reçoit un warn ({reason}). Total: {warns_data[uid]['count']}",
        ephemeral=EPHEMERAL_GLOBAL
    )

    if warns_data[uid]["count"] >= WARN_LIMIT:
        await interaction.channel.send(f"{user.mention} kick temporaire ({KICK_DURATION}s)")
        try:
            # CORRECTION: Utiliser datetime.now(timezone.utc) au lieu de utcnow()
            timeout_until = datetime.now(timezone.utc) + timedelta(seconds=KICK_DURATION)
            await user.edit(timed_out_until=timeout_until)
        except Exception as e:
            logger.error(f"Erreur kick temporaire: {e}")

@bot.tree.command(name="warns", description="Voir warns utilisateur")
@app_commands.describe(user="Utilisateur")
async def warns_check(interaction: discord.Interaction, user: discord.Member):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    uid = user.id
    data = warns_data.get(uid)
    if not data:
        await interaction.response.send_message(f"{user.mention} n'a aucun warn.", ephemeral=EPHEMERAL_GLOBAL
)
        return
    msg = f"Warns pour {user.mention} :\n"
    for i, reason in enumerate(data["reasons"], start=1):
        msg += f"{i}. {reason}\n"
    await interaction.response.send_message(msg, ephemeral=EPHEMERAL_GLOBAL
)

@bot.tree.command(name="unwarn", description="Supprime un warn d'un utilisateur")
@app_commands.describe(user="Utilisateur", number="Numéro du warn à supprimer (optionnel)")
async def unwarn_command(interaction: discord.Interaction, user: discord.Member, number: int = None):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    if not is_admin(interaction):
        await interaction.response.send_message("permission_denied", ephemeral=EPHEMERAL_GLOBAL
)
        return
    uid = user.id
    data = warns_data.get(uid)
    if not data or data["count"] == 0:
        await interaction.response.send_message(f"{user.mention} n'a aucun warn.", ephemeral=EPHEMERAL_GLOBAL
)
        return
    if number is None:
        removed_reason = data["reasons"].pop()
        data["count"] -= 1
        action = f"Le dernier warn a été supprimé : {removed_reason}"
    else:
        if number < 1 or number > data["count"]:
            await interaction.response.send_message(f"Numéro de warn invalide. Total: {data['count']}", ephemeral=EPHEMERAL_GLOBAL
)
            return
        removed_reason = data["reasons"].pop(number - 1)
        data["count"] -= 1
        action = f"Le warn #{number} a été supprimé : {removed_reason}"
    if data["count"] == 0:
        warns_data.pop(uid)
    else:
        warns_data[uid] = data
    save_warns(warns_data)
    await interaction.response.send_message(f"{user.mention} - {action}", ephemeral=EPHEMERAL_GLOBAL
)
#a finir

@bot.tree.command(name="report", description="Signale un groupe de message au staff")
@app_commands.describe(nombre="Nombre de messages à signaler (10-50)", reason="Raison du signalement")
async def report_command(interaction: discord.Interaction, nombre: int, reason: str):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    await interaction.response.send_message(
        "🚧 Fonctionnalité en construction.",
        ephemeral=EPHEMERAL_GLOBAL
    )

# --------- Logs ---------
@bot.tree.command(name="logs", description="Affiche les derniers logs du bot")
async def logs_command(interaction: discord.Interaction):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    await interaction.response.defer(ephemeral=EPHEMERAL_GLOBAL
)
    try:
        log_files = sorted(LOGS_DIR.glob("bot_*.log"), reverse=True)
        if not log_files:
            await interaction.followup.send("❌ Aucun fichier de log trouvé.", ephemeral=EPHEMERAL_GLOBAL
)
            return
        latest_file = log_files[0]
        content = latest_file.read_text(encoding="utf-8")[-1900:]
        embed = discord.Embed(title=f"📜 Logs Bot ({latest_file.name})",
                              description=f"```{content}```",
                              color=discord.Color.green())
        await interaction.followup.send(embed=embed, ephemeral=EPHEMERAL_GLOBAL
)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lecture logs: {e}", ephemeral=EPHEMERAL_GLOBAL
)

# --------- Système ---------

@bot.tree.command(name="reboot", description="Redémarre le bot") 
async def reboot_command(interaction: discord.Interaction):
    cmd_user = interaction.user
    cmd_name = interaction.command.name
    logger.info(f"L'utilisateur {cmd_user} a exécuté la commande {cmd_name}")

    if not is_admin(interaction):
        await interaction.response.send_message(
            t("permission_denied", interaction),
            ephemeral=EPHEMERAL_GLOBAL
        )
        return  # Ce return est correct ici

    # Code exécuté seulement si admin
    await interaction.response.send_message(
        "🔄 Redémarrage du bot...",
        ephemeral=EPHEMERAL_GLOBAL
    )

    logger.info("🔄 Redémarrage demandé par %s", interaction.user)
    await bot.close()
    os.execv(sys.executable, [sys.executable] + sys.argv)@bot.tree.command(name="upgrade", description="Met à jour le bot depuis Git")
async def upgrade_command(interaction: discord.Interaction):
    cmd_user = interaction.user
    cmd_name = interaction.command.name
    logger.info(f"L'utilisateur {cmd_user} a exécuté la commande {cmd_name}")

    if not is_admin(interaction):
        await interaction.response.send_message(
            t("permission_denied", interaction),
            ephemeral=EPHEMERAL_GLOBAL
        )
        return  # Ce return est correct ici

    # Code exécuté seulement si admin
    await interaction.response.send_message(
        "⬆️ Mise à jour du bot en cours...",
        ephemeral=EPHEMERAL_GLOBAL
    )
    logger.info("⬆️ Mise à jour demandée par %s", interaction.user)

    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        output = result.stdout + "\n" + result.stderr
        logger.info("Git pull output:\n%s", output)
        await bot.close()
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour: {e}")
        await interaction.followup.send(
            f"❌ Erreur mise à jour: {e}",
            ephemeral=EPHEMERAL_GLOBAL
        )

@bot.tree.command(name="ephemeral", description="Active ou désactive les messages éphémères")
@app_commands.describe(option="true pour activer, false pour désactiver")
async def ephemeral_command(interaction: discord.Interaction, option: bool):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    global EPHEMERAL_GLOBAL
    if not is_admin(interaction):
        await interaction.response.send_message("permission_denied", ephemeral=True
)
        return

    EPHEMERAL_GLOBAL = option
    status = "activés" if EPHEMERAL_GLOBAL else "désactivés"
    await interaction.response.send_message(f"✅ Les messages éphémères sont maintenant {status}.", ephemeral=EPHEMERAL_GLOBAL
)

# ----------- Test -----------
@bot.tree.command(name="test", description="Commande de test")
async def test_command(interaction: discord.Interaction):
    user = interaction.user
    name = interaction.command.name
    logger.info(f"L'utilisateur {user} a exécuté la commande {name}")
    await interaction.response.send_message("✅ Test réussi!", ephemeral=EPHEMERAL_GLOBAL
)

# ========================================
# LANCEMENT DU BOT
# ========================================
if __name__ == "__main__":
    bot.run(NUDE_CORE_TOKEN)