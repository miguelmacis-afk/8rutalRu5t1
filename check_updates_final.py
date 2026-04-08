import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from packaging import version
import os
import re
import time
import random

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

session = requests.Session()
retry_strategy = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

def generate_umod_slug(name):
    """Convierte TruePVE -> true-pve, ZonePVxInfo -> zone-pvx-info"""
    manual = {"MagicCh47Panel": "magic-ch47-panel", "ZonePVxInfo": "zone-pvx-info", "PlayerDLCAPI": "player-dlc-api"}
    if name in manual: return manual[name]
    
    slug = re.sub(r'([a-z])([A-Z])', r'\1-\2', name)
    slug = re.sub(r'([A-Z])([A-Z][a-z])', r'\1-\2', slug)
    return slug.replace("_", "-").replace(" ", "-").replace("--", "-").lower().strip("-")

def super_clean(text):
    if not text: return ""
    text = text.lower().split('.')[0]
    text = re.sub(r'[-_ ]v?\d+([\.\d+]+)?', '', text)
    return text.replace("_", "").replace("-", "").replace(" ", "").replace("v", "")

def run_checker():
    if not os.path.exists("plugins_list.json"):
        print("❌ Error: plugins_list.json no existe.")
        return

    with open("plugins_list.json") as f:
        plugins = json.load(f)

    print("📡 Descargando base de datos completa de Codefling...")
    codefling_db = []
    try:
        r_cf = session.get("https://www.codefling.com/db?category=all", headers=HEADERS, timeout=25)
        if r_cf.status_code == 200:
            codefling_db = r_cf.json()
            print(f"✅ Se han cargado {len(codefling_db)} recursos de Codefling.")
    except Exception as e:
        print(f"⚠️ Error al conectar con Codefling: {e}")

    updates = []
    updatesNotFound = []
    versions_output = {}

    for plugin in plugins:
        name = plugin["Name"]
        local_ver = str(plugin["Version"])
        local_author = plugin.get("Author", "")

        if name == "UltimateCasesConverter" :
            continue
        
        local_author = local_author.lower().strip()
        latest_ver = None
        download_link = None
        source_found = "Ninguna"

        print(f"🔍 Buscando: {name} (v{local_ver})")
        target_name = super_clean(name)

        if name != "RaidableBases":
            for item in codefling_db:
                cf_file = super_clean(item.get("fileName", ""))
                cf_title = super_clean(item.get("name", ""))
                if target_name == cf_file or target_name == cf_title:
                    latest_ver = item.get("version")
                    download_link = f"https://codefling.com/files/file/{item.get('id')}-a/"
                    source_found = "Codefling"
                    break

        if not latest_ver:
            umod_slug = generate_umod_slug(name)
            wait = random.uniform(4, 9)
            print(f"   ⏳ Esperando {wait:.2f}s para uMod...")
            time.sleep(wait)
            
            try:
                r_umod = session.get(f"https://umod.org/plugins/{umod_slug}.json", headers=HEADERS, timeout=10)
                if r_umod.status_code == 200:
                    data = r_umod.json()
                    latest_ver = data.get("latest_release_version")
                    download_link = f"https://umod.org/plugins/{umod_slug}"
                    source_found = "uMod"
            except: pass

        if latest_ver:
            versions_output[name] = {"local": local_ver, "latest": latest_ver, "source": source_found}
            try:
                v_loc = version.parse(re.sub(r'[^\d.]', '', local_ver))
                v_rem = version.parse(re.sub(r'[^\d.]', '', latest_ver))
                
                if v_rem > v_loc:
                    print(f"   ✨ ¡NUEVA! v{local_ver} -> v{latest_ver} ({source_found})")
                    updates.append(f"📦 **{name}**\n🔹 `v{local_ver}` ➜ ✨ `v{latest_ver}`\n🔗 [Descargar]({download_link})")
                else:
                    print(f"   ✅ Al día")
            except: print(f"   ⚠️ Error de formato en versión")
        else:
            print(f"   ❌ No encontrado")
            updatesNotFound.append(f"❓ **{name}** (v{local_ver})")
            versions_output[name] = {"local": local_ver, "latest": "❌", "source": "Ninguna"}
        
        print("-" * 30)

    if DISCORD_WEBHOOK:
        if updates:
            for i in range(0, len(updates), 5):
                session.post(DISCORD_WEBHOOK, json={"embeds": [{"title": "🚀 Actualizaciones", "description": "\n\n".join(updates[i:i+5]), "color": 3066993}]})
        
        clean_not_found = updatesNotFound[:]
        if clean_not_found:
            for i in range(0, len(clean_not_found), 10):
                session.post(DISCORD_WEBHOOK, json={"embeds": [{"title": "🔍 No localizados", "description": "\n".join(clean_not_found[i:i+10]), "color": 15158332}]})

    with open("versions.json", "w") as f:
        json.dump(versions_output, f, indent=2)
    print("✅ Finalizado.")

if __name__ == "__main__":
    run_checker()
