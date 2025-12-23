import re
import csv

# Fichier source contenant tes commandes
input_file = "main.py"
# Fichier CSV de sortie
output_file = "commands_help.csv"

# Regex pour capturer name et description
pattern = re.compile(
    r'@bot\.tree\.command\s*\(\s*name\s*=\s*"([^"]+)"\s*,\s*description\s*=\s*"([^"]+)"\s*\)'
)

# Liste pour stocker les résultats
commands = []

# Lire le fichier
with open(input_file, "r", encoding="utf-8") as f:
    content = f.read()
    matches = pattern.findall(content)
    for name, description in matches:
        commands.append([name, description])

# Écrire le CSV
with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "description"])
    writer.writerows(commands)

print(f"✅ {len(commands)} commandes extraites dans {output_file}")
