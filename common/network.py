import os
import socket
import configparser
import urllib.request
from enum import Enum

from larccommon.config_loader import find_cfg


class NetworkMode(Enum):
    INTRANET = 'intranet'
    INTERNET = 'internet'
    OFFLINE  = 'offline'


def detect_network() -> NetworkMode:
    """Retourne le mode réseau actuel (INTRANET > INTERNET > OFFLINE)."""
    cfg = configparser.ConfigParser()
    cfg.read(find_cfg())
    host = cfg.get('IntranetDatabase', 'Host', fallback='192.168.2.90')
    port = cfg.getint('IntranetDatabase', 'Port', fallback=5432)

    try:
        with socket.create_connection((host, port), timeout=1.5):
            return NetworkMode.INTRANET
    except OSError:
        pass

    try:
        urllib.request.urlopen('https://www.google.com', timeout=3)
        return NetworkMode.INTERNET
    except Exception:
        pass

    return NetworkMode.OFFLINE
