# ==========================================
# traffic_classifier.py
# Clasificador pasivo de tráfico por servicio
# ==========================================

from typing import Tuple

# Mapa simple de servicios por rangos IP conocidos (CDN)
SERVICE_IP_MAP = {
    "YouTube": [
        "142.250.", "172.217.", "216.58."
    ],
    "Google": [
        "142.250.", "172.217.", "216.58."
    ],
    "Facebook": [
        "157.240."
    ],
    "Instagram": [
        "157.240."
    ],
    "TikTok": [
        "161.117.", "47.88."
    ],
    "Netflix": [
        "52.89.", "54.148.", "34.210."
    ]
}


def classify_service(ip: str, port: int) -> Tuple[str, str]:
    """
    Clasifica el servicio y protocolo basándose en IP y puerto.
    Retorna: (servicio, protocolo)
    """
    protocol = "HTTPS" if port == 443 else "HTTP" if port == 80 else "Otro"

    for service, prefixes in SERVICE_IP_MAP.items():
        for prefix in prefixes:
            if ip.startswith(prefix):
                return service, protocol

    return "Desconocido", protocol
