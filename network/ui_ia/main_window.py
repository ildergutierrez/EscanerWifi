#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_window.py - NetGuard · Interfaz gráfica principal
Manejo profesional de threads con QMutex
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QTextEdit, QLineEdit, QLabel, QProgressBar,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject, QMutex
from PyQt6.QtGui import QTextCursor

import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.scanner import NetworkScanner
from core.monitor import TrafficMonitor
from core.ai_detector import AnomalyDetector, VulnerabilityAnalyzer, SecurityChatbot


# =============================================================
# ESTILO
# =============================================================

STYLE = """
QMainWindow, QWidget { background:#0d1117; color:#c9d1d9; }
QSplitter::handle { background:#21262d; width:2px; }

QPushButton {
    background:#161b22; border:1px solid #30363d;
    border-radius:6px; padding:8px 16px;
    font-size:11px; font-weight:600; color:#c9d1d9;
}
QPushButton:hover { background:#21262d; border-color:#58a6ff; color:#58a6ff; }
QPushButton:disabled { color:#484f58; border-color:#21262d; }

QPushButton#btn_scan   { background:#0d419d; border-color:#1f6feb; color:#e6edf3; }
QPushButton#btn_scan:hover { background:#1158c7; }
QPushButton#btn_cancel { background:#6e1a1a; border-color:#da3633; color:#ffa198; }
QPushButton#btn_cancel:hover { background:#8b2020; }
QPushButton#btn_monitor { background:#0a3622; border-color:#238636; color:#3fb950; }
QPushButton#btn_monitor:hover { background:#0d4b2b; }
QPushButton#btn_stop { background:#5a3e1b; border-color:#d29922; color:#e3b341; }
QPushButton#btn_stop:hover { background:#6e4d22; }
QPushButton#btn_send {
    background:#1f6feb; border-color:#1f6feb;
    color:#ffffff; min-width:70px;
}
QPushButton#btn_send:hover { background:#388bfd; }

QTextEdit#console {
    background:#0d1117; border:1px solid #21262d;
    border-radius:6px; font-family:'Courier New',monospace;
    font-size:11px; color:#c9d1d9; padding:8px;
}
QTextEdit#chat_display {
    background:#161b22; border:1px solid #21262d;
    border-radius:6px; font-size:11px; color:#c9d1d9; padding:8px;
}
QLineEdit#chat_input {
    background:#0d1117; border:1px solid #30363d;
    border-radius:6px; padding:8px 12px; font-size:11px; color:#c9d1d9;
}
QLineEdit#chat_input:focus { border-color:#58a6ff; }

QLabel#lbl_title {
    font-size:15px; font-weight:700; color:#e6edf3;
    padding:10px 16px; background:#161b22; border-bottom:1px solid #21262d;
}
QLabel#lbl_section {
    font-size:10px; font-weight:700; color:#8b949e;
    padding:4px 0; letter-spacing:1px;
}
QLabel#lbl_info {
    font-size:10px; color:#8b949e; padding:3px 10px;
    background:#161b22; border-radius:4px; border:1px solid #21262d;
}
QLabel#lbl_cmd {
    font-family:'Courier New',monospace; font-size:10px; color:#e3b341;
    background:#1c1a00; border:1px solid #3a3200;
    border-radius:4px; padding:4px 8px;
}

QProgressBar {
    background:#21262d; border:none; border-radius:3px; height:4px;
}
QProgressBar::chunk { background:#1f6feb; border-radius:3px; }
"""

RISK_COLOR = {
    "CRITICO": "#ff4444",
    "ALTO": "#f85149",
    "MEDIO": "#e3b341",
    "BAJO": "#3fb950"
}


# =============================================================
# WORKERS PROFESIONALES CON QMUTEX
# =============================================================

