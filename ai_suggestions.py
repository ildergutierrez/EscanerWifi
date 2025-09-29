# ai_suggestions.py
"""
Genera sugerencias de tecnología y protocolo WiFi usando un modelo gratuito de HuggingFace.
- Timeout máximo: 5 segundos.
- Si no hay internet o el servicio no responde, se devuelve un mensaje claro.
"""

import requests

# Modelo gratuito de HuggingFace (puedes probar otros: "tiiuae/falcon-7b-instruct")
HF_MODEL = "google/flan-t5-large"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# Opcional: poner tu token gratuito de HuggingFace si quieres más estabilidad
HF_HEADERS = {}  # ejemplo: {"Authorization": "Bearer TU_TOKEN_HF"}


def _query_hf(prompt: str) -> str:
    try:
        response = requests.post(
            HF_API_URL,
            headers=HF_HEADERS,
            json={"inputs": prompt},
            timeout=5  # ⏱ máximo 5 segundos
        )
        if response.status_code == 200:
            data = response.json()
            # Algunas veces la salida es lista
            if isinstance(data, list) and len(data) > 0:
                if "generated_text" in data[0]:
                    return data[0]["generated_text"].strip()
                if isinstance(data[0], str):
                    return data[0].strip()
            # Otras veces es dict
            if isinstance(data, dict):
                if "generated_text" in data:
                    return data["generated_text"].strip()
                if "error" in data:
                    return f"Error IA: {data['error']}"
        return "⚠️ La IA no devolvió sugerencia."
    except requests.exceptions.Timeout:
        return "⏱ Tiempo de espera agotado (más de 5s)."
    except requests.exceptions.ConnectionError:
        return "🌐 No hay conexión a Internet."
    except Exception as e:
        return f"⚠️ Error consultando IA: {e}"


def sugerencia_tecnologia(red_meta: dict) -> str:
    prompt = f"""
    Tengo los siguientes datos de una red WiFi:
    SSID: {red_meta.get('SSID')}
    Banda: {red_meta.get('Banda')}
    Señal: {red_meta.get('Señal')} dBm
    Ancho de canal: {red_meta.get('AnchoCanal')}
    Tecnología actual: {red_meta.get('Tecnologia')}

    Dame una recomendación corta (máx. 3 líneas) sobre si conviene migrar a otra tecnología WiFi más moderna (ejemplo: WiFi 6 o 6E).
    """
    return _query_hf(prompt)


def sugerencia_protocolo(red_meta: dict) -> str:
    prompt = f"""
    Datos de la red WiFi:
    SSID: {red_meta.get('SSID')}
    Seguridad (AKM): {red_meta.get('Seguridad')}

    Dame una recomendación corta (máx. 3 líneas) sobre el protocolo de seguridad que debería usarse (ejemplo: WPA2, WPA3).
    """
    return _query_hf(prompt)
