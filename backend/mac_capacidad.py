# mac_capacidad.py
# Sistema para detectar modelo y capacidad de routers por MAC
import re
import requests
import json
import os
from typing import Optional, Dict, Any, List

class RouterModelDetector:
    def __init__(self):
        self.database_file = "router_models_database.json"
        self.models_db = self._load_models_database()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _load_models_database(self) -> Dict:
        """Cargar base de datos de modelos desde archivo JSON"""
        try:
            with open(self.database_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error cargando base de datos: {e}")
            return self._create_fallback_database()
    
    def _create_fallback_database(self) -> Dict:
        """Crear base de datos básica si el archivo no existe"""
        return {
            "router_models": {},
            "technology_estimations": {
                "WiFi 6 (AX)": {"max_devices": 100, "confidence": "high"},
                "WiFi 5 (AC)": {"max_devices": 60, "confidence": "medium"},
                "WiFi 4 (N)": {"max_devices": 25, "confidence": "medium"},
                "WiFi 3 (G)": {"max_devices": 15, "confidence": "low"},
                "Unknown": {"max_devices": 30, "confidence": "low"}
            }
        }
    
    def get_oui_prefix(self, mac: str) -> str:
        """Obtener prefijo OUI de la MAC"""
        mac_clean = re.sub(r'[^0-9A-Fa-f]', '', mac.upper())
        return mac_clean[:6] if len(mac_clean) >= 6 else mac_clean
    
    def find_model_by_mac(self, mac: str, vendor: str) -> Optional[Dict]:
        """Buscar modelo específico por MAC y fabricante"""
        oui_prefix = self.get_oui_prefix(mac)
        
        # Buscar en la base de datos por fabricante
        if vendor in self.models_db.get("router_models", {}):
            vendor_models = self.models_db["router_models"][vendor]["common_models"]
            
            for model_info in vendor_models:
                if "mac_prefixes" in model_info and oui_prefix in model_info["mac_prefixes"]:
                    return {
                        "model": model_info["model"],
                        "max_devices": model_info["max_devices"],
                        "wifi_standard": model_info.get("wifi_standard", "Unknown"),
                        "confidence": "high",
                        "source": "exact_mac_match"
                    }
        
        return None
    
    def find_model_by_vendor(self, vendor: str) -> Optional[Dict]:
        """Buscar modelo más común por fabricante"""
        if vendor in self.models_db.get("router_models", {}):
            vendor_models = self.models_db["router_models"][vendor]["common_models"]
            if vendor_models:
                # Devolver el primer modelo (más común)
                model_info = vendor_models[0]
                return {
                    "model": model_info["model"],
                    "max_devices": model_info["max_devices"],
                    "wifi_standard": model_info.get("wifi_standard", "Unknown"),
                    "confidence": "medium",
                    "source": "vendor_common_model"
                }
        return None
    
    def estimate_by_technology(self, wifi_tech: str) -> Dict:
        """Estimar capacidad basada en tecnología WiFi"""
        tech_estimations = self.models_db.get("technology_estimations", {})
        
        for tech, est in tech_estimations.items():
            if tech.lower() in wifi_tech.lower():
                return {
                    "max_devices": est["max_devices"],
                    "confidence": est["confidence"],
                    "source": "technology_estimation"
                }
                
        return {
            "max_devices": 30,
            "confidence": "low",
            "source": "default_estimation"
        }
    
    def search_online_info(self, mac: str, vendor: str) -> Optional[Dict]:
        """Buscar información online como respaldo"""
        try:
            # MAC Vendors API para información adicional
            url = f"https://api.macvendors.com/{mac.replace(':', '')}"
            response = self.session.get(url, timeout=3)
            
            if response.status_code == 200:
                vendor_details = response.text
                # Intentar inferir modelo del nombre del fabricante
                inferred_model = self._infer_model_from_vendor_name(vendor_details)
                if inferred_model:
                    return {
                        "model": inferred_model["model"],
                        "max_devices": inferred_model["max_devices"],
                        "wifi_standard": inferred_model.get("wifi_standard", "Unknown"),
                        "confidence": "low",
                        "source": "online_api"
                    }
        except:
            pass
        
        return None
    
    def _infer_model_from_vendor_name(self, vendor_name: str) -> Optional[Dict]:
        """Inferir modelo basado en nombre del fabricante"""
        vendor_lower = vendor_name.lower()
        
        # Patrones comunes en nombres de modelos
        patterns = {
            "archer": {"model": "Archer Series", "max_devices": 60, "wifi_standard": "AC/AX"},
            "nighthawk": {"model": "Nighthawk Series", "max_devices": 70, "wifi_standard": "AC/AX"},
            "airport": {"model": "AirPort", "max_devices": 30, "wifi_standard": "AC"},
            "dir-": {"model": "DIR Series", "max_devices": 45, "wifi_standard": "AC"},
            "rt-": {"model": "ASUS Router", "max_devices": 65, "wifi_standard": "AC/AX"},
            "ax": {"model": "WiFi 6 Router", "max_devices": 80, "wifi_standard": "AX"},
            "ac": {"model": "WiFi 5 Router", "max_devices": 50, "wifi_standard": "AC"}
        }
        
        for pattern, model_info in patterns.items():
            if pattern in vendor_lower:
                return model_info
        
        return None
    
    def detect_router_model_and_capacity(self, mac: str, wifi_technology: str = "", vendor: str = "") -> Dict:
        """
        Detectar modelo del router y capacidad máxima de dispositivos
        
        Args:
            mac: Dirección MAC del router
            wifi_technology: Tecnología WiFi detectada
            vendor: Fabricante del router
            
        Returns:
            Dict con información del router
        """
        print(f"🔍 Analizando router: {vendor} - {mac}")
        
        result = {
            "mac": mac,
            "vendor": vendor or "Desconocido",
            "model": "No detectado",
            "max_devices": 30,
            "wifi_standard": "Desconocido",
            "confidence": "low",
            "sources": []
        }
        
        # Método 1: Búsqueda exacta por MAC
        if vendor and vendor != "Desconocido":
            exact_match = self.find_model_by_mac(mac, vendor)
            if exact_match:
                result.update(exact_match)
                result["sources"].append("exact_mac_match")
        
        # Método 2: Modelo común del fabricante
        if result["model"] == "No detectado" and vendor and vendor != "Desconocido":
            vendor_model = self.find_model_by_vendor(vendor)
            if vendor_model:
                result.update(vendor_model)
                result["sources"].append("vendor_common")
        
        # Método 3: Estimación por tecnología
        if wifi_technology:
            tech_est = self.estimate_by_technology(wifi_technology)
            # Usar estimación tecnológica si es mejor que la actual
            if (tech_est["confidence"] == "high" or 
                (tech_est["confidence"] == "medium" and result["confidence"] == "low")):
                result["max_devices"] = tech_est["max_devices"]
                result["confidence"] = tech_est["confidence"]
                result["sources"].append(tech_est["source"])
            
            result["wifi_standard"] = wifi_technology
        
        # Método 4: Búsqueda online como último recurso
        if result["model"] == "No detectado" and vendor and vendor != "Desconocido":
            online_info = self.search_online_info(mac, vendor)
            if online_info:
                result.update(online_info)
                result["sources"].append("online_search")
        
        # Ajustar capacidad para uso real
        result["max_devices"] = self._adjust_real_capacity(result["max_devices"])
        
        # Limpiar fuentes duplicadas
        result["sources"] = list(set(result["sources"]))
        
        print(f"✅ Resultado: {result['model']} - {result['max_devices']} dispositivos")
        
        return result
    
    def _adjust_real_capacity(self, theoretical_capacity: int) -> int:
        """Ajustar capacidad teórica a escenario real"""
        # En uso real, la capacidad efectiva es ~70% de la teórica
        return max(10, int(theoretical_capacity * 0.7))
    
    def get_database_stats(self) -> Dict:
        """Obtener estadísticas de la base de datos"""
        router_models = self.models_db.get("router_models", {})
        return {
            "total_vendors": len(router_models),
            "total_models": sum(len(vendor["common_models"]) for vendor in router_models.values()),
            "vendors": list(router_models.keys())
        }

# Función de conveniencia
def get_router_info(mac: str, wifi_tech: str = "", vendor: str = "") -> Dict:
    """
    Obtener información del router por MAC
    
    Args:
        mac: Dirección MAC del router
        wifi_tech: Tecnología WiFi (opcional)
        vendor: Fabricante (opcional)
        
    Returns:
        Dict con modelo y capacidad
    """
    detector = RouterModelDetector()
    return detector.detect_router_model_and_capacity(mac, wifi_tech, vendor)

# Ejemplo de uso
if __name__ == "__main__":
    print("🚀 Probando detector de modelos de routers...")
    
    detector = RouterModelDetector()
    stats = detector.get_database_stats()
    print(f"📊 Base de datos: {stats['total_vendors']} fabricantes, {stats['total_models']} modelos")
    
    # Ejemplos de prueba
    test_cases = [
        ("C0:C9:E3:12:34:56", "WiFi 5 (AC)", "TP-LINK TECHNOLOGIES CO.,LTD."),
        ("A8:49:4D:AB:CD:EF", "WiFi 6 (AX)", "Huawei Technologies Co., Ltd"),
        ("DC:54:AD:11:22:33", "WiFi 5 (AC)", "D-Link International"),
        ("00:0F:B0:44:55:66", "WiFi 4 (N)", "NETGEAR")
    ]
    
    for mac, tech, vendor in test_cases:
        print(f"\n--- Analizando {vendor} ---")
        info = get_router_info(mac, tech, vendor)
        
        print(f"📍 MAC: {info['mac']}")
        print(f"🏭 Fabricante: {info['vendor']}")
        print(f"📱 Modelo: {info['model']}")
        print(f"📊 Capacidad: {info['max_devices']} dispositivos")
        print(f"📡 Estándar: {info['wifi_standard']}")
        print(f"🎯 Confianza: {info['confidence']}")
        print(f"🔍 Fuentes: {', '.join(info['sources'])}")