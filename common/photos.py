import os
import urllib.request
from .session import session, ConnMode
from .app_config import app_config
from .logger import log

_SUPABASE_REF = "crvyxfsuvwqxzlhsfbwq"
_STORAGE_URL = f"https://{_SUPABASE_REF}.supabase.co/storage/v1/object/public/student-photos"


def _intranet_path(sid: int) -> str:
    return os.path.join(app_config.get("photos_dir"), f"{sid}.png")


def _cache_path(sid: int) -> str:
    return os.path.join(app_config.get("photos_cache_dir"), f"{sid}.png")


def get_photo_path(sid: int) -> str:
    """Renvoie un chemin valide vers la photo de l'élève.

    - Intranet : chemin local direct (dossier partagé LarcSuperviseur)
    - Cloud    : télécharge depuis Supabase Storage dans le cache local
    """
    if session.conn_mode == ConnMode.INTRANET:
        return _intranet_path(sid)

    cache = _cache_path(sid)
    if os.path.isfile(cache):
        return cache

    try:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        url = f"{_STORAGE_URL}/{sid}.png"
        urllib.request.urlretrieve(url, cache)
        log(f"Photos: telecharge {sid}.png depuis le cloud")
    except Exception as e:
        log(f"Photos: echec telechargement {sid}.png ({e})")
        return _intranet_path(sid)

    return cache