class ScanHostsWorker(QObject):
    """Worker para escanear hosts - THREAD-SAFE con QMutex"""
    finished = pyqtSignal(list)
    device_found = pyqtSignal(dict)
    output = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
        self._is_running = True
        self._mutex = QMutex()

    def stop(self):
        """Detiene el worker de forma segura"""
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

    def is_running(self):
        """Verifica si debe continuar ejecutándose"""
        self._mutex.lock()
        running = self._is_running
        self._mutex.unlock()
        return running

    def run(self):
        """Ejecuta el escaneo de hosts"""
        try:
            self.output.emit("🔍 INICIANDO ESCANEO DE RED")
            self.output.emit("📡 Buscando dispositivos activos...")

            if not self.is_running():
                self.finished.emit([])
                return

            devices = self.scanner.scan_hosts_sync()

            if not self.is_running():
                self.finished.emit([])
                return

            for device in devices:
                if not self.is_running():
                    break
                self.device_found.emit(device)

            self.finished.emit(devices if self.is_running() else [])

        except Exception as e:
            self.error.emit(f"❌ Error: {str(e)}")
            self.finished.emit([])


class ScanPortsWorker(QObject):
    """Worker para escanear puertos - THREAD-SAFE con QMutex"""
    finished = pyqtSignal(str, list, list, int, str)
    output = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
        self._is_running = True
        self._mutex = QMutex()

    def stop(self):
        """Detiene el worker de forma segura"""
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

    def is_running(self):
        """Verifica si debe continuar ejecutándose"""
        self._mutex.lock()
        running = self._is_running
        self._mutex.unlock()
        return running

    def scan_device(self, ip, hostname):
        """Escanea puertos de un dispositivo"""
        try:
            if not self.is_running():
                self.finished.emit(ip, [], [], 0, hostname)
                return

            self.output.emit(f"")
            self.output.emit(f"📡 ESCANEANDO: {ip}")
            self.output.emit(f"   {'='*40}")

            ports = self.scanner.scan_ports_sync(ip)

            if not self.is_running():
                self.finished.emit(ip, [], [], 0, hostname)
                return

            classified, score = self.scanner.classify_ports(ports)

            self.output.emit(f"   {'='*40}")
            self.output.emit(f"   ✅ Completado {ip}")

            self.finished.emit(ip, ports, classified, score, hostname)

        except Exception as e:
            self.error.emit(f"❌ Error: {str(e)}")
            self.finished.emit(ip, [], [], 0, hostname)


# =============================================================
# VENTANA PRINCIPAL
# =============================================================

