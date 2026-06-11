import smtplib
import ssl
import configparser
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional


def _load_smtp_config() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    paths = [
        os.path.join(here, '..', 'config.ini'),
        os.path.join(here, '..', '..', 'eLarcProf', 'config.ini'),
    ]
    cfg = configparser.ConfigParser()
    for p in paths:
        if os.path.exists(p):
            cfg.read(p)
            break
    if not cfg.has_section('SMTP'):
        return {}
    return dict(cfg['SMTP'])


def send_email(
    to_addrs: list[str],
    subject: str,
    body_html: str,
    from_addr: Optional[str] = None,
    smtp_config: Optional[dict] = None,
) -> tuple[bool, str]:
    """Envoie un email HTML via SMTP.

    Args:
        to_addrs: Liste des destinataires.
        subject: Objet du message.
        body_html: Corps HTML.
        from_addr: Expéditeur (par défaut celui du config).
        smtp_config: Dict avec Host, Port, User, Pass, FromName (optionnel).

    Returns:
        (succès, message d'erreur ou 'OK')
    """
    cfg = smtp_config or _load_smtp_config()
    if not cfg.get('Host') or not cfg.get('User') or not cfg.get('Pass'):
        return False, "SMTP non configuré dans config.ini"

    host = cfg['Host']
    port = int(cfg.get('Port', 587))
    user = cfg['User']
    password = cfg['Pass']
    from_name = cfg.get('FromName', '')
    from_addr = from_addr or user

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg['To'] = ', '.join(to_addrs)
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(user, password)
            server.sendmail(from_addr, to_addrs, msg.as_string())
        return True, "OK"
    except Exception as e:
        return False, str(e)
