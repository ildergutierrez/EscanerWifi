#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_detector.py - NetGuard · Motor de IA Local
Detección de anomalías, análisis de vulnerabilidades y chatbot
"""

import numpy as np
import re
from collections import defaultdict

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False
    print("⚠ sklearn no disponible. Detección limitada.")

# =============================================================
# DETECTOR DE ANOMALÍAS
# =============================================================

class AnomalyDetector:
    """
    Detecta anomalías en tráfico de red usando Isolation Forest + reglas.
    """

    def __init__(self, contamination=0.08):
        self.contamination = contamination
        self.is_trained = False
        self.model = None
        self.scaler = None
        self.stats = {}
        self._upload_mean = 0
        self._download_mean = 0
        self._upload_std = 1
        self._download_std = 1

    def train(self, data):
        """
        Entrena modelo con historial de tráfico.
        data: lista de [upload_kb, download_kb]
        """
        if not SKLEARN_OK:
            return False

        try:
            if not data or len(data) < 10:
                return False

            X = np.array(data, dtype=float)
            if X.ndim == 1:
                X = X.reshape(-1, 1)
            if X.shape[1] < 2:
                return False

            # Estadísticas
            self._upload_mean = float(np.mean(X[:, 0]))
            self._download_mean = float(np.mean(X[:, 1]))
            self._upload_std = float(np.std(X[:, 0])) or 1.0
            self._download_std = float(np.std(X[:, 1])) or 1.0

            self.stats = {
                "samples": len(data),
                "upload_mean": round(self._upload_mean, 2),
                "upload_std": round(self._upload_std, 2),
                "download_mean": round(self._download_mean, 2),
                "download_std": round(self._download_std, 2),
                "upload_max": round(float(np.max(X[:, 0])), 2),
                "download_max": round(float(np.max(X[:, 1])), 2),
            }

            # Normalizar y entrenar
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            self.model = IsolationForest(
                contamination=self.contamination,
                n_estimators=150,
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_scaled)
            self.is_trained = True
            return True

        except Exception as e:
            print(f"❌ Error entrenando IA: {e}")
            return False

    def predict(self, upload_kb, download_kb):
        """
        Predice si una muestra es anómala.
        Retorna dict con label, severity, reasons
        """
        reasons = []
        severity = "NORMAL"

        # Reglas heurísticas
        total = upload_kb + download_kb

        if upload_kb > 8000:
            reasons.append("Upload extremo: posible exfiltración de datos")
            severity = "CRITICO"
        elif upload_kb > 3000:
            reasons.append("Upload muy alto: posible exfiltración")
            severity = "ALTO"

        if download_kb > 15000:
            reasons.append("Download extremo: posible DDoS")
            severity = "CRITICO"

        if total > 20000:
            reasons.append("Tráfico total extremo")
            severity = "CRITICO"

        # Isolation Forest
        ml_anomaly = False
        if self.is_trained and self.model and self.scaler:
            try:
                sample = np.array([[upload_kb, download_kb]], dtype=float)
                scaled = self.scaler.transform(sample)
                pred = self.model.predict(scaled)

                if pred[0] == -1:
                    ml_anomaly = True
                    up_dev = abs(upload_kb - self._upload_mean) / self._upload_std
                    dl_dev = abs(download_kb - self._download_mean) / self._download_std

                    if up_dev > dl_dev:
                        reasons.append(f"Upload inusual ({up_dev:.1f}σ sobre media)")
                    else:
                        reasons.append(f"Download inusual ({dl_dev:.1f}σ sobre media)")

                    if severity == "NORMAL":
                        severity = "MEDIO"

            except Exception as e:
                print(f"⚠ Error en predict: {e}")

        return {
            "label": "ANOMALIA" if reasons else "NORMAL",
            "severity": severity if reasons else "NORMAL",
            "reasons": reasons,
            "ml_signal": ml_anomaly
        }

    def get_stats(self):
        return self.stats


# =============================================================
# ANALIZADOR DE VULNERABILIDADES
# =============================================================

class VulnerabilityAnalyzer:
    """
    Analiza resultados de escaneo y genera informes detallados.
    """

    def analyze(self, scan_results):
        """
        Analiza resultados y genera informe completo.
        scan_results: lista de dicts con resultados por dispositivo
        """
        report = {
            "summary": {},
            "devices": [],
            "critical_findings": [],
            "dangerous_combos": [],
            "action_plan": [],
            "overall_risk": "BAJO"
        }

        total_ports = 0
        total_critical = 0
        total_high = 0
        all_scores = []

        for device in scan_results:
            ip = device.get("ip", "?")
            hostname = device.get("hostname", "Desconocido")
            ports = set(device.get("ports", []))
            score = device.get("score", 0)

            all_scores.append(score)
            device_report = {
                "ip": ip,
                "hostname": hostname,
                "port_count": len(ports),
                "findings": [],
                "combos": [],
                "risk_score": score
            }

            # Analizar cada puerto
            for finding in device.get("classified", []):
                total_ports += 1
                risk = finding.get("risk", "MEDIO")

                device_report["findings"].append(finding)

                if risk == "CRITICO":
                    total_critical += 1
                    report["critical_findings"].append({
                        "ip": ip,
                        "port": finding["port"],
                        "service": finding["service"],
                        "recommendation": finding["recommendation"]
                    })
                elif risk == "ALTO":
                    total_high += 1

            # Detectar combinaciones
            # (esto requeriría importar de scanner, lo simplificamos)
            if {445, 3389}.issubset(ports):
                combo = {
                    "ip": ip,
                    "ports": [445, 3389],
                    "severity": "CRITICO",
                    "name": "SMB + RDP",
                    "description": "Combinación favorita de ransomware"
                }
                device_report["combos"].append(combo)
                report["dangerous_combos"].append(combo)

            report["devices"].append(device_report)

        # Resumen
        report["summary"] = {
            "total_devices": len(scan_results),
            "total_ports": total_ports,
            "critical_ports": total_critical,
            "high_ports": total_high,
            "dangerous_combos": len(report["dangerous_combos"]),
            "avg_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
        }

        # Riesgo global
        if total_critical > 0 or report["dangerous_combos"]:
            report["overall_risk"] = "CRITICO"
        elif total_high > 2:
            report["overall_risk"] = "ALTO"
        elif total_high > 0:
            report["overall_risk"] = "MEDIO"

        # Plan de acción
        priority = 1
        for combo in report["dangerous_combos"]:
            report["action_plan"].append({
                "priority": priority,
                "urgency": "INMEDIATA",
                "device": combo["ip"],
                "action": f"[{combo['name']}] {combo.get('description', '')}"
            })
            priority += 1

        for finding in report["critical_findings"]:
            report["action_plan"].append({
                "priority": priority,
                "urgency": "HOY",
                "device": finding["ip"],
                "action": f"Puerto {finding['port']} ({finding['service']}): {finding['recommendation']}"
            })
            priority += 1

        return report


# =============================================================
# CHATBOT DE SEGURIDAD
# =============================================================

class SecurityChatbot:
    """
    Asistente de seguridad 100% local.
    Responde preguntas sobre vulnerabilidades y configuración.
    """

    KNOWLEDGE = {
        "smb": "🔴 **SMB (puerto 445)** es el vector favorito de ransomware (WannaCry, NotPetya).\n\n**Acción:** Bloquear en firewall. Deshabilitar SMBv1.",
        "rdp": "🔴 **RDP (puerto 3389)** es el principal punto de entrada de ransomware.\n\n**Protección:** Bloquear en firewall. Usar VPN. Habilitar NLA.",
        "ssh": "🟡 **SSH (puerto 22)** seguro si está bien configurado.\n\n**Hardening:** Deshabilitar contraseñas, usar claves, cambiar puerto, fail2ban.",
        "ftp": "🔴 **FTP (puerto 21)** transmite credenciales en texto plano.\n\n**Alternativa:** SFTP (SSH) o FTPS.",
        "telnet": "🔴 **TELNET (puerto 23)** - TRANSMITE TODO EN TEXTO PLANO.\n\n**Acción:** Deshabilitar INMEDIATAMENTE. Usar SSH.",
        "mysql": "🔴 **MySQL (puerto 3306)** no debe exponerse.\n\n**Solución:** bind-address = 127.0.0.1 en my.cnf",
        "mongodb": "🔴 **MongoDB (puerto 27017)** históricamente sin autenticación.\n\n**Solución:** bindIp: 127.0.0.1 en mongod.conf",
        "redis": "🔴 **Redis (puerto 6379)** - PERMITE ESCRIBIR ARCHIVOS.\n\n**Solución:** bind 127.0.0.1 en redis.conf",
        "vnc": "🔴 **VNC (puerto 5900)** sin cifrado.\n\n**Solución:** Usar solo por túnel SSH/VPN.",
        "firewall": "🛡️ **Configuración básica UFW:**\n```\nufw default deny incoming\nufw allow from 192.168.1.0/24 to any port 22\nufw allow 80\nufw allow 443\nufw enable\n```",
        "exfiltracion": "🔍 **Posible exfiltración:** Upload alto sostenido.\n\n**Verificar:** `nethogs`, `iftop`, `netstat -tulpn`",
        "ransomware": "🛡️ **Protección anti-ransomware:**\n• Bloquear SMB(445) y RDP(3389) en firewall\n• Backups 3-2-1\n• Actualizaciones automáticas\n• Segmentación de red"
    }

    def __init__(self):
        self.scan_report = None
        self.scan_results = []

    def set_scan_report(self, report, raw_results=None):
        """Inyecta resultados del último escaneo"""
        self.scan_report = report
        if raw_results:
            self.scan_results = raw_results

    def ask(self, question):
        """Responde una pregunta"""
        q = question.lower().strip()

        # Buscar en conocimiento base
        for key, answer in self.KNOWLEDGE.items():
            if key in q:
                return answer

        # Generar resumen si pregunta por resultados
        if any(word in q for word in ["resumen", "resultado", "vulnerabilidad"]):
            return self._generate_summary()

        # Respuesta por defecto
        return (
            "🤖 Puedo ayudarte con:\n"
            "• Puertos específicos (ej: 'puerto 445', 'SSH', 'RDP')\n"
            "• Configuración de firewall\n"
            "• Protección contra ransomware\n"
            "• Detección de exfiltración\n\n"
            "Ejecuta un escaneo para obtener análisis específico."
        )

    def _generate_summary(self):
        """Genera resumen del último escaneo"""
        if not self.scan_report:
            return "⚠ No hay resultados de escaneo aún."

        s = self.scan_report.get("summary", {})
        risk = self.scan_report.get("overall_risk", "BAJO")

        return (
            f"📊 **RESUMEN DE SEGURIDAD - Riesgo {risk}**\n\n"
            f"• Dispositivos: {s.get('total_devices', 0)}\n"
            f"• Puertos totales: {s.get('total_ports', 0)}\n"
            f"• Críticos: {s.get('critical_ports', 0)}\n"
            f"• Alto riesgo: {s.get('high_ports', 0)}\n"
            f"• Combinaciones peligrosas: {s.get('dangerous_combos', 0)}"
        )