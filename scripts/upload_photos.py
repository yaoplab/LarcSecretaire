"""Upload photos étudiantes vers Supabase Storage.

Usage :
  1. Récupérer la clé service_role depuis :
     Supabase Dashboard → Project Settings → API → service_role key
  2. Lancer :
     python scripts/upload_photos.py
"""

import os
import sys
import requests

_SUPABASE_REF = "crvyxfsuvwqxzlhsfbwq"
_BUCKET = "student-photos"
_PHOTOS_DIR = r"C:\Projets\LarcSuperviseur\photos"

# Clé service_role (à remplir)
SERVICE_ROLE_KEY = ""

_API = f"https://{_SUPABASE_REF}.supabase.co/storage/v1"


def upload_file(path: str) -> bool:
    sid = os.path.splitext(os.path.basename(path))[0]
    url = f"{_API}/object/{_BUCKET}/{sid}.png"
    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "image/png",
    }
    with open(path, "rb") as f:
        resp = requests.put(url, data=f, headers=headers)
    if resp.status_code in (200, 201):
        print(f"  OK  {sid}.png")
        return True
    print(f"  ERR {sid}.png ({resp.status_code}): {resp.text[:80]}")
    return False


def main():
    if not SERVICE_ROLE_KEY:
        print("Erreur : SERVICE_ROLE_KEY vide. Mets la cle dans le script.")
        sys.exit(1)

    files = sorted(
        f for f in os.listdir(_PHOTOS_DIR)
        if f.lower().endswith(".png")
    )
    print(f"Upload de {len(files)} photos vers {_BUCKET}...")
    ok = err = 0
    for fname in files:
        if upload_file(os.path.join(_PHOTOS_DIR, fname)):
            ok += 1
        else:
            err += 1
    print(f"Termine : {ok} OK, {err} erreurs")


if __name__ == "__main__":
    main()
