#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_detector.py  –  NetGuard · Motor de IA Local Completo
- Deteccion de anomalias de trafico (Isolation Forest) con persistencia
- Analizador de vulnerabilidades con explicaciones para cualquier usuario
- Chatbot local con base de conocimiento de ciberseguridad
- Entrenamiento persistente con documentos PDF/TXT/DOCX
- Deteccion de idioma automatica del sistema
- Sin dependencias de internet
"""

import os
import re
import json
import pickle
import hashlib
import locale
import platform
import numpy as np
from datetime import datetime
from pathlib import Path

# sklearn
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

# PDF - múltiples backends, el primero que funcione gana
PDF_BACKEND = None
try:
    import pdfplumber
    PDF_BACKEND = "pdfplumber"
except ImportError:
    pass

if not PDF_BACKEND:
    try:
        import fitz  # PyMuPDF
        PDF_BACKEND = "fitz"
    except ImportError:
        pass

if not PDF_BACKEND:
    try:
        import pypdf as _pypdf
        PDF_BACKEND = "pypdf"
    except ImportError:
        pass

if not PDF_BACKEND:
    try:
        import PyPDF2 as _pypdf
        PDF_BACKEND = "pypdf"
    except ImportError:
        pass

PDF_OK = PDF_BACKEND is not None

# DOCX
try:
    import docx
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

# =============================================================
# RUTAS DE PERSISTENCIA
# =============================================================

_BASE_DIR   = Path(__file__).parent
MODELS_DIR  = _BASE_DIR / "netguard_data" / "models"
DOCS_DIR    = _BASE_DIR / "netguard_data" / "documents"
TRAFFIC_MDL = MODELS_DIR / "traffic_anomaly.pkl"
DOC_INDEX   = MODELS_DIR / "doc_index.pkl"

for _d in (MODELS_DIR, DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# =============================================================
# DETECCION DE IDIOMA DEL SISTEMA
# =============================================================

def detect_system_language() -> str:
    try:
        lang = (os.environ.get("LANG", "") or
                os.environ.get("LANGUAGE", "") or
                os.environ.get("LC_ALL", ""))
        if not lang:
            lang = locale.getdefaultlocale()[0] or ""
        if not lang and platform.system() == "Windows":
            try:
                import ctypes
                lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
                lcid_map = {0x0C0A: "es", 0x0409: "en", 0x040C: "fr",
                            0x0416: "pt", 0x0407: "de"}
                return lcid_map.get(lang_id, "es")
            except Exception:
                pass
        code = lang[:2].lower()
        return code if code in ("es", "en", "fr", "pt", "de") else "es"
    except Exception:
        return "es"


SYSTEM_LANG = detect_system_language()


def t(key: str, lang: str = None) -> str:
    """Retorna texto en el idioma del sistema."""
    L = lang or SYSTEM_LANG
    return TEXTS.get(L, TEXTS["es"]).get(key, TEXTS["es"].get(key, key))


TEXTS = {
    "es": {
        "model_loaded":   "Modelo cargado de sesion anterior",
        "no_scan":        "No hay resultados de escaneo aun. Ejecuta un escaneo primero.",
        "no_trained":     "Modelo sin entrenar. Ve a la pestana Entrenamiento IA.",
        "doc_empty":      "El documento esta vacio o tiene muy poco contenido.",
        "doc_duplicate":  "Este documento ya fue agregado anteriormente.",
        "doc_invalid":    "El documento no parece relacionado con redes o seguridad",
        "doc_valid":      "Documento valido",
        "doc_added":      "Documento agregado correctamente",
        "upload":         "Subida",
        "download":       "Bajada",
        "total_traffic":  "Total",
        "risk_low":       "NORMAL — Tu red esta funcionando con trafico habitual",
        "risk_med":       "ATENCION — El trafico es mas alto de lo usual",
        "risk_high":      "ALERTA — Trafico muy alto, verifica que no haya actividad sospechosa",
        "anomaly":        "ANOMALIA DETECTADA",
        "normal":         "Trafico normal",
        "trained_ok":     "Modelo entrenado y guardado correctamente",
        "trained_fail":   "Error al entrenar el modelo",
        "docs_loaded":    "documento(s) cargado(s) de sesion anterior",
    },
    "en": {
        "model_loaded":   "Model loaded from previous session",
        "no_scan":        "No scan results yet. Run a scan first.",
        "no_trained":     "Model not trained. Go to AI Training tab.",
        "doc_empty":      "Document is empty or has very little content.",
        "doc_duplicate":  "This document was already added previously.",
        "doc_invalid":    "Document doesn't seem related to networks or security",
        "doc_valid":      "Valid document",
        "doc_added":      "Document added successfully",
        "upload":         "Upload",
        "download":       "Download",
        "total_traffic":  "Total",
        "risk_low":       "NORMAL — Your network is running with normal traffic",
        "risk_med":       "ATTENTION — Traffic is higher than usual",
        "risk_high":      "ALERT — Very high traffic, check for suspicious activity",
        "anomaly":        "ANOMALY DETECTED",
        "normal":         "Normal traffic",
        "trained_ok":     "Model trained and saved successfully",
        "trained_fail":   "Error training the model",
        "docs_loaded":    "document(s) loaded from previous session",
    },
}


# =============================================================
# BASE DE CONOCIMIENTO PRE-ENTRENADA
# =============================================================

PORT_EXPLANATIONS = {
    21: {
        "service": "FTP (Transferencia de Archivos)",
        "plain_risk": {
            "es": "Es como tener una caja fuerte con la llave puesta por fuera. Cualquiera en la red puede ver tus archivos y contrasenas sin ningun esfuerzo.",
            "en": "Like having a safe with the key left outside. Anyone on the network can see your files and passwords effortlessly."
        },
        "action": {
            "es": "Desactiva FTP. Usa SFTP (mismo puerto 22 que SSH) para transferir archivos de forma segura.",
            "en": "Disable FTP. Use SFTP (same port 22 as SSH) to transfer files securely."
        },
        "risk": "ALTO", "score": 7
    },
    22: {
        "service": "SSH (Acceso Remoto Seguro)",
        "plain_risk": {
            "es": "Es una puerta de acceso remoto cifrada. Es segura, pero los atacantes la golpean constantemente intentando adivinar contrasenas.",
            "en": "It's an encrypted remote access door. It's secure, but attackers constantly try to guess passwords."
        },
        "action": {
            "es": "Configura SSH para que solo acepte llaves digitales (no contrasenas). Instala fail2ban para bloquear intentos repetidos.",
            "en": "Configure SSH to only accept digital keys (not passwords). Install fail2ban to block repeated attempts."
        },
        "risk": "MEDIO", "score": 3
    },
    23: {
        "service": "Telnet (Acceso Remoto INSEGURO)",
        "plain_risk": {
            "es": "Todo lo que escribes — contrasenas, comandos, datos — viaja en texto abierto por la red. Es como gritar tus contrasenas en publico.",
            "en": "Everything you type — passwords, commands, data — travels as open text on the network. Like shouting your passwords in public."
        },
        "action": {
            "es": "DESACTIVALO HOY. No existe ninguna razon valida para mantener Telnet activo. Usa SSH.",
            "en": "DISABLE IT TODAY. There is no valid reason to keep Telnet active. Use SSH."
        },
        "risk": "CRITICO", "score": 10
    },
    80: {
        "service": "HTTP (Sitio Web sin Seguridad)",
        "plain_risk": {
            "es": "Tu sitio web no tiene candado. Todo lo que los usuarios escriben — formularios, contrasenas, datos personales — puede ser interceptado.",
            "en": "Your website has no padlock. Everything users type — forms, passwords, personal data — can be intercepted."
        },
        "action": {
            "es": "Instala un certificado SSL gratuito (Let's Encrypt) para activar HTTPS.",
            "en": "Install a free SSL certificate (Let's Encrypt) to enable HTTPS."
        },
        "risk": "MEDIO", "score": 4
    },
    443: {
        "service": "HTTPS (Sitio Web Seguro)",
        "plain_risk": {
            "es": "Tu sitio web tiene el candado de seguridad. Las comunicaciones estan cifradas. Esto es lo correcto.",
            "en": "Your website has the security padlock. Communications are encrypted. This is correct."
        },
        "action": {
            "es": "Verifica que el certificado no este caducado.",
            "en": "Verify that the certificate is not expired."
        },
        "risk": "BAJO", "score": 1
    },
    445: {
        "service": "SMB (Comparticion de Archivos Windows)",
        "plain_risk": {
            "es": "Este es el puerto que uso el virus WannaCry en 2017 para infectar 200.000 computadoras en 150 paises en horas, cifrando todos los archivos y pidiendo rescate en Bitcoin. Si este puerto esta expuesto a internet, tu red es un objetivo inmediato de ransomware.",
            "en": "This is the port used by WannaCry in 2017 to infect 200,000 computers in 150 countries in hours, encrypting all files and demanding Bitcoin ransom. If exposed to the internet, your network is an immediate ransomware target."
        },
        "action": {
            "es": "URGENTE: Bloquea el puerto 445 en el firewall AHORA. Para compartir archivos en red local, asegurate de que no sea accesible desde internet.",
            "en": "URGENT: Block port 445 in the firewall NOW. For local file sharing, make sure it's not accessible from the internet."
        },
        "risk": "CRITICO", "score": 10
    },
    3306: {
        "service": "MySQL (Base de Datos)",
        "plain_risk": {
            "es": "Tu base de datos esta expuesta a la red. Es como dejar el archivo con todos los datos de tus clientes en la vitrina de la tienda. Cualquiera puede intentar robarlos.",
            "en": "Your database is exposed to the network. Like leaving the file with all your customer data in the store window. Anyone can try to steal it."
        },
        "action": {
            "es": "Configura MySQL para que solo sea accesible desde el mismo servidor: agrega 'bind-address = 127.0.0.1' en el archivo de configuracion.",
            "en": "Configure MySQL to only be accessible from the same server: add 'bind-address = 127.0.0.1' to the configuration file."
        },
        "risk": "ALTO", "score": 8
    },
    3389: {
        "service": "RDP (Escritorio Remoto Windows)",
        "plain_risk": {
            "es": "Es como tener la puerta principal de tu computadora abierta a internet. Los hackers tienen robots que intentan entrar probando millones de contrasenas por hora. Si logran entrar, tienen control total y pueden instalar ransomware, robar datos o espiar todo lo que haces.",
            "en": "Like having the front door of your computer open to the internet. Hackers have bots trying millions of passwords per hour. If they get in, they have full control and can install ransomware, steal data, or spy on everything you do."
        },
        "action": {
            "es": "URGENTE: Bloquea el puerto 3389 en el firewall. Para acceso remoto, usa una VPN primero y luego conecta por RDP dentro de la VPN.",
            "en": "URGENT: Block port 3389 in the firewall. For remote access, use a VPN first, then connect via RDP inside the VPN."
        },
        "risk": "CRITICO", "score": 10
    },
    5432: {
        "service": "PostgreSQL (Base de Datos)",
        "plain_risk": {
            "es": "Tu base de datos PostgreSQL esta expuesta a la red. Los datos de tus usuarios y aplicaciones estan en riesgo.",
            "en": "Your PostgreSQL database is exposed to the network. Your users' and application data is at risk."
        },
        "action": {
            "es": "Configura PostgreSQL para escuchar solo en localhost: listen_addresses = 'localhost' en postgresql.conf.",
            "en": "Configure PostgreSQL to listen only on localhost: listen_addresses = 'localhost' in postgresql.conf."
        },
        "risk": "ALTO", "score": 7
    },
    5900: {
        "service": "VNC (Control Remoto de Pantalla)",
        "plain_risk": {
            "es": "Permite ver y controlar tu pantalla remotamente. Muchas instalaciones tienen contrasenas debiles o no tienen contrasena. Un atacante puede ver y controlar todo tu equipo.",
            "en": "Allows viewing and controlling your screen remotely. Many installations have weak or no passwords. An attacker can see and control everything on your machine."
        },
        "action": {
            "es": "Desactiva VNC si no lo usas. Si lo necesitas, usalo solo a traves de un tunel VPN.",
            "en": "Disable VNC if you don't use it. If needed, use it only through a VPN tunnel."
        },
        "risk": "CRITICO", "score": 9
    },
    6379: {
        "service": "Redis (Base de Datos en Memoria)",
        "plain_risk": {
            "es": "Redis expuesto es uno de los fallos mas graves. Un atacante puede conectarse sin contrasena y crear una llave maestra para entrar a tu servidor como administrador sin necesitar tu contrasena.",
            "en": "Exposed Redis is one of the most serious flaws. An attacker can connect without a password and create a master key to enter your server as administrator."
        },
        "action": {
            "es": "CRITICO: Agrega 'bind 127.0.0.1' y 'requirepass TuContrasena' en redis.conf. Haz esto ahora.",
            "en": "CRITICAL: Add 'bind 127.0.0.1' and 'requirepass YourPassword' in redis.conf. Do this now."
        },
        "risk": "CRITICO", "score": 10
    },
    27017: {
        "service": "MongoDB (Base de Datos NoSQL)",
        "plain_risk": {
            "es": "Miles de bases de datos MongoDB han sido robadas porque estaban sin contrasena. Tus datos pueden estar disponibles para cualquiera que sepa como buscarlos.",
            "en": "Thousands of MongoDB databases have been stolen because they had no password. Your data may be available to anyone who knows how to find them."
        },
        "action": {
            "es": "Configura MongoDB con autenticacion y solo en localhost: bindIp: 127.0.0.1 en mongod.conf.",
            "en": "Configure MongoDB with authentication and localhost only: bindIp: 127.0.0.1 in mongod.conf."
        },
        "risk": "CRITICO", "score": 10
    },
    9200: {
        "service": "Elasticsearch (Motor de Busqueda)",
        "plain_risk": {
            "es": "Elasticsearch sin autenticacion expone TODOS los datos indexados sin necesidad de contrasena. Hay robots que buscan estos puertos en internet continuamente.",
            "en": "Elasticsearch without authentication exposes ALL indexed data without a password. There are bots that continuously scan the internet for these ports."
        },
        "action": {
            "es": "Habilita seguridad en Elasticsearch o bloquea el puerto con firewall urgentemente.",
            "en": "Enable Elasticsearch security or block the port with firewall urgently."
        },
        "risk": "CRITICO", "score": 10
    },
    1433: {
        "service": "SQL Server (Microsoft)",
        "plain_risk": {
            "es": "Base de datos SQL Server de Microsoft expuesta. Objetivo frecuente de ataques automatizados.",
            "en": "Microsoft SQL Server database exposed. Frequent target of automated attacks."
        },
        "action": {
            "es": "No exponer a internet. Usar firewall para restringir acceso.",
            "en": "Do not expose to internet. Use firewall to restrict access."
        },
        "risk": "ALTO", "score": 8
    },
}

DANGEROUS_COMBOS = [
    {
        "ports": {445, 3389},
        "severity": "CRITICO",
        "name": "Combinacion de Ransomware",
        "plain": {
            "es": "Tienes abiertas las DOS puertas que usan los virus ransomware mas destructivos (WannaCry, Ryuk, Conti). Esta combinacion es la forma numero uno en que las empresas pierden todos sus datos y terminan pagando miles de dolares de rescate.",
            "en": "You have open the TWO doors used by the most destructive ransomware (WannaCry, Ryuk, Conti). This is the #1 way companies lose all their data and end up paying thousands in ransom."
        },
        "action": {
            "es": "Bloquea los puertos 445 y 3389 en tu firewall HOY. Para acceso remoto usa VPN.",
            "en": "Block ports 445 and 3389 in your firewall TODAY. For remote access use VPN."
        }
    },
    {
        "ports": {3306, 80},
        "severity": "ALTO",
        "name": "Servidor Web con Base de Datos Expuesta",
        "plain": {
            "es": "Tienes un sitio web Y la base de datos accesible directamente. Un atacante que encuentre una falla en tu web puede robar todos tus datos de clientes directamente.",
            "en": "You have a website AND the database directly accessible. An attacker who finds a flaw in your site can directly steal all your customer data."
        },
        "action": {
            "es": "Configura la base de datos para que solo sea accesible desde el servidor web, no desde internet.",
            "en": "Configure the database to only be accessible from the web server, not from the internet."
        }
    },
    {
        "ports": {23, 22},
        "severity": "CRITICO",
        "name": "Telnet activo con SSH",
        "plain": {
            "es": "Tienes Telnet (completamente inseguro) activo junto con SSH (seguro). Un atacante puede espiar todo lo que escribes por Telnet aunque creas que estas usando SSH.",
            "en": "You have Telnet (completely insecure) active alongside SSH (secure). An attacker can spy on everything you type via Telnet even if you think you're using SSH."
        },
        "action": {
            "es": "Desactiva Telnet inmediatamente. SSH es mas que suficiente y es seguro.",
            "en": "Disable Telnet immediately. SSH is more than enough and is secure."
        }
    },
    {
        "ports": {6379, 22},
        "severity": "CRITICO",
        "name": "Redis puede dar acceso root al servidor",
        "plain": {
            "es": "Con Redis expuesto, un atacante puede crear su propia llave SSH y entrar a tu servidor con permisos de administrador sin necesitar tu contrasena.",
            "en": "With Redis exposed, an attacker can create their own SSH key and enter your server with administrator permissions without needing your password."
        },
        "action": {
            "es": "Cierra Redis a internet inmediatamente (bind 127.0.0.1 en redis.conf).",
            "en": "Close Redis to the internet immediately (bind 127.0.0.1 in redis.conf)."
        }
    },
    {
        "ports": {5900, 3389},
        "severity": "CRITICO",
        "name": "Doble Acceso Remoto Expuesto",
        "plain": {
            "es": "Tienes DOS formas de controlar tu computadora remotamente expuestas a internet. Esto duplica las posibilidades de que alguien tome control de tu sistema.",
            "en": "You have TWO ways to remotely control your computer exposed to the internet. This doubles the chances of someone taking control of your system."
        },
        "action": {
            "es": "Desactiva uno de los dos. El que mantengas, protegelo con VPN.",
            "en": "Disable one of the two. Whichever you keep, protect it with a VPN."
        }
    },
]

QA_KNOWLEDGE = [
    {
        "kw_es": ["smb", "445", "wannacry", "ransomware", "compartir archivos"],
        "kw_en": ["smb", "445", "wannacry", "ransomware", "file sharing"],
        "answer": {
            "es": (
                "SMB / Puerto 445 - Riesgo Maximo\n\n"
                "Que es? SMB es el sistema que usa Windows para compartir carpetas y archivos entre computadoras.\n\n"
                "Por que es tan peligroso? En mayo de 2017, el virus WannaCry uso una falla en SMB para infectar "
                "mas de 200.000 computadoras en 150 paises en solo 4 dias. Hospitales, bancos y empresas perdieron "
                "todos sus datos. El dano total supero los 4.000 millones de dolares.\n\n"
                "Que debo hacer?\n"
                "1. Bloquear el puerto 445 en el firewall\n"
                "2. Mantener Windows actualizado (instala los parches de seguridad)\n"
                "3. Si compartes carpetas en red local, asegurate de que no sean accesibles desde internet\n"
                "4. Haz copias de seguridad regularmente en un disco desconectado de la red"
            ),
            "en": (
                "SMB / Port 445 - Maximum Risk\n\n"
                "What is it? SMB is the system Windows uses to share folders and files between computers.\n\n"
                "Why is it so dangerous? In May 2017, WannaCry used an SMB vulnerability to infect "
                "over 200,000 computers in 150 countries in just 4 days. Hospitals, banks and companies lost "
                "all their data. Total damage exceeded $4 billion.\n\n"
                "What should I do?\n"
                "1. Block port 445 in the firewall\n"
                "2. Keep Windows updated (install security patches)\n"
                "3. If sharing folders on local network, make sure they're not accessible from the internet\n"
                "4. Make regular backups on a drive disconnected from the network"
            )
        }
    },
    {
        "kw_es": ["rdp", "3389", "escritorio remoto", "acceso remoto windows"],
        "kw_en": ["rdp", "3389", "remote desktop", "windows remote access"],
        "answer": {
            "es": (
                "RDP / Puerto 3389 - Puerta Abierta para Hackers\n\n"
                "Que es? El Escritorio Remoto de Windows permite controlar tu PC desde otro lugar.\n\n"
                "Por que es peligroso? Los hackers tienen robots que escanean todo internet buscando este puerto. "
                "Cuando lo encuentran, prueban miles de contrasenas automaticamente. Si entran, tienen control "
                "total: pueden robar datos, instalar virus o cifrar todos tus archivos y pedir rescate.\n\n"
                "Que debo hacer?\n"
                "1. Bloquear el puerto 3389 en el firewall\n"
                "2. Si necesitas acceso remoto: instala una VPN y conectate por RDP solo dentro de la VPN\n"
                "3. Activa autenticacion en dos pasos\n"
                "4. Usa contrasenas largas y complejas"
            ),
            "en": (
                "RDP / Port 3389 - Open Door for Hackers\n\n"
                "What is it? Windows Remote Desktop lets you control your PC from another location.\n\n"
                "Why is it dangerous? Hackers have bots that scan the entire internet for this port. "
                "When found, they automatically try thousands of passwords. If they get in, they have "
                "full control: they can steal data, install viruses, or encrypt all your files and demand ransom.\n\n"
                "What should I do?\n"
                "1. Block port 3389 in the firewall\n"
                "2. If you need remote access: install a VPN and connect via RDP only inside the VPN\n"
                "3. Enable two-factor authentication\n"
                "4. Use long, complex passwords"
            )
        }
    },
    {
        "kw_es": ["firewall", "cortafuegos", "bloquear puerto", "proteger red"],
        "kw_en": ["firewall", "block port", "protect network"],
        "answer": {
            "es": (
                "Como Proteger tu Red con Firewall\n\n"
                "Que es un firewall? Es el guardia de seguridad de tu red. Decide que conexiones se permiten "
                "y cuales se bloquean.\n\n"
                "Reglas basicas:\n"
                "1. Bloquear todo el trafico que no sea necesario\n"
                "2. Solo abrir los puertos que realmente uses\n"
                "3. Nunca exponer bases de datos a internet\n"
                "4. Para acceso remoto, usar VPN en vez de exponer RDP directamente\n\n"
                "Comandos en Linux (UFW):\n"
                "  ufw default deny incoming\n"
                "  ufw allow 80\n"
                "  ufw allow 443\n"
                "  ufw deny 445\n"
                "  ufw deny 3389\n"
                "  ufw enable"
            ),
            "en": (
                "How to Protect Your Network with Firewall\n\n"
                "What is a firewall? It's the security guard of your network. It decides which connections "
                "are allowed and which are blocked.\n\n"
                "Basic rules:\n"
                "1. Block all traffic that isn't necessary\n"
                "2. Only open ports you actually use\n"
                "3. Never expose databases to the internet\n"
                "4. For remote access, use VPN instead of exposing RDP directly\n\n"
                "Linux commands (UFW):\n"
                "  ufw default deny incoming\n"
                "  ufw allow 80\n"
                "  ufw allow 443\n"
                "  ufw deny 445\n"
                "  ufw deny 3389\n"
                "  ufw enable"
            )
        }
    },
    {
        "kw_es": ["vpn", "tunel", "red privada", "acceso seguro remoto"],
        "kw_en": ["vpn", "tunnel", "private network", "secure remote"],
        "answer": {
            "es": (
                "VPN - Tunel Seguro para tu Red\n\n"
                "Que es? Una VPN crea un tunel cifrado entre tu dispositivo y tu red. "
                "Es como un tubo blindado a traves de internet.\n\n"
                "Para que sirve?\n"
                "- Acceder remotamente a tu red de forma segura (en vez de exponer RDP)\n"
                "- Cifrar el trafico en redes WiFi publicas\n"
                "- Conectar oficinas remotas de forma segura\n\n"
                "Opciones recomendadas (gratuitas y seguras):\n"
                "- WireGuard: mas moderno y facil de configurar\n"
                "- OpenVPN: probado y muy estable"
            ),
            "en": (
                "VPN - Secure Tunnel for Your Network\n\n"
                "What is it? A VPN creates an encrypted tunnel between your device and your network. "
                "Like an armored pipe through the internet.\n\n"
                "What is it for?\n"
                "- Securely remote access to your network (instead of exposing RDP)\n"
                "- Encrypt traffic on public WiFi networks\n"
                "- Securely connect remote offices\n\n"
                "Recommended options (free and secure):\n"
                "- WireGuard: more modern and easy to configure\n"
                "- OpenVPN: proven and very stable"
            )
        }
    },
    {
        "kw_es": ["anomalia", "trafico", "sospechoso", "subida alta", "bajada alta"],
        "kw_en": ["anomaly", "traffic", "suspicious", "high upload", "high download"],
        "answer": {
            "es": (
                "Trafico Anomalo - Que Significa?\n\n"
                "Subida alta inusual (Upload): Tu computadora esta enviando muchos datos.\n"
                "Puede significar: alguien robando tus archivos, un virus enviando informacion, "
                "o un programa desconocido.\n\n"
                "Bajada alta inusual (Download): Tu red esta recibiendo muchos datos.\n"
                "Puede ser: descarga no autorizada, ataque DDoS, o actualizaciones masivas.\n\n"
                "Que hacer?\n"
                "1. Ver que programa usa la red: en Windows, Administrador de tareas > Red\n"
                "2. En Linux: iftop o nethogs\n"
                "3. Si no identificas el origen, desconecta de internet y ejecuta un antivirus"
            ),
            "en": (
                "Anomalous Traffic - What Does It Mean?\n\n"
                "Unusual high upload: Your computer is sending a lot of data.\n"
                "Could mean: someone stealing your files, a virus sending information, "
                "or an unknown program.\n\n"
                "Unusual high download: Your network is receiving a lot of data.\n"
                "Could be: unauthorized download, DDoS attack, or mass updates.\n\n"
                "What to do?\n"
                "1. See which program is using the network: on Windows, Task Manager > Network\n"
                "2. On Linux: iftop or nethogs\n"
                "3. If you can't identify the source, disconnect from internet and run antivirus"
            )
        }
    },
    {
        "kw_es": ["backup", "copia de seguridad", "respaldo", "recuperar datos"],
        "kw_en": ["backup", "recovery", "restore data"],
        "answer": {
            "es": (
                "Copias de Seguridad - Tu Ultima Defensa\n\n"
                "Los backups son lo que te salva si te ataca un ransomware.\n\n"
                "Regla 3-2-1:\n"
                "- 3 copias de tus datos\n"
                "- En 2 medios distintos (disco duro + nube)\n"
                "- 1 copia en un lugar fisico diferente\n\n"
                "IMPORTANTE: Los backups deben estar DESCONECTADOS de la red principal. "
                "Si estan conectados, el ransomware tambien los cifrara."
            ),
            "en": (
                "Backups - Your Last Line of Defense\n\n"
                "Backups are what saves you if ransomware attacks.\n\n"
                "3-2-1 Rule:\n"
                "- 3 copies of your data\n"
                "- On 2 different media (hard drive + cloud)\n"
                "- 1 copy in a different physical location\n\n"
                "IMPORTANT: Backups must be DISCONNECTED from the main network. "
                "If connected, ransomware will encrypt them too."
            )
        }
    },
    {
        "kw_es": ["contrasena", "password", "clave", "autenticacion", "dos pasos"],
        "kw_en": ["password", "authentication", "two factor", "2fa", "credentials"],
        "answer": {
            "es": (
                "Contrasenas Seguras\n\n"
                "Reglas basicas:\n"
                "- Minimo 12 caracteres con mayusculas, numeros y simbolos\n"
                "- Contrasena diferente para cada servicio\n"
                "- Usa un gestor de contrasenas: Bitwarden (gratuito) o KeePass\n\n"
                "Para servidores:\n"
                "- SSH: usa llaves en vez de contrasenas\n"
                "- Instala fail2ban para bloquear fuerza bruta\n"
                "- Activa autenticacion en dos pasos siempre que sea posible"
            ),
            "en": (
                "Secure Passwords\n\n"
                "Basic rules:\n"
                "- Minimum 12 characters with uppercase, numbers and symbols\n"
                "- Different password for each service\n"
                "- Use a password manager: Bitwarden (free) or KeePass\n\n"
                "For servers:\n"
                "- SSH: use keys instead of passwords\n"
                "- Install fail2ban to block brute force\n"
                "- Enable two-factor authentication whenever possible"
            )
        }
    },
]

# Palabras clave para validar documentos
SECURITY_KEYWORDS = set([
    # === ESPAÑOL - Redes generales ===
    "red", "redes", "protocolo", "router", "switch", "hub", "servidor", "host",
    "dominio", "subred", "mascara", "gateway", "puerta", "enlace", "nodo",
    "topologia", "infraestructura", "interfaz", "adaptador", "cable", "fibra",
    "ethernet", "conector", "medio", "transmision", "latencia", "ancho",
    "banda", "throughput", "paquete", "trama", "segmento", "datagrama",
    "encapsulacion", "encaminamiento", "enrutamiento", "conmutacion",
    # === ESPAÑOL - Redes inalámbricas ===
    "inalambrica", "inalambrico", "wifi", "wireless", "wlan", "ssid", "bssid",
    "antena", "frecuencia", "canal", "cobertura", "punto", "acceso", "ap",
    "wpa", "wpa2", "wpa3", "wep", "psk", "eap", "radius", "autenticacion",
    "asociacion", "beacon", "espectro", "ghz", "mhz", "banda", "mimo",
    "ofdm", "802.11", "bluetooth", "zigbee", "celular", "lte", "5g", "4g",
    # === ESPAÑOL - Protocolos y capas ===
    "tcp", "udp", "ip", "ipv4", "ipv6", "icmp", "arp", "rarp", "dhcp",
    "dns", "http", "https", "ftp", "sftp", "smtp", "pop", "imap", "snmp",
    "ntp", "telnet", "ssh", "rdp", "sip", "voip", "ospf", "rip", "bgp",
    "eigrp", "vlan", "nat", "pat", "acl", "qos", "mpls", "ppp", "frame",
    # === ESPAÑOL - Seguridad ===
    "seguridad", "ciberseguridad", "firewall", "puerto", "vulnerabilidad",
    "ataque", "malware", "virus", "cifrado", "vpn", "proxy", "intrusion",
    "ids", "ips", "siem", "nmap", "escaneo", "pentesting", "hacker",
    "exploit", "phishing", "ransomware", "ddos", "botnet", "contrasena",
    "certificado", "ssl", "tls", "wan", "clave", "llave", "criptografia",
    "hash", "firma", "digital", "rsa", "aes", "ipsec", "pkc", "pki",
    "token", "biometria", "mfa", "2fa", "perimetro", "desmilitarizada",
    "dmz", "honeypot", "sandbox", "forensico", "incidente", "amenaza",
    "riesgo", "parche", "actualizacion", "politica", "cumplimiento",
    "auditoria", "log", "registro", "monitoreo", "disponibilidad",
    "integridad", "confidencialidad", "triada", "zero", "confianza",
    # === INGLÉS - General networking ===
    "network", "networking", "router", "switch", "gateway", "subnet", "mask",
    "topology", "infrastructure", "interface", "adapter", "cable", "fiber",
    "ethernet", "transmission", "latency", "bandwidth", "throughput",
    "packet", "frame", "segment", "datagram", "encapsulation", "routing",
    "switching", "node", "hub", "backbone", "link", "layer",
    # === INGLÉS - Wireless ===
    "wireless", "wifi", "wlan", "ssid", "antenna", "frequency", "channel",
    "coverage", "access point", "wpa", "wpa2", "wpa3", "wep", "beacon",
    "spectrum", "mimo", "ofdm", "bluetooth", "cellular", "mobile",
    # === INGLÉS - Protocols ===
    "tcp", "udp", "ipv4", "ipv6", "icmp", "arp", "dhcp", "dns", "http",
    "https", "ftp", "smtp", "ssh", "rdp", "ospf", "bgp", "rip", "vlan",
    "nat", "acl", "qos", "mpls", "snmp", "ntp", "sip", "voip",
    # === INGLÉS - Security ===
    "security", "cybersecurity", "firewall", "port", "vulnerability",
    "encryption", "scan", "authentication", "password", "credential",
    "breach", "threat", "defense", "intrusion", "detection", "prevention",
    "monitoring", "access", "control", "patch", "update", "exploit",
    "payload", "lateral", "privilege", "escalation", "exfiltration",
    "persistence", "reconnaissance", "malware", "ransomware", "phishing",
    "ddos", "botnet", "ssl", "tls", "vpn", "ipsec", "certificate",
    "cryptography", "hash", "digital", "signature", "rsa", "aes", "pki",
    "mfa", "honeypot", "sandbox", "forensic", "incident", "compliance",
    "audit", "log", "monitoring", "confidentiality", "integrity",
    "availability", "zero trust", "dmz", "siem", "ids", "ips",
])


# =============================================================
# DETECTOR DE ANOMALIAS (persistente)
# =============================================================

class AnomalyDetector:
    def __init__(self, contamination=0.08):
        self.contamination  = contamination
        self.is_trained     = False
        self.model          = None
        self.scaler         = None
        self.stats          = {}
        self._upload_mean   = 0
        self._download_mean = 0
        self._upload_std    = 1
        self._download_std  = 1
        self._load_model()

    def _save_model(self):
        try:
            with open(TRAFFIC_MDL, "wb") as f:
                pickle.dump({
                    "model": self.model, "scaler": self.scaler,
                    "stats": self.stats,
                    "upload_mean": self._upload_mean, "download_mean": self._download_mean,
                    "upload_std": self._upload_std, "download_std": self._download_std,
                }, f)
        except Exception as e:
            print(f"No se pudo guardar modelo: {e}")

    def _load_model(self):
        if not TRAFFIC_MDL.exists():
            return
        try:
            with open(TRAFFIC_MDL, "rb") as f:
                d = pickle.load(f)
            self.model          = d["model"];    self.scaler         = d["scaler"]
            self.stats          = d["stats"];    self._upload_mean   = d["upload_mean"]
            self._download_mean = d["download_mean"]
            self._upload_std    = d["upload_std"]
            self._download_std  = d["download_std"]
            self.is_trained     = True
            n = self.stats.get("samples", "?")
            print(f"Modelo de trafico cargado ({n} muestras)")
        except Exception as e:
            print(f"Error cargando modelo de trafico: {e}")

    def train(self, data) -> bool:
        if not SKLEARN_OK:
            return False
        try:
            if not data or len(data) < 10:
                return False
            X = np.array(data, dtype=float)
            if X.ndim == 1: X = X.reshape(-1, 1)
            if X.shape[1] < 2: return False

            self._upload_mean   = float(np.mean(X[:, 0]))
            self._download_mean = float(np.mean(X[:, 1]))
            self._upload_std    = float(np.std(X[:, 0]))  or 1.0
            self._download_std  = float(np.std(X[:, 1]))  or 1.0

            self.stats = {
                "samples":       len(data),
                "upload_mean":   round(self._upload_mean,   2),
                "upload_std":    round(self._upload_std,    2),
                "download_mean": round(self._download_mean, 2),
                "download_std":  round(self._download_std,  2),
                "upload_max":    round(float(np.max(X[:, 0])), 2),
                "download_max":  round(float(np.max(X[:, 1])), 2),
                "trained_at":    datetime.now().isoformat(),
            }
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            self.model = IsolationForest(
                contamination=self.contamination,
                n_estimators=150, random_state=42, n_jobs=-1
            )
            self.model.fit(X_scaled)
            self.is_trained = True
            self._save_model()
            return True
        except Exception as e:
            print(f"Error entrenando: {e}")
            return False

    def predict(self, upload_kb: float, download_kb: float) -> dict:
        lang    = SYSTEM_LANG if SYSTEM_LANG in ("es", "en") else "es"
        reasons = []
        severity = "NORMAL"

        if upload_kb > 8000:
            msg = {"es": f"Subida extrema ({upload_kb:.0f} KB/s): posible robo de archivos",
                   "en": f"Extreme upload ({upload_kb:.0f} KB/s): possible file theft"}
            reasons.append(msg[lang]); severity = "CRITICO"
        elif upload_kb > 3000:
            msg = {"es": f"Subida muy alta ({upload_kb:.0f} KB/s): verifica que programa envia datos",
                   "en": f"Very high upload ({upload_kb:.0f} KB/s): check which program sends data"}
            reasons.append(msg[lang]); severity = "ALTO"

        if download_kb > 15000:
            msg = {"es": f"Bajada extrema ({download_kb:.0f} KB/s): posible ataque DDoS",
                   "en": f"Extreme download ({download_kb:.0f} KB/s): possible DDoS attack"}
            reasons.append(msg[lang]); severity = "CRITICO"

        if self.is_trained and self.model and self.scaler:
            try:
                sample = np.array([[upload_kb, download_kb]], dtype=float)
                scaled = self.scaler.transform(sample)
                if self.model.predict(scaled)[0] == -1:
                    up_dev = abs(upload_kb   - self._upload_mean)   / (self._upload_std   or 1)
                    dl_dev = abs(download_kb - self._download_mean) / (self._download_std or 1)
                    if up_dev > dl_dev:
                        msg = {"es": f"La subida es {up_dev:.1f}x mayor de lo normal para esta red",
                               "en": f"Upload is {up_dev:.1f}x higher than normal for this network"}
                    else:
                        msg = {"es": f"La bajada es {dl_dev:.1f}x mayor de lo normal para esta red",
                               "en": f"Download is {dl_dev:.1f}x higher than normal for this network"}
                    reasons.append(msg[lang])
                    if severity == "NORMAL": severity = "MEDIO"
            except Exception:
                pass

        return {
            "label":    "ANOMALIA" if reasons else "NORMAL",
            "severity": severity if reasons else "NORMAL",
            "reasons":  reasons,
        }

    def get_stats(self) -> dict:
        return self.stats


# =============================================================
# ANALIZADOR DE VULNERABILIDADES
# =============================================================

class VulnerabilityAnalyzer:
    def analyze(self, scan_results: list) -> dict:
        lang = SYSTEM_LANG if SYSTEM_LANG in ("es", "en") else "es"
        report = {
            "summary": {}, "devices": [],
            "critical_findings": [], "dangerous_combos": [],
            "action_plan": [], "overall_risk": "BAJO", "lang": lang,
        }
        total_ports = total_critical = total_high = 0
        all_scores = []

        for device in scan_results:
            ip       = device.get("ip", "?")
            hostname = device.get("hostname", "Desconocido")
            ports    = set(device.get("ports", []))
            score    = device.get("score", 0)
            all_scores.append(score)

            dev = {"ip": ip, "hostname": hostname, "findings": [],
                   "combos": [], "risk_score": score}

            for classified in device.get("classified", []):
                total_ports += 1
                port = classified.get("port", 0)
                risk = classified.get("risk", "MEDIO")
                kb   = PORT_EXPLANATIONS.get(port, {})

                enriched = dict(classified)
                enriched["plain_risk"]    = kb.get("plain_risk", {}).get(lang, classified.get("recommendation", ""))
                enriched["plain_action"]  = kb.get("action", {}).get(lang, "")
                enriched["service_name"]  = kb.get("service", classified.get("service", f"Puerto {port}"))
                dev["findings"].append(enriched)

                if risk == "CRITICO":
                    total_critical += 1
                    report["critical_findings"].append({
                        "ip": ip, "port": port,
                        "service":      enriched["service_name"],
                        "plain_risk":   enriched["plain_risk"],
                        "plain_action": enriched["plain_action"],
                    })
                elif risk == "ALTO":
                    total_high += 1

            for combo in DANGEROUS_COMBOS:
                if combo["ports"].issubset(ports):
                    c = {
                        "ip": ip, "ports": sorted(combo["ports"]),
                        "severity": combo["severity"], "name": combo["name"],
                        "plain":  combo["plain"].get(lang, combo["plain"]["es"]),
                        "action": combo["action"].get(lang, combo["action"]["es"]),
                    }
                    dev["combos"].append(c)
                    report["dangerous_combos"].append(c)

            report["devices"].append(dev)

        report["summary"] = {
            "total_devices":    len(scan_results),
            "total_ports":      total_ports,
            "critical_ports":   total_critical,
            "high_ports":       total_high,
            "dangerous_combos": len(report["dangerous_combos"]),
            "avg_score":        round(sum(all_scores)/len(all_scores), 1) if all_scores else 0,
        }

        if total_critical > 0 or any(c["severity"]=="CRITICO" for c in report["dangerous_combos"]):
            report["overall_risk"] = "CRITICO"
        elif total_high > 2:
            report["overall_risk"] = "ALTO"
        elif total_high > 0:
            report["overall_risk"] = "MEDIO"

        priority = 1
        for combo in report["dangerous_combos"]:
            if combo["severity"] == "CRITICO":
                urg = "INMEDIATA" if lang=="es" else "IMMEDIATE"
                report["action_plan"].append({
                    "priority": priority, "urgency": urg,
                    "device": combo["ip"],
                    "action": f"[{combo['name']}] {combo['action']}"
                })
                priority += 1
        for f in report["critical_findings"]:
            urg = "HOY" if lang=="es" else "TODAY"
            report["action_plan"].append({
                "priority": priority, "urgency": urg,
                "device": f["ip"],
                "action": f"Puerto {f['port']} ({f['service']}): {f['plain_action'] or ''}"
            })
            priority += 1

        return report


# =============================================================
# GESTOR DE DOCUMENTOS (persistente)
# =============================================================

class DocumentTrainer:
    def __init__(self):
        self.documents   = {}
        self.vectorizer  = None
        self.doc_vectors = None
        self.doc_texts   = []
        self.doc_names   = []
        self._load()

    def _save(self):
        try:
            with open(DOC_INDEX, "wb") as f:
                pickle.dump({
                    "documents": self.documents, "vectorizer": self.vectorizer,
                    "doc_vectors": self.doc_vectors, "doc_texts": self.doc_texts,
                    "doc_names": self.doc_names,
                }, f)
        except Exception as e:
            print(f"No se pudo guardar documentos: {e}")

    def _load(self):
        if not DOC_INDEX.exists():
            return
        try:
            with open(DOC_INDEX, "rb") as f:
                d = pickle.load(f)
            self.documents   = d.get("documents", {})
            self.vectorizer  = d.get("vectorizer")
            self.doc_vectors = d.get("doc_vectors")
            self.doc_texts   = d.get("doc_texts", [])
            self.doc_names   = d.get("doc_names", [])
            n = len(self.documents)
            if n: print(f"{n} {t('docs_loaded')}")
        except Exception as e:
            print(f"Error cargando documentos: {e}")

    def extract_text(self, filepath: str) -> str:
        ext = Path(filepath).suffix.lower()

        if ext == ".pdf":
            # Intentar todos los backends disponibles
            text = ""

            if PDF_BACKEND == "pdfplumber":
                try:
                    import pdfplumber
                    with pdfplumber.open(filepath) as pdf:
                        for page in pdf.pages:
                            try: text += (page.extract_text() or "") + "\n"
                            except: pass
                except Exception as e:
                    print(f"pdfplumber error: {e}")

            elif PDF_BACKEND == "fitz":
                try:
                    import fitz
                    doc = fitz.open(filepath)
                    for page in doc:
                        try: text += page.get_text() + "\n"
                        except: pass
                    doc.close()
                except Exception as e:
                    print(f"PyMuPDF error: {e}")

            elif PDF_BACKEND == "pypdf":
                try:
                    with open(filepath, "rb") as f:
                        reader = _pypdf.PdfReader(f)
                        for page in reader.pages:
                            try: text += (page.extract_text() or "") + "\n"
                            except: pass
                except Exception as e:
                    print(f"pypdf error: {e}")

            # Si aun vacio, leer bytes crudos buscando texto ASCII (ultimo recurso)
            if not text.strip():
                try:
                    with open(filepath, "rb") as f:
                        raw = f.read()
                    import re as _re
                    chunks = _re.findall(rb'[\x20-\x7E]{4,}', raw)
                    text = " ".join(c.decode("ascii", errors="ignore") for c in chunks)
                    print("Usando extraccion de texto crudo (fallback)")
                except Exception as e:
                    print(f"Fallback crudo error: {e}")

            return text.strip()

        elif ext == ".txt":
            for enc in ("utf-8", "latin-1", "cp1252", "utf-16"):
                try:
                    with open(filepath, "r", encoding=enc, errors="ignore") as f:
                        return f.read()
                except: pass
            return ""

        elif ext == ".docx":
            if DOCX_OK:
                try:
                    doc = docx.Document(filepath)
                    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                except: pass
            # fallback: leer XML interno del docx (es un ZIP)
            try:
                import zipfile, xml.etree.ElementTree as ET
                with zipfile.ZipFile(filepath) as z:
                    with z.open("word/document.xml") as xf:
                        tree = ET.parse(xf)
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                return " ".join(n.text or "" for n in tree.iter(f"{ns}t") if n.text)
            except: return ""

        elif ext in (".md", ".rst", ".csv", ".log", ".ini", ".conf", ".yaml", ".yml", ".json"):
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    with open(filepath, "r", encoding=enc, errors="ignore") as f:
                        return f.read()
                except: pass
            return ""

        return ""

    def validate_document(self, text: str) -> tuple:
        """Solo verifica que el documento tenga contenido legible. Sin restriccion de tema."""
        lang = SYSTEM_LANG
        if not text or len(text.strip()) < 50:
            return False, 0.0, t("doc_empty")
        # Calcular relevancia informativa (solo para mostrar, no para rechazar)
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return False, 0.0, t("doc_empty")
        hits  = sum(1 for w in words if w in SECURITY_KEYWORDS)
        score = hits / len(words) if words else 0.0
        msg = (f"{t('doc_valid')} ({score*100:.1f}% relevancia temas red/seguridad)." if lang=="es"
               else f"{t('doc_valid')} ({score*100:.1f}% network/security relevance).")
        return True, score, msg

    def add_document(self, filepath: str) -> tuple:
        ext = Path(filepath).suffix.lower()
        supported = (".pdf", ".txt", ".docx", ".md", ".rst", ".csv",
                     ".log", ".ini", ".conf", ".yaml", ".yml", ".json")
        if ext not in supported:
            lang = SYSTEM_LANG
            return False, (
                f"Formato '{ext}' no soportado. Usa: {', '.join(supported)}" if lang=="es"
                else f"Format '{ext}' not supported. Use: {', '.join(supported)}"
            )

        text = self.extract_text(filepath)
        if not text or len(text.strip()) < 50:
            lang = SYSTEM_LANG
            tip = (" (Si es PDF escaneado/imagen, instala pdfplumber: pip install pdfplumber)"
                   if ext == ".pdf" else "")
            return False, (
                f"No se pudo extraer texto del documento.{tip}" if lang=="es"
                else f"Could not extract text from document.{tip}"
            )

        valid, score, reason = self.validate_document(text)
        if not valid:
            return False, reason

        doc_hash = hashlib.md5(text.encode()).hexdigest()
        if doc_hash in self.documents:
            return False, t("doc_duplicate")

        filename = Path(filepath).name
        self.documents[doc_hash] = {
            "filename": filename, "text": text,
            "score": round(score, 4), "date": datetime.now().isoformat(),
            "chars": len(text),
        }
        self._rebuild_index()
        self._save()

        lang = SYSTEM_LANG
        msg = (f"'{filename}' agregado correctamente ({len(text):,} caracteres, {score*100:.1f}% relevancia red/seg)."
               if lang=="es"
               else f"'{filename}' added successfully ({len(text):,} chars, {score*100:.1f}% network/sec relevance).")
        return True, msg

    def _rebuild_index(self):
        if not self.documents:
            return
        self.doc_texts = [v["text"]     for v in self.documents.values()]
        self.doc_names = [v["filename"] for v in self.documents.values()]
        if SKLEARN_OK:
            try:
                self.vectorizer  = TfidfVectorizer(max_features=5000, ngram_range=(1,2), min_df=1)
                self.doc_vectors = self.vectorizer.fit_transform(self.doc_texts)
            except Exception as e:
                print(f"Error reconstruyendo indice TF-IDF: {e}")
                self.vectorizer  = None
                self.doc_vectors = None
        # Si no hay sklearn, doc_texts y doc_names ya están listos para búsqueda simple

    def search(self, query: str, top_k: int = 3) -> list:
        if not self.doc_texts:
            return []

        # Búsqueda con TF-IDF (sklearn disponible)
        if SKLEARN_OK and self.doc_vectors is not None and self.vectorizer is not None:
            try:
                q_vec  = self.vectorizer.transform([query])
                scores = cosine_similarity(q_vec, self.doc_vectors).flatten()
                top_idx = scores.argsort()[::-1][:top_k]
                results = []
                for idx in top_idx:
                    if scores[idx] > 0.01:
                        fragment = self._extract_fragment(self.doc_texts[idx], query)
                        results.append((self.doc_names[idx], fragment))
                return results
            except Exception:
                pass  # fallback a búsqueda simple

        # Búsqueda simple por palabras clave (sin sklearn)
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        if not query_words:
            return []

        scored = []
        for i, text in enumerate(self.doc_texts):
            tl = text.lower()
            hits = sum(tl.count(w) for w in query_words)
            if hits > 0:
                scored.append((hits, i))

        scored.sort(reverse=True)
        results = []
        for _, idx in scored[:top_k]:
            fragment = self._extract_fragment(self.doc_texts[idx], query)
            results.append((self.doc_names[idx], fragment))
        return results

    def _extract_fragment(self, text: str, query: str, length: int = 400) -> str:
        """Extrae el fragmento más relevante del texto para la consulta."""
        tl = text.lower()
        best_pos = 0
        for word in query.lower().split():
            if len(word) > 2:
                p = tl.find(word)
                if p >= 0:
                    best_pos = p
                    break
        start    = max(0, best_pos - 100)
        fragment = text[start: start + length].strip()
        # Limpiar espacios múltiples y saltos excesivos
        fragment = re.sub(r'\n{3,}', '\n\n', fragment)
        fragment = re.sub(r'[ \t]{2,}', ' ', fragment)
        return fragment

    def list_documents(self) -> list:
        return [{"filename": v["filename"], "date": v["date"][:10],
                 "chars": v["chars"], "score": v["score"]}
                for v in self.documents.values()]

    def remove_document(self, filename: str) -> bool:
        for h, v in list(self.documents.items()):
            if v["filename"] == filename:
                del self.documents[h]
                self._rebuild_index()
                self._save()
                return True
        return False


# =============================================================
# CHATBOT DE SEGURIDAD
# =============================================================

class SecurityChatbot:
    def __init__(self, doc_trainer: DocumentTrainer = None):
        self.scan_report  = None
        self.scan_results = []
        self.doc_trainer  = doc_trainer or DocumentTrainer()
        self.lang         = SYSTEM_LANG if SYSTEM_LANG in ("es","en") else "es"

    def set_scan_report(self, report: dict, raw_results: list = None):
        self.scan_report  = report
        self.scan_results = raw_results or []

    def ask(self, question: str) -> str:
        q = question.lower().strip()

        # 1. Resumen
        if any(k in q for k in (["resumen","resultado","que encontraste","riesgo","analisis"] if self.lang=="es"
                                 else ["summary","result","found","risk","analysis"])):
            return self._summary()

        # 2. Plan
        if any(k in q for k in (["plan","que hacer","solucionar","arreglar","pasos","remediar"] if self.lang=="es"
                                 else ["plan","what to do","fix","steps","remediate"])):
            return self._action_plan()

        # 3. Criticos
        if any(k in q for k in (["critico","urgente","peligroso","grave","peor"] if self.lang=="es"
                                 else ["critical","urgent","dangerous","severe","worst"])):
            return self._criticals()

        # 4. QA base
        for qa in QA_KNOWLEDGE:
            kw = qa.get(f"kw_{self.lang}", qa.get("kw_es", []))
            if any(k in q for k in kw):
                return qa["answer"].get(self.lang, qa["answer"].get("es",""))

        # 5. Documentos del usuario
        doc_results = self.doc_trainer.search(question, top_k=2)
        if doc_results:
            hdr = ("Encontre informacion en tus documentos:\n\n" if self.lang=="es"
                   else "Found information in your documents:\n\n")
            parts = [hdr]
            for fname, fragment in doc_results:
                parts.append(f"[{fname}]\n{fragment}\n")
            return "\n".join(parts)

        # 6. Busqueda en base de puertos
        for port, info in PORT_EXPLANATIONS.items():
            svc_words = info.get("service","").lower().split()
            if str(port) in q or any(w in q for w in svc_words if len(w) > 3):
                icon = {"CRITICO":"[!!!]","ALTO":"[!!]","MEDIO":"[!]","BAJO":"[ ]"}.get(info["risk"],"[ ]")
                return (
                    f"{icon} Puerto {port} - {info['service']} (Riesgo: {info['risk']})\n\n"
                    f"Que significa: {info['plain_risk'].get(self.lang, info['plain_risk']['es'])}\n\n"
                    f"Que hacer: {info['action'].get(self.lang, info['action']['es'])}"
                )

        # 7. Default
        return self._default()

    def _summary(self) -> str:
        if not self.scan_report:
            return t("no_scan", self.lang)
        s    = self.scan_report.get("summary", {})
        risk = self.scan_report.get("overall_risk","BAJO")
        icon = {"CRITICO":"[!!!]","ALTO":"[!!]","MEDIO":"[!]","BAJO":"[OK]"}.get(risk,"[ ]")

        if self.lang == "es":
            lines = [f"{icon} RESUMEN DE SEGURIDAD - Nivel de Riesgo: {risk}\n",
                     f"Se analizaron {s.get('total_devices',0)} dispositivo(s) en tu red.",
                     f"Se encontraron {s.get('total_ports',0)} puertos abiertos en total."]
            if s.get("critical_ports",0):
                lines.append(f"[!!!] {s['critical_ports']} puerto(s) CRITICO(S): requieren accion inmediata.")
            if s.get("high_ports",0):
                lines.append(f"[!!] {s['high_ports']} puerto(s) de ALTO riesgo: deben revisarse pronto.")
            if s.get("dangerous_combos",0):
                lines.append(f"[ALERTA] {s['dangerous_combos']} combinacion(es) peligrosa(s) detectada(s).")
            lines.append("\nEscribe 'plan de accion' para ver los pasos a seguir.")
        else:
            lines = [f"{icon} SECURITY SUMMARY - Risk Level: {risk}\n",
                     f"Analyzed {s.get('total_devices',0)} device(s) on your network.",
                     f"Found {s.get('total_ports',0)} open ports in total."]
            if s.get("critical_ports",0):
                lines.append(f"[!!!] {s['critical_ports']} CRITICAL port(s): require immediate action.")
            if s.get("high_ports",0):
                lines.append(f"[!!] {s['high_ports']} HIGH risk port(s): should be reviewed soon.")
            if s.get("dangerous_combos",0):
                lines.append(f"[ALERT] {s['dangerous_combos']} dangerous combination(s) detected.")
            lines.append("\nType 'action plan' to see the steps to take.")

        return "\n".join(lines)

    def _action_plan(self) -> str:
        if not self.scan_report:
            return t("no_scan", self.lang)
        plan = self.scan_report.get("action_plan", [])
        if not plan:
            return ("Tu red parece bien configurada. No se encontraron acciones urgentes."
                    if self.lang=="es" else
                    "Your network seems well configured. No urgent actions found.")
        hdr = ("PLAN DE ACCION - Que hacer y en que orden\n\n"
               if self.lang=="es" else
               "ACTION PLAN - What to do and in what order\n\n")
        lines = [hdr]
        for item in plan:
            urg = item.get("urgency","")
            lines.append(f"[{urg}] Dispositivo: {item['device']}" if self.lang=="es"
                         else f"[{urg}] Device: {item['device']}")
            lines.append(f"  {item['priority']}. {item['action']}\n")
        return "\n".join(lines)

    def _criticals(self) -> str:
        if not self.scan_report:
            return t("no_scan", self.lang)
        crit   = self.scan_report.get("critical_findings", [])
        combos = [c for c in self.scan_report.get("dangerous_combos",[]) if c["severity"]=="CRITICO"]
        if not crit and not combos:
            return ("No se detectaron hallazgos criticos." if self.lang=="es"
                    else "No critical findings detected.")
        hdr = "HALLAZGOS CRITICOS\n\n" if self.lang=="es" else "CRITICAL FINDINGS\n\n"
        lines = [hdr]
        for c in combos:
            lines.append(f"[COMBO CRITICO] {c['name']} (dispositivo: {c['ip']})")
            lines.append(f"  {c['plain']}")
            lines.append(f"  Accion: {c['action']}\n" if self.lang=="es"
                         else f"  Action: {c['action']}\n")
        for f in crit:
            lines.append(f"[!!!] Puerto {f['port']} - {f['service']} (dispositivo: {f['ip']})")
            if f.get("plain_risk"):
                lines.append(f"  {f['plain_risk']}")
            if f.get("plain_action"):
                lines.append(f"  Accion: {f['plain_action']}\n" if self.lang=="es"
                             else f"  Action: {f['plain_action']}\n")
        return "\n".join(lines)

    def _default(self) -> str:
        n_docs = len(self.doc_trainer.documents)
        if self.lang == "es":
            msg = (
                "No tengo informacion especifica sobre esa consulta.\n\n"
                "Puedo ayudarte con:\n"
                "- 'resumen': estado general de tu red\n"
                "- 'plan de accion': pasos para mejorar la seguridad\n"
                "- 'criticos': los problemas mas urgentes\n"
                "- Preguntas sobre puertos: 'puerto 445', 'que es RDP', 'es peligroso SSH'\n"
                "- Temas: firewall, VPN, contrasenas, ransomware, backup, anomalias"
            )
            if not self.scan_report:
                msg += "\n\nEjecuta un escaneo primero para obtener analisis de tu red."
            if n_docs == 0:
                msg += "\n\nConsejo: Sube documentos PDF/TXT en la pestana 'Entrenamiento IA' para ampliar mi conocimiento."
        else:
            msg = (
                "I don't have specific information about that query.\n\n"
                "I can help you with:\n"
                "- 'summary': your network's general status\n"
                "- 'action plan': steps to improve security\n"
                "- 'critical': the most urgent issues\n"
                "- Port questions: 'port 445', 'what is RDP', 'is SSH dangerous'\n"
                "- Topics: firewall, VPN, passwords, ransomware, backup, anomalies"
            )
            if not self.scan_report:
                msg += "\n\nRun a scan first to get your network analysis."
            if n_docs == 0:
                msg += "\n\nTip: Upload PDF/TXT documents in the 'AI Training' tab to expand my knowledge."
        return msg