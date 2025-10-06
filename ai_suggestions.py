import requests
import time
import random

# ---------------- Configuración OpenRouter ----------------
OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://localhost",
    "X-Title": "WiFi Analyzer App"
}

# Lista de modelos a probar en orden
MODELOS = [
    "google/gemini-2.0-flash-exp:free",
    "anthropic/claude-3-haiku", 
    "meta-llama/llama-3.3-70b-instruct",
    "microsoft/wizardlm-2-8x22b:free"
]

# Cache simple para evitar consultas repetidas
_cache = {}
_CACHE_DURATION = 30  # segundos

def _query_ai(prompt: str, max_retries=2) -> str:
    """Envía prompt a la API probando diferentes modelos"""
    
    # Verificar cache primero
    cache_key = hash(prompt)
    if cache_key in _cache:
        timestamp, response = _cache[cache_key]
        if time.time() - timestamp < _CACHE_DURATION:
            return response
    
    for intento in range(max_retries):
        modelo = MODELOS[intento % len(MODELOS)]
        
        try:
            payload = {
                "model": modelo,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                
                "temperature": 0.4
            }
            
            # Espera aleatoria entre intentos para evitar rate limits
            if intento > 0:
                time.sleep(1 + random.random())
            
            response = requests.post(OPENROUTER_URL, headers=HEADERS, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    message = data["choices"][0].get("message", {})
                    content = message.get("content", "⚠️ Sin respuesta.").strip()
                    # Guardar en cache
                    _cache[cache_key] = (time.time(), content)
                    return content
            
            elif response.status_code == 429:
                # Rate limit - esperar más tiempo
                time.sleep(3)
                continue
                
            elif response.status_code == 402:
                # Sin saldo, probar siguiente modelo
                continue
                
        except requests.exceptions.Timeout:
            continue
        except Exception:
            continue
    
    # Si todos los intentos fallan, usar respuestas predefinidas inteligentes
    return _respuesta_predefinida(prompt)

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
    return _query_ai(prompt)

def sugerencia_protocolo(red_meta: dict) -> str:
    """Obtiene recomendación de seguridad"""
    prompt = _crear_prompt_protocolo(red_meta)
    return _query_ai(prompt)

# ---------------- Prueba mejorada ----------------
# if __name__ == "__main__":
#     print("🚀 VERSIÓN OPTIMIZADA - MÚLTIPLES MODELOS")
#     print("=" * 45)
    
#     red_ejemplo = {
#         'SSID': 'MiCasa_WiFi_5G',
#         'Señal': -68,
#         'Banda': '5 GHz',
#         'Tecnologia': 'WiFi 5 (802.11ac)',
#         'Seguridad': 'WPA2-Personal',
#     }
    
#     print(f"\n📡 Modelos disponibles: {len(MODELOS)}")
    
#     print("\n🔧 **TECNOLOGÍA:**")
#     tech = sugerencia_tecnologia(red_ejemplo)
#     print(tech)
    
#     print("\n🔐 **SEGURIDAD:**")
#     seg = sugerencia_protocolo(red_ejemplo)
#     print(seg)
    
#     print(f"\n💾 Cache: {len(_cache)} entradas")