class MainWindow(QMainWindow):
    """Ventana principal con manejo profesional de threads"""
    scanner_output = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NetGuard - Seguridad de Red con IA Local")
        self.setGeometry(80, 60, 1200, 700)
        self.setMinimumSize(1100, 600)
        self.setStyleSheet(STYLE)

        # Módulos
        self.scanner = NetworkScanner(output_callback=self._on_scanner_raw)
        self.monitor = TrafficMonitor()
        self.anomaly_detector = AnomalyDetector()
        self.vuln_analyzer = VulnerabilityAnalyzer()
        self.chatbot = SecurityChatbot()

        # Estado (thread-safe con mutex)
        self._mutex = QMutex()
        self.scan_active = False
        self.monitoring_active = False
        self.scan_results = []
        self.scanned_ips = set()
        self.total_ports_found = 0
        self.traffic_history = []
        self._devices_to_scan = []
        self._devices_scanned = 0
        self._last_report = None

        # Threads (guardar referencias)
        self._host_thread = None
        self._host_worker = None
        self._port_threads = []
        self._port_workers = []

        # Construir UI
        self._build_ui()

        # Señales
        self.scanner_output.connect(self._display_scanner_msg)

        # Timer monitoreo
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_traffic)

        # Bienvenida
        self._show_welcome()
        self._chat_sys("🛡️ NetGuard activo. Ejecuta un escaneo para comenzar.")

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self):
        """Construye la interfaz de usuario"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet("background:#161b22; border-bottom:1px solid #21262d;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("NETGUARD - SEGURIDAD DE RED CON IA LOCAL")
        title.setStyleSheet("font-size:14px; font-weight:700; color:#e6edf3; background:transparent;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self.lbl_ip = QLabel(f"IP: {self.scanner.get_local_ip()} | Rango: {self.scanner.get_network_range()}")
        self.lbl_ip.setObjectName("lbl_info")
        h_layout.addWidget(self.lbl_ip)
        layout.addWidget(header)

        # Info bar
        info = QWidget()
        info.setFixedHeight(36)
        info.setStyleSheet("background:#0d1117; border-bottom:1px solid #161b22;")
        i_layout = QHBoxLayout(info)
        i_layout.setContentsMargins(12, 0, 12, 0)
        i_layout.setSpacing(8)

        self.lbl_status = QLabel("LISTO")
        self.lbl_devices = QLabel("Dispositivos: 0")
        self.lbl_ports = QLabel("Puertos: 0")
        self.lbl_scanning = QLabel("")
        self.lbl_ai_status = QLabel("IA: sin entrenar")

        for lbl in (self.lbl_status, self.lbl_devices, self.lbl_ports,
                    self.lbl_scanning, self.lbl_ai_status):
            lbl.setObjectName("lbl_info")
            i_layout.addWidget(lbl)

        i_layout.addStretch()
        self.lbl_cmd = QLabel("")
        self.lbl_cmd.setObjectName("lbl_cmd")
        self.lbl_cmd.hide()
        i_layout.addWidget(self.lbl_cmd)
        layout.addWidget(info)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        layout.addWidget(self.progress)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        layout.addWidget(splitter, 1)

        # Panel izquierdo - Consola
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 6, 12)
        left_layout.setSpacing(8)

        lbl_console = QLabel("CONSOLA DE ANÁLISIS")
        lbl_console.setObjectName("lbl_section")
        left_layout.addWidget(lbl_console)

        self.console = QTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        left_layout.addWidget(self.console, 1)

        # Botones
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_scan = QPushButton("🔍 ESCANEAR")
        self.btn_cancel = QPushButton("❌ CANCELAR")
        self.btn_monitor = QPushButton("📡 MONITOREAR")
        self.btn_stop = QPushButton("⏹️ DETENER")
        self.btn_train = QPushButton("🧠 ENTRENAR IA")
        self.btn_clear = QPushButton("🗑️ LIMPIAR")

        self.btn_scan.setObjectName("btn_scan")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_monitor.setObjectName("btn_monitor")
        self.btn_stop.setObjectName("btn_stop")

        self.btn_cancel.setEnabled(False)
        self.btn_stop.setEnabled(False)

        for btn in (self.btn_scan, self.btn_cancel, self.btn_monitor,
                    self.btn_stop, self.btn_train, self.btn_clear):
            btn_row.addWidget(btn)

        left_layout.addLayout(btn_row)
        splitter.addWidget(left)

        # Panel derecho - Chat
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 12, 12, 12)
        right_layout.setSpacing(8)

        lbl_chat = QLabel("ASISTENTE IA LOCAL")
        lbl_chat.setObjectName("lbl_section")
        right_layout.addWidget(lbl_chat)

        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chat_display")
        self.chat_display.setReadOnly(True)
        right_layout.addWidget(self.chat_display, 1)

        # Botones rápidos
        quick = QHBoxLayout()
        quick.setSpacing(4)
        for label, prompt in [
            ("Resumen", "resumen de vulnerabilidades"),
            ("Críticos", "puertos críticos"),
            ("Ransomware", "protección ransomware"),
            ("Firewall", "configurar firewall"),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, p=prompt: self._send_chat(p))
            quick.addWidget(btn)
        right_layout.addLayout(quick)

        # Input chat
        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self.chat_input = QLineEdit()
        self.chat_input.setObjectName("chat_input")
        self.chat_input.setPlaceholderText("Pregunta sobre seguridad...")
        self.chat_input.returnPressed.connect(self._on_chat_send)
        self.btn_send = QPushButton("Enviar")
        self.btn_send.setObjectName("btn_send")
        self.btn_send.clicked.connect(self._on_chat_send)
        input_row.addWidget(self.chat_input, 1)
        input_row.addWidget(self.btn_send)
        right_layout.addLayout(input_row)

        splitter.addWidget(right)
        splitter.setSizes([700, 500])

        # Conexiones
        self.btn_scan.clicked.connect(self._run_scan)
        self.btn_cancel.clicked.connect(self._cancel_scan)
        self.btn_monitor.clicked.connect(self._start_monitoring)
        self.btn_stop.clicked.connect(self._stop_monitoring)
        self.btn_train.clicked.connect(self._train_ai)
        self.btn_clear.clicked.connect(self._clear_output)

    # =========================================================
    # UTILIDADES
    # =========================================================

    def _con(self, text, color="#c9d1d9", bold=False):
        """Añade texto a la consola"""
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.console.setTextCursor(cursor)
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if bold:
            safe = f"<b>{safe}</b>"
        self.console.insertHtml(f"<font color='{color}'>{safe}</font><br>")
        self.console.ensureCursorVisible()

    def _con_cmd(self, cmd):
        """Muestra un comando ejecutado"""
        self._con(f"$ {cmd}", "#e3b341", bold=True)
        self.lbl_cmd.setText(f"$ {cmd}")
        self.lbl_cmd.show()

    def _con_sep(self, title=""):
        """Muestra un separador"""
        self._con("─" * 55, "#30363d")
        if title:
            self._con(f"  {title}", "#58a6ff", bold=True)

    def _show_welcome(self):
        """Muestra mensaje de bienvenida"""
        self._con_sep("NETGUARD - SEGURIDAD CON IA LOCAL")
        self._con(f"  IP: {self.scanner.get_local_ip()}", "#58a6ff")
        self._con(f"  Red: {self.scanner.get_network_range()}", "#58a6ff")
        self._con("─" * 55, "#30363d")
        self._con("  Presiona ESCANEAR para comenzar", "#8b949e")

    def _chat_append(self, role, text):
        """Añade mensaje al chat"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)

        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        if role == "user":
            self.chat_display.insertHtml(
                f"<div style='margin:6px 0;'>"
                f"<span style='color:#58a6ff;font-weight:700;'>Tú:</span> "
                f"<span style='color:#c9d1d9;'>{safe}</span></div>"
            )
        elif role == "assistant":
            self.chat_display.insertHtml(
                f"<div style='margin:6px 0; background:#1c2128; padding:8px; "
                f"border-radius:6px; border-left:3px solid #238636;'>"
                f"<span style='color:#3fb950;font-weight:700;'>IA:</span> "
                f"<span style='color:#c9d1d9;'>{safe}</span></div>"
            )
        else:
            self.chat_display.insertHtml(
                f"<div style='margin:4px 0; color:#8b949e; font-style:italic;'>{safe}</div>"
            )
        self.chat_display.ensureCursorVisible()

    def _chat_sys(self, text):
        """Añade mensaje del sistema al chat"""
        self._chat_append("system", text)

    def _on_chat_send(self):
        """Envía mensaje de chat"""
        msg = self.chat_input.text().strip()
        if not msg:
            return
        self.chat_input.clear()
        self._chat_append("user", msg)
        self._send_chat(msg)

    def _send_chat(self, msg):
        """Procesa mensaje y obtiene respuesta"""
        response = self.chatbot.ask(msg)
        self._chat_append("assistant", response)

    def _on_scanner_raw(self, msg):
        """Recibe mensaje raw del scanner"""
        self.scanner_output.emit(msg)

    def _display_scanner_msg(self, msg):
        """Muestra mensaje del scanner en consola"""
        msg = msg.strip()
        if not msg:
            return

        # Colorear
        if "✅" in msg or "Encontrado:" in msg:
            color = "#3fb950"
            ips = re.findall(r'\b\d+\.\d+\.\d+\.\d+\b', msg)
            for ip in ips:
                if ip not in self.scanned_ips:
                    self.scanned_ips.add(ip)
                    self.lbl_devices.setText(f"Dispositivos: {len(self.scanned_ips)}")
        elif "❌" in msg:
            color = "#f85149"
        elif "⚠" in msg:
            color = "#e3b341"
        elif "Escaneando" in msg or "🔍" in msg:
            color = "#58a6ff"
            ips = re.findall(r'\b\d+\.\d+\.\d+\.\d+\b', msg)
            if ips:
                self.lbl_scanning.setText(f"→ {ips[0]}")
        elif "Puerto" in msg and "abierto" in msg:
            color = "#e3b341"
            self.total_ports_found += 1
            self.lbl_ports.setText(f"Puertos: {self.total_ports_found}")
        else:
            color = "#8b949e"

        self._con(msg, color)

    def _set_controls(self, scanning=False, monitoring=False):
        """Habilita/deshabilita controles"""
        self.btn_scan.setEnabled(not scanning and not monitoring)
        self.btn_cancel.setEnabled(scanning)
        self.btn_monitor.setEnabled(not monitoring and not scanning)
        self.btn_stop.setEnabled(monitoring)
        self.btn_train.setEnabled(not scanning and not monitoring)

    def _clear_output(self):
        """Limpia consola"""
        self.console.clear()
        self._show_welcome()
        self.lbl_status.setText("LISTO")
        self.lbl_devices.setText("Dispositivos: 0")
        self.lbl_ports.setText("Puertos: 0")

    # =========================================================
    # ESCANEO (CON MANEJO PROFESIONAL DE THREADS)
    # =========================================================

    def _run_scan(self):
        """Inicia escaneo de red"""
        self._cleanup_threads()

        self.console.clear()
        self.scan_results = []
        self.scanned_ips = set()
        self.total_ports_found = 0
        self._devices_to_scan = []
        self._devices_scanned = 0
        self.scan_active = True

        self.lbl_devices.setText("Dispositivos: 0")
        self.lbl_ports.setText("Puertos: 0")
        self.lbl_scanning.setText("")

        self._con_sep("ANÁLISIS DE VULNERABILIDADES")
        self._con_cmd(f"nmap -sn -T4 {self.scanner.get_network_range()}")
        self._con("")

        self._set_controls(scanning=True)
        self.lbl_status.setText("ESCANEANDO")
        self.progress.show()

        # Thread para hosts
        self._host_thread = QThread()
        self._host_worker = ScanHostsWorker(self.scanner)
        self._host_worker.moveToThread(self._host_thread)

        self._host_thread.started.connect(self._host_worker.run)
        self._host_worker.finished.connect(self._on_hosts_finished)
        self._host_worker.device_found.connect(self._on_device_found)
        self._host_worker.output.connect(self.scanner_output.emit)
        self._host_worker.error.connect(lambda m: self._con(m, "#f85149"))

        self._host_worker.finished.connect(self._host_thread.quit)
        self._host_worker.finished.connect(self._host_worker.deleteLater)
        self._host_thread.finished.connect(self._host_thread.deleteLater)
        self._host_thread.finished.connect(lambda: setattr(self, '_host_thread', None))

        self._host_thread.start()

    def _on_device_found(self, device):
        """Dispositivo encontrado"""
        ip = device["ip"]
        if ip not in self.scanned_ips:
            self.scanned_ips.add(ip)
            self.lbl_devices.setText(f"Dispositivos: {len(self.scanned_ips)}")

    def _on_hosts_finished(self, devices):
        """Escaneo de hosts completado"""
        if not self.scan_active:
            return

        if not devices:
            self._con("No se encontraron dispositivos", "#f85149")
            self._finish_scan()
            return

        self._con("")
        self._con(f"  {len(devices)} dispositivo(s). Escaneando puertos...", "#3fb950", bold=True)
        self._con("")

        self._devices_to_scan = devices
        self._devices_scanned = 0

        self._cleanup_port_threads()

        for device in devices:
            if not self.scan_active:
                break
            self._scan_device_ports(device)

    def _scan_device_ports(self, device):
        """Escanea puertos de un dispositivo"""
        if not self.scan_active:
            return

        self._con_cmd(f"nmap -F -T4 {device['ip']}")

        thread = QThread()
        worker = ScanPortsWorker(self.scanner)
        worker.moveToThread(thread)

        self._port_threads.append(thread)
        self._port_workers.append(worker)

        thread.started.connect(lambda: worker.scan_device(device["ip"], device["hostname"]))
        worker.finished.connect(self._on_ports_finished)
        worker.output.connect(self.scanner_output.emit)
        worker.error.connect(lambda m: self._con(m, "#f85149"))

        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._on_port_thread_finished(thread, worker))

        thread.start()

    def _on_port_thread_finished(self, thread, worker):
        """Limpia thread de puertos"""
        if thread in self._port_threads:
            self._port_threads.remove(thread)
        if worker in self._port_workers:
            self._port_workers.remove(worker)
        self._check_completion()

    def _on_ports_finished(self, ip, ports, classified, score, hostname):
        """Escaneo de puertos completado"""
        if not self.scan_active:
            return

        self._mutex.lock()
        self.scan_results.append({
            "ip": ip,
            "hostname": hostname,
            "ports": ports,
            "classified": classified,
            "score": score
        })
        self._devices_scanned += 1
        self._mutex.unlock()

    def _check_completion(self):
        """Verifica si todos los dispositivos fueron escaneados"""
        self._mutex.lock()
        done = self._devices_scanned >= len(self._devices_to_scan) and len(self._port_threads) == 0
        self._mutex.unlock()

        if done and self.scan_active:
            self._show_results()

    def _show_results(self):
        """Muestra resultados finales"""
        if not self.scan_active:
            return

        self.scan_active = False
        self.console.clear()

        # Analizar resultados
        report = self.vuln_analyzer.analyze(self.scan_results)
        self._last_report = report
        self.chatbot.set_scan_report(report, self.scan_results)

        # Mostrar resumen
        self._con_sep("RESULTADOS DEL ANÁLISIS")
        s = report["summary"]
        risk = report["overall_risk"]
        color = RISK_COLOR.get(risk, "#c9d1d9")

        self._con(f"  RIESGO GLOBAL: {risk}", color, bold=True)
        self._con(f"  Dispositivos: {s['total_devices']}")
        self._con(f"  Puertos totales: {s['total_ports']}")
        self._con(f"  Críticos: {s['critical_ports']}", "#ff4444" if s['critical_ports'] else "#3fb950")
        self._con(f"  Alto riesgo: {s['high_ports']}", "#f85149" if s['high_ports'] else "#3fb950")
        self._con("")

        # Detalle por dispositivo
        for dev in report["devices"]:
            self._con(f"  📍 {dev['ip']} ({dev['hostname']})", "#58a6ff", bold=True)

            for finding in dev["findings"]:
                fcolor = RISK_COLOR.get(finding["risk"], "#c9d1d9")
                self._con(
                    f"     • Puerto {finding['port']:5} {finding['service']:<12} [{finding['risk']}]",
                    fcolor
                )
                self._con(f"       💡 {finding['recommendation']}", "#8b949e")

            if not dev["findings"]:
                self._con("     Sin puertos abiertos", "#3fb950")
            self._con("")

        self._chat_sys(
            f"Análisis completado. Riesgo {risk}. "
            f"{s['critical_ports']} críticos, {s['high_ports']} alto riesgo."
        )

        self._finish_scan()

    def _finish_scan(self):
        """Finaliza escaneo"""
        self.scan_active = False
        self.progress.hide()
        self.lbl_cmd.hide()
        self.lbl_scanning.setText("")
        self.lbl_status.setText("COMPLETADO")
        self._set_controls(scanning=False, monitoring=self.monitoring_active)

    def _cancel_scan(self):
        """Cancela escaneo en curso"""
        if not self.scan_active:
            return

        self.scan_active = False
        self._cleanup_threads()
        self._con("⚠️ ESCANEO CANCELADO", "#e3b341", bold=True)
        self._finish_scan()
        self.lbl_status.setText("CANCELADO")

    def _cleanup_threads(self):
        """Limpia todos los threads"""
        # Detener worker de hosts
        if self._host_worker:
            self._host_worker.stop()

        # Detener workers de puertos
        for worker in self._port_workers:
            worker.stop()

        # Esperar threads
        if self._host_thread and self._host_thread.isRunning():
            self._host_thread.quit()
            self._host_thread.wait(2000)

        for thread in self._port_threads:
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)

        self._port_threads.clear()
        self._port_workers.clear()
        self._host_thread = None
        self._host_worker = None

    def _cleanup_port_threads(self):
        """Limpia solo threads de puertos"""
        for worker in self._port_workers:
            worker.stop()

        for thread in self._port_threads:
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)

        self._port_threads.clear()
        self._port_workers.clear()

    # =========================================================
    # MONITOREO
    # =========================================================

    def _start_monitoring(self):
        """Inicia monitoreo de tráfico"""
        if self.monitoring_active:
            return

        self._con("")
        self._con_sep("MONITOREO EN TIEMPO REAL")

        self.monitoring_active = True
        self._set_controls(monitoring=True)
        self.lbl_status.setText("MONITOREANDO")
        self.monitor.initialize()
        self.timer.start(2000)

    def _stop_monitoring(self):
        """Detiene monitoreo"""
        if not self.monitoring_active:
            return

        self.timer.stop()
        self.monitoring_active = False
        self._set_controls(monitoring=False)
        self._con("Monitoreo detenido", "#e3b341")
        self.lbl_status.setText("LISTO")

    def _update_traffic(self):
        """Actualiza datos de tráfico"""
        t = self.monitor.get_traffic()
        self.traffic_history.append([t["upload_kb"], t["download_kb"]])
        if len(self.traffic_history) > 1000:
            self.traffic_history = self.traffic_history[-1000:]

        base_risk = self.monitor.evaluate_risk(t["upload_kb"], t["download_kb"])
        color = RISK_COLOR.get(base_risk, "#c9d1d9")

        if self.anomaly_detector.is_trained:
            result = self.anomaly_detector.predict(t["upload_kb"], t["download_kb"])
            if result["label"] == "ANOMALIA":
                prefix = "[ANOMALÍA] "
                color = RISK_COLOR.get(result["severity"], "#ff4444")
            else:
                prefix = "   "
        else:
            prefix = "   "

        self._con(
            f"  {prefix}⬆ {t['upload_kb']:7.2f} KB/s  "
            f"⬇ {t['download_kb']:7.2f} KB/s  "
            f"📊 {t['total_kb']:7.2f} KB/s  | {base_risk}",
            color
        )

    # =========================================================
    # IA
    # =========================================================

    def _train_ai(self):
        """Entrena modelo de IA"""
        n = len(self.traffic_history)
        if n < 10:
            self._con(f"Se necesitan 10 muestras (tienes {n})", "#e3b341")
            return

        self._con("Entrenando modelo...", "#58a6ff")
        QApplication.processEvents()

        if self.anomaly_detector.train(self.traffic_history):
            stats = self.anomaly_detector.get_stats()
            self._con(f"✅ IA entrenada con {n} muestras", "#3fb950", bold=True)
            self.lbl_ai_status.setText(f"IA: entrenada ({n} muestras)")
            self._chat_sys(f"Modelo entrenado. Upload μ={stats.get('upload_mean')} KB/s")
        else:
            self._con("❌ Error entrenando IA", "#f85149")

    # =========================================================
    # CIERRE
    # =========================================================

    def closeEvent(self, event):
        """Maneja cierre de aplicación"""
        self.timer.stop()
        if self.scan_active:
            self._cancel_scan()
        else:
            self._cleanup_threads()
        event.accept()