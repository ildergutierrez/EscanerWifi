import requests
import time
import random
from dotenv import load_dotenv
import os
# ---------------- Configuración OpenRouter ----------------
load_dotenv()
OPENROUTER_API_KEY = os.getenv("API_KEY")
OPENROUTER_URL = os.getenv("OPENROUTER")
'''print("API:", OPENROUTER_API_KEY)
print("URL:", OPENROUTER_URL)'''

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://localhost",
    "X-Title": "WiFi Analyzer App"
}

# Lista de modelos a probar en orden
MODELOS = [
    "google/gemini-2.0-flash-exp:free",
    "microsoft/wizardlm-2-8x22b:free",
    "stepfun/step-3.5-flash:free",
    "arcee-ai/trinity-large-preview:free"
    
]

# Cache simple para evitar consultas repetidas
_cache = {}
_CACHE_DURATION = 30  # segundos

def _query_tecnologia(prompt: str) -> str:
    """Consulta directa a OpenRouter sin reintentos"""
    cache_key = prompt.strip()

    # 🔹 Verificar cache
    if cache_key in _cache:
        timestamp, response_cached = _cache[cache_key]
        if time.time() - timestamp < _CACHE_DURATION:
            #print("⚡ Respuesta desde cache")
            return response_cached
        
    MODELO = "stepfun/step-3.5-flash:free"  # usa uno válido

    payload = {
        "model": MODELO,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=HEADERS,
            json=payload,
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            return f"Error {response.status_code}: {response.text}"

    except Exception as e:
        return f"Error de conexión: {e}"
    

def _query_Protocolo(prompt: str) -> str:
    """Consulta directa a OpenRouter sin reintentos"""
    cache_key = prompt.strip()

    # 🔹 Verificar cache
    if cache_key in _cache:
        timestamp, response_cached = _cache[cache_key]
        if time.time() - timestamp < _CACHE_DURATION:
            #print("⚡ Respuesta desde cache")
            return response_cached
        
    MODELO = "arcee-ai/trinity-large-preview:free"  # usa uno válido

    payload = {
        "model": MODELO,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=HEADERS,
            json=payload,
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            return f"Error {response.status_code}: {response.text}"

    except Exception as e:
        return f"Error de conexión: {e}"
    
    


def _respuesta_predefinida(prompt: str) -> str:
    """Respuestas predefinidas inteligentes cuando la IA no está disponible"""
    if "tecnología" in prompt.lower() or "wifi 6" in prompt.lower():
        return "📡 WiFi 5 detectado. Actualiza a WiFi 6 para mejor eficiencia y menor latencia."
    elif "seguridad" in prompt.lower() or "wpa" in prompt.lower():
        return "🔒 WPA2 es seguro. Migra a WPA3 para protección mejorada."
    else:
        return "💡 Consulta no disponible temporalmente. Intenta más tarde."

def _crear_prompt_tecnologia(red_meta: dict) -> str:
    """Crea prompt ultra corto para tecnología"""
    return f"Analiza WiFi: {red_meta.get('SSID')} | Señal: {red_meta.get('Señal')}dBm | Banda: {red_meta.get('Banda')} | Tech: {red_meta.get('Tecnologia')}. ¿A que wifi recomiendas actualizar y por qué?  Respuesta  clara y puedes sugerir sitios o plataformas que me ayuden a entender el por que de dicha sugerencia."

def _crear_prompt_protocolo(red_meta: dict) -> str:
    """Crea prompt ultra corto para seguridad"""
    return f"Analiza seguridad: {red_meta.get('SSID')} | Seguridad: {red_meta.get('Seguridad')}. ¿Protocolo recomendado? se preciso en la respuesta y da sitios donde puedo saber más"

# ---------------- Funciones principales ----------------
def sugerencia_tecnologia(red_meta: dict) -> str:
    """Obtiene recomendación de tecnología"""
    prompt = _crear_prompt_tecnologia(red_meta)
    return _query_tecnologia(prompt)

def sugerencia_protocolo(red_meta: dict) -> str:
    """Obtiene recomendación de seguridad"""
    prompt = _crear_prompt_protocolo(red_meta)
    return _query_Protocolo(prompt)

# ---------------- Prueba mejorada ----------------
'''if __name__ == "__main__":
    print("🚀 VERSIÓN OPTIMIZADA - MÚLTIPLES MODELOS")
    print("=" * 45)
    
    red_ejemplo = {
         'SSID': 'MiCasa_WiFi_5G',
         'Señal': -68,
         'Banda': '5 GHz',
        'Tecnologia': 'WiFi 5 (802.11ac)',
         'Seguridad': 'WPA2-Personal',
     }
    
    print(f"\n📡 Modelos disponibles: {len(MODELOS)}")
    
    print("\n🔧 **TECNOLOGÍA:**")
    tech = sugerencia_tecnologia(red_ejemplo)
    print(tech)
    
    print("\n🔐 **SEGURIDAD:**")
    seg = sugerencia_protocolo(red_ejemplo)
    print(seg)
    
    print(f"\n💾 Cache: {len(_cache)} entradas")'''

#Fin