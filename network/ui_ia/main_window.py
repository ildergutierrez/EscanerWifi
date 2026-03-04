#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_window.py  –  NetGuard · Ventana principal completa
- IA 100% local, sin internet
- Pestaña de Entrenamiento IA con subida de documentos PDF/TXT
- Resultados explicados en lenguaje claro para cualquier usuario
- Monitoreo de trafico con explicaciones de que significa cada nivel
- Entrenamiento persistente entre sesiones
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QTextEdit, QLineEdit, QLabel, QProgressBar,
    QApplication, QTabWidget, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject, QMutex
from PyQt6.QtGui import QTextCursor, QFont, QColor

import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.scanner import NetworkScanner
from core.monitor import TrafficMonitor
from core.ai_detector import (
    AnomalyDetector, VulnerabilityAnalyzer,
    SecurityChatbot, DocumentTrainer, SYSTEM_LANG, t
)

# =============================================================
# ESTILO
# =============================================================

STYLE = """
QMainWindow, QWidget { background:#0d1117; color:#c9d1d9; }
QSplitter::handle { background:#21262d; width:2px; }
QTabWidget::pane { border:1px solid #21262d; background:#0d1117; }
QTabBar::tab {
    background:#161b22; border:1px solid #21262d;
    padding:8px 18px; font-size:11px; font-weight:600; color:#8b949e;
    border-bottom:none; border-radius:4px 4px 0 0; margin-right:2px;
}
QTabBar::tab:selected { background:#0d1117; color:#58a6ff; border-color:#58a6ff; }
QTabBar::tab:hover    { color:#c9d1d9; }

QPushButton {
    background:#161b22; border:1px solid #30363d;
    border-radius:6px; padding:8px 16px;
    font-size:11px; font-weight:600; color:#c9d1d9;
}
QPushButton:hover { background:#21262d; border-color:#58a6ff; color:#58a6ff; }
QPushButton:disabled { color:#484f58; border-color:#21262d; }

QPushButton#btn_scan    { background:#0d419d; border-color:#1f6feb; color:#e6edf3; }
QPushButton#btn_scan:hover { background:#1158c7; }
QPushButton#btn_cancel  { background:#6e1a1a; border-color:#da3633; color:#ffa198; }
QPushButton#btn_cancel:hover { background:#8b2020; }
QPushButton#btn_monitor { background:#0a3622; border-color:#238636; color:#3fb950; }
QPushButton#btn_monitor:hover { background:#0d4b2b; }
QPushButton#btn_stop    { background:#5a3e1b; border-color:#d29922; color:#e3b341; }
QPushButton#btn_stop:hover { background:#6e4d22; }
QPushButton#btn_send    { background:#1f6feb; border-color:#1f6feb; color:#fff; min-width:70px; }
QPushButton#btn_send:hover { background:#388bfd; }
QPushButton#btn_upload  { background:#0a3622; border-color:#238636; color:#3fb950; }
QPushButton#btn_upload:hover { background:#0d4b2b; }
QPushButton#btn_remove  { background:#6e1a1a; border-color:#da3633; color:#ffa198; font-size:10px; padding:4px 10px; }

QTextEdit#console {
    background:#0d1117; border:1px solid #21262d;
    border-radius:6px; font-family:'Courier New',monospace;
    font-size:11px; color:#c9d1d9; padding:8px;
}
QTextEdit#chat_display {
    background:#161b22; border:1px solid #21262d;
    border-radius:6px; font-size:11px; color:#c9d1d9; padding:8px;
}
QTextEdit#doc_log {
    background:#0d1117; border:1px solid #21262d;
    border-radius:6px; font-family:'Courier New',monospace;
    font-size:11px; color:#c9d1d9; padding:8px;
}
QLineEdit#chat_input {
    background:#0d1117; border:1px solid #30363d;
    border-radius:6px; padding:8px 12px; font-size:11px; color:#c9d1d9;
}
QLineEdit#chat_input:focus { border-color:#58a6ff; }

QLabel#lbl_title {
    font-size:15px; font-weight:700; color:#e6edf3;
    padding:10px 16px; background:#161b22;
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
QLabel#lbl_risk_card {
    font-size:13px; font-weight:700; padding:10px 16px;
    border-radius:8px; border:2px solid #30363d;
}

QProgressBar {
    background:#21262d; border:none; border-radius:3px; height:4px;
}
QProgressBar::chunk { background:#1f6feb; border-radius:3px; }

QTableWidget {
    background:#0d1117; border:1px solid #21262d;
    gridline-color:#21262d; font-size:11px; color:#c9d1d9;
}
QTableWidget::item { padding:6px; border:none; }
QTableWidget::item:selected { background:#1f3a5f; }
QHeaderView::section {
    background:#161b22; border:1px solid #21262d;
    padding:6px; font-size:10px; font-weight:700; color:#8b949e;
}

QScrollBar:vertical { background:#0d1117; width:8px; }
QScrollBar::handle:vertical { background:#30363d; border-radius:4px; min-height:20px; }
QScrollBar::handle:vertical:hover { background:#484f58; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }

QFrame#card {
    background:#161b22; border:1px solid #21262d;
    border-radius:8px; padding:4px;
}
"""

RISK_COLOR = {
    "CRITICO": "#ff4444",
    "ALTO":    "#f85149",
    "MEDIO":   "#e3b341",
    "BAJO":    "#3fb950",
}

RISK_BG = {
    "CRITICO": "#2d1117",
    "ALTO":    "#2b1a16",
    "MEDIO":   "#251e10",
    "BAJO":    "#0d1f10",
}


# =============================================================
# WORKERS
# =============================================================

class ScanHostsWorker(QObject):
    finished     = pyqtSignal(list)
    device_found = pyqtSignal(dict)
    error        = pyqtSignal(str)
    def __init__(self, scanner):
        super().__init__()
        self.scanner    = scanner
        self._cancelled = False
    def cancel(self): self._cancelled = True
    def run(self):
        try:
            devices = self.scanner.scan_hosts_sync()
            if self._cancelled: self.finished.emit([]); return
            for d in devices: self.device_found.emit(d)
            self.finished.emit(devices)
        except Exception as e:
            self.error.emit(f"Error hosts: {e}"); self.finished.emit([])


class ScanPortsWorker(QObject):
    finished = pyqtSignal(str, list, list, int, str)
    error    = pyqtSignal(str)
    def __init__(self, scanner):
        super().__init__()
        self.scanner    = scanner
        self._cancelled = False
    def cancel(self): self._cancelled = True
    def scan_single_device(self, ip, hostname):
        try:
            if self._cancelled: return
            ports = self.scanner.scan_ports_sync(ip)
            if self._cancelled: return
            classified, score = self.scanner.classify_ports(ports)
            self.finished.emit(ip, ports, classified, score, hostname)
        except Exception as e:
            self.error.emit(f"Error puertos {ip}: {e}")
            self.finished.emit(ip, [], [], 0, hostname)


# =============================================================
# VENTANA PRINCIPAL
# =============================================================

class MainWindow(QMainWindow):
    _scanner_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        title_es = "NetGuard — Seguridad de Red Inteligente [IA Local]"
        title_en = "NetGuard — Intelligent Network Security [Local AI]"
        self.setWindowTitle(title_es if SYSTEM_LANG == "es" else title_en)
        self.setGeometry(60, 40, 1300, 680)
        self.setMinimumSize(1200, 520)
        self.setStyleSheet(STYLE)

        # Modulos
        self.scanner           = NetworkScanner(output_callback=self._on_scanner_raw)
        self.monitor           = TrafficMonitor()
        self.anomaly_detector  = AnomalyDetector()
        self.vuln_analyzer     = VulnerabilityAnalyzer()
        self.doc_trainer       = DocumentTrainer()
        self.chatbot           = SecurityChatbot(self.doc_trainer)

        # Estado
        self.traffic_history   = []
        self.monitoring_active = False
        self.scan_active       = False
        self.scan_results      = []
        self.scanned_ips       = set()
        self.total_ports_found = 0
        self._devices_to_scan  = []
        self._devices_scanned  = 0
        self._mutex            = QMutex()
        self._last_report      = None
        # Strong references to port-scan threads/workers to prevent GC mid-run
        self._port_threads       = []
        self._port_workers       = []
        # Flags propias de estado de hilos (no depender de isRunning() sobre C++ destruido)
        self._host_thread_alive  = False
        self._port_threads_alive = []

        self._build_ui()
        self._scanner_msg.connect(self._display_scanner_msg)
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_traffic)
        self._show_welcome()
        self._chat_sys(self._txt(
            "IA Local activa. Sin internet. Analizo tu red y respondo tus preguntas en lenguaje sencillo.\n"
            "Ejecuta un escaneo para comenzar.",
            "Local AI active. No internet needed. I analyze your network and answer questions in plain language.\n"
            "Run a scan to get started."
        ))
        # Informar si hay modelo cargado
        if self.anomaly_detector.is_trained:
            n = self.anomaly_detector.stats.get("samples", "?")
            self.lbl_ai_status.setText(
                self._txt(f"IA: entrenada ({n} muestras)", f"AI: trained ({n} samples)")
            )
            self.lbl_ai_status.setStyleSheet("QLabel#lbl_info { color:#3fb950; }")

    def _txt(self, es: str, en: str) -> str:
        return es if SYSTEM_LANG == "es" else en

    # ==========================================================
    # CONSTRUCCION DE UI
    # ==========================================================

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet("background:#161b22; border-bottom:1px solid #21262d;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)

        lbl_title = QLabel("NETGUARD  —  Security Monitor  [IA Local / Local AI]")
        lbl_title.setObjectName("lbl_title")
        lbl_title.setStyleSheet("background:transparent; border:none;")
        h_lay.addWidget(lbl_title)
        h_lay.addStretch()

        self.lbl_ip = QLabel(
            f"IP: {self.scanner.get_local_ip()}  |  "
            f"{self._txt('Rango','Range')}: {self.scanner.get_network_range()}"
        )
        self.lbl_ip.setObjectName("lbl_info")
        h_lay.addWidget(self.lbl_ip)
        rl.addWidget(header)

        # Status bar
        status_bar = QWidget()
        status_bar.setFixedHeight(36)
        status_bar.setStyleSheet("background:#0d1117; border-bottom:1px solid #161b22;")
        sb = QHBoxLayout(status_bar)
        sb.setContentsMargins(12, 0, 12, 0)
        sb.setSpacing(8)

        self.lbl_status    = QLabel(self._txt("LISTO", "READY"))
        self.lbl_devices   = QLabel(self._txt("Dispositivos: 0", "Devices: 0"))
        self.lbl_ports     = QLabel(self._txt("Puertos: 0", "Ports: 0"))
        self.lbl_scanning  = QLabel("")
        self.lbl_ai_status = QLabel(self._txt("IA: sin entrenar", "AI: not trained"))

        for lbl in (self.lbl_status, self.lbl_devices, self.lbl_ports,
                    self.lbl_scanning, self.lbl_ai_status):
            lbl.setObjectName("lbl_info")
            sb.addWidget(lbl)

        sb.addStretch()
        self.lbl_cmd = QLabel("")
        self.lbl_cmd.setObjectName("lbl_cmd")
        self.lbl_cmd.hide()
        sb.addWidget(self.lbl_cmd)
        rl.addWidget(status_bar)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        rl.addWidget(self.progress)

        # TABS
        tabs = QTabWidget()
        rl.addWidget(tabs, 1)

        # Tab 1: Scanner + Chat
        tab_scan = QWidget()
        self._build_scan_tab(tab_scan)
        tabs.addTab(tab_scan, self._txt("Analisis de Red", "Network Analysis"))

        # Tab 2: Monitor
        tab_monitor = QWidget()
        self._build_monitor_tab(tab_monitor)
        tabs.addTab(tab_monitor, self._txt("Monitor de Trafico", "Traffic Monitor"))

        # Tab 3: Entrenamiento IA
        tab_train = QWidget()
        self._build_training_tab(tab_train)
        tabs.addTab(tab_train, self._txt("Entrenamiento IA", "AI Training"))

    # ----------------------------------------------------------
    # TAB 1 — ANALISIS
    # ----------------------------------------------------------

    def _build_scan_tab(self, parent):
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        layout.addWidget(splitter)

        # Panel izquierdo: consola
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 6, 12)
        ll.setSpacing(8)

        lbl_c = QLabel(self._txt("CONSOLA DE ANALISIS", "ANALYSIS CONSOLE"))
        lbl_c.setObjectName("lbl_section")
        ll.addWidget(lbl_c)

        self.console = QTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        ll.addWidget(self.console, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_scan    = QPushButton(self._txt("ESCANEAR", "SCAN"))
        self.btn_cancel  = QPushButton(self._txt("CANCELAR", "CANCEL"))
        self.btn_train   = QPushButton(self._txt("ENTRENAR IA", "TRAIN AI"))
        self.btn_clear   = QPushButton(self._txt("LIMPIAR", "CLEAR"))

        self.btn_scan.setObjectName("btn_scan")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setEnabled(False)

        for b in (self.btn_scan, self.btn_cancel, self.btn_train, self.btn_clear):
            btn_row.addWidget(b)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

        # Panel derecho: chat IA
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(6, 12, 12, 12)
        rl.setSpacing(8)

        lbl_ai = QLabel(self._txt(
            "ASISTENTE IA LOCAL — Explicaciones en Lenguaje Claro",
            "LOCAL AI ASSISTANT — Plain Language Explanations"
        ))
        lbl_ai.setObjectName("lbl_section")
        rl.addWidget(lbl_ai)

        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chat_display")
        self.chat_display.setReadOnly(True)
        rl.addWidget(self.chat_display, 1)

        # Botones rapidos
        quick_row1 = QHBoxLayout()
        quick_row1.setSpacing(4)
        quick_row2 = QHBoxLayout()
        quick_row2.setSpacing(4)

        sugerencias = [
            (self._txt("Resumen",   "Summary"),
             self._txt("dame un resumen de lo que encontraste", "give me a summary of what you found")),
            (self._txt("Criticos",  "Critical"),
             self._txt("muéstrame los problemas criticos y urgentes", "show me the critical and urgent problems")),
            (self._txt("Plan",      "Action Plan"),
             self._txt("dame el plan de accion paso a paso", "give me the action plan step by step")),
            (self._txt("SMB/445",   "SMB/445"),
             self._txt("que es el puerto 445 y por que es peligroso", "what is port 445 and why is it dangerous")),
            (self._txt("RDP/3389",  "RDP/3389"),
             self._txt("que es RDP y por que es peligroso", "what is RDP and why is it dangerous")),
            (self._txt("Firewall",  "Firewall"),
             self._txt("como configuro el firewall para proteger mi red", "how do I configure the firewall to protect my network")),
            (self._txt("VPN",       "VPN"),
             self._txt("que es una VPN y como me protege", "what is a VPN and how does it protect me")),
            (self._txt("Backup",    "Backup"),
             self._txt("como hacer copias de seguridad correctamente", "how to make backups correctly")),
        ]

        for i, (label, prompt) in enumerate(sugerencias):
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setStyleSheet("""
                QPushButton {
                    background:#21262d; border:1px solid #30363d;
                    border-radius:4px; font-size:10px; padding:2px 8px;
                }
                QPushButton:hover { border-color:#58a6ff; color:#58a6ff; }
            """)
            btn.clicked.connect(lambda _, p=prompt: self._send_to_chat(p))
            if i < 4:
                quick_row1.addWidget(btn)
            else:
                quick_row2.addWidget(btn)

        rl.addLayout(quick_row1)
        rl.addLayout(quick_row2)

        # Input
        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self.chat_input = QLineEdit()
        self.chat_input.setObjectName("chat_input")
        ph = (self._txt(
            "Escribe tu pregunta en lenguaje normal...",
            "Type your question in plain language..."
        ))
        self.chat_input.setPlaceholderText(ph)
        self.chat_input.returnPressed.connect(self._on_chat_send)
        self.btn_send = QPushButton(self._txt("Enviar", "Send"))
        self.btn_send.setObjectName("btn_send")
        self.btn_send.clicked.connect(self._on_chat_send)
        input_row.addWidget(self.chat_input, 1)
        input_row.addWidget(self.btn_send)
        rl.addLayout(input_row)

        splitter.addWidget(right)
        splitter.setSizes([820, 620])

        # Signals
        self.btn_scan.clicked.connect(self._run_scan)
        self.btn_cancel.clicked.connect(self._cancel_scan)
        self.btn_train.clicked.connect(self._train_traffic_model)
        self.btn_clear.clicked.connect(self._clear_output)

    # ----------------------------------------------------------
    # TAB 2 — MONITOR
    # ----------------------------------------------------------

    def _build_monitor_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Explicacion del monitor
        info_frame = QFrame()
        info_frame.setObjectName("card")
        info_frame.setStyleSheet(
            "QFrame#card { background:#161b22; border:1px solid #21262d; border-radius:8px; padding:8px; }"
        )
        info_lay = QVBoxLayout(info_frame)
        info_lay.setContentsMargins(12, 8, 12, 8)

        lbl_info = QLabel(self._txt(
            "COMO INTERPRETAR EL MONITOR DE TRAFICO",
            "HOW TO INTERPRET THE TRAFFIC MONITOR"
        ))
        lbl_info.setObjectName("lbl_section")
        info_lay.addWidget(lbl_info)

        explain = QLabel(self._txt(
            "SUBIDA (Upload): datos que tu red envia hacia internet.  |  "
            "BAJADA (Download): datos que recibes de internet.  |  "
            "NORMAL (verde): trafico habitual.  |  "
            "ATENCION (amarillo): trafico inusualmente alto — verifica que no haya programas descargando sin permiso.  |  "
            "ALERTA (rojo): trafico muy alto — puede indicar un ataque o un virus enviando datos.",
            "UPLOAD: data your network sends to the internet.  |  "
            "DOWNLOAD: data you receive from the internet.  |  "
            "NORMAL (green): usual traffic.  |  "
            "ATTENTION (yellow): unusually high traffic — check no programs are downloading without permission.  |  "
            "ALERT (red): very high traffic — may indicate an attack or virus sending data."
        ))
        explain.setWordWrap(True)
        explain.setStyleSheet("font-size:11px; color:#8b949e; padding:4px 0;")
        info_lay.addWidget(explain)
        layout.addWidget(info_frame)

        # Panel estado actual — fila de cards
        status_row = QHBoxLayout()
        status_row.setSpacing(12)

        self.card_ip       = self._make_traffic_card(self._txt("IP LOCAL", "LOCAL IP"),
                                                      self.scanner.get_local_ip(), "#a371f7")
        self.card_upload   = self._make_traffic_card(self._txt("SUBIDA", "UPLOAD"),   "0.00 KB/s", "#58a6ff")
        self.card_download = self._make_traffic_card(self._txt("BAJADA", "DOWNLOAD"), "0.00 KB/s", "#3fb950")
        self.card_total    = self._make_traffic_card(self._txt("TOTAL",  "TOTAL"),    "0.00 KB/s", "#e3b341")
        self.card_status   = self._make_traffic_card(self._txt("ESTADO", "STATUS"),
                                                      self._txt("Detenido", "Stopped"), "#484f58")

        for card in (self.card_ip, self.card_upload, self.card_download, self.card_total, self.card_status):
            status_row.addWidget(card)
        layout.addLayout(status_row)

        # Splitter: log | tabla puertos
        from PyQt6.QtWidgets import QSplitter
        mon_splitter = QSplitter(Qt.Orientation.Horizontal)
        mon_splitter.setHandleWidth(2)

        # Log de trafico (izquierda)
        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(0, 0, 4, 0)
        left_l.setSpacing(4)
        lbl_log = QLabel(self._txt("REGISTRO EN TIEMPO REAL", "REAL-TIME LOG"))
        lbl_log.setObjectName("lbl_section")
        left_l.addWidget(lbl_log)
        self.traffic_log = QTextEdit()
        self.traffic_log.setObjectName("console")
        self.traffic_log.setReadOnly(True)
        left_l.addWidget(self.traffic_log, 1)
        mon_splitter.addWidget(left_w)

        # Tabla de puertos abiertos (derecha)
        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.setContentsMargins(4, 0, 0, 0)
        right_l.setSpacing(4)
        lbl_ports_hdr = QLabel(self._txt("PUERTOS ABIERTOS DETECTADOS", "DETECTED OPEN PORTS"))
        lbl_ports_hdr.setObjectName("lbl_section")
        right_l.addWidget(lbl_ports_hdr)

        self.ports_table = QTableWidget(0, 4)
        self.ports_table.setHorizontalHeaderLabels([
            self._txt("IP", "IP"),
            self._txt("Puerto", "Port"),
            self._txt("Servicio", "Service"),
            self._txt("Riesgo", "Risk"),
        ])
        self.ports_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.ports_table.verticalHeader().setVisible(False)
        self.ports_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ports_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right_l.addWidget(self.ports_table, 1)

        lbl_ports_hint = QLabel(self._txt(
            "Se actualiza al completar un escaneo de red.",
            "Updated when a network scan completes."
        ))
        lbl_ports_hint.setStyleSheet("font-size:10px; color:#484f58; padding:2px 0;")
        right_l.addWidget(lbl_ports_hint)
        mon_splitter.addWidget(right_w)

        mon_splitter.setSizes([700, 420])
        layout.addWidget(mon_splitter, 1)

        # Botones
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_monitor = QPushButton(self._txt("INICIAR MONITOREO", "START MONITORING"))
        self.btn_stop    = QPushButton(self._txt("DETENER",           "STOP"))
        self.btn_train_traffic = QPushButton(self._txt("ENTRENAR IA CON TRAFICO ACTUAL", "TRAIN AI WITH CURRENT TRAFFIC"))

        self.btn_monitor.setObjectName("btn_monitor")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)

        btn_row.addWidget(self.btn_monitor)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_train_traffic)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.btn_monitor.clicked.connect(self._start_monitoring)
        self.btn_stop.clicked.connect(self._stop_monitoring)
        self.btn_train_traffic.clicked.connect(self._train_traffic_model)

    def _make_traffic_card(self, label: str, value: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:#161b22; border:1px solid #21262d; "
            f"border-radius:8px; border-top:3px solid {color}; }}"
        )
        vl = QVBoxLayout(frame)
        vl.setContentsMargins(14, 10, 14, 10)
        vl.setSpacing(4)

        lbl_label = QLabel(label)
        lbl_label.setStyleSheet(f"font-size:10px; font-weight:700; color:{color}; letter-spacing:1px;")

        lbl_value = QLabel(value)
        lbl_value.setStyleSheet("font-size:20px; font-weight:700; color:#e6edf3;")
        lbl_value.setObjectName(f"card_val_{label}")

        vl.addWidget(lbl_label)
        vl.addWidget(lbl_value)

        # Guardar ref al valor
        frame._value_label = lbl_value
        return frame

    # ----------------------------------------------------------
    # TAB 3 — ENTRENAMIENTO IA
    # ----------------------------------------------------------

    def _build_training_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Titulo
        lbl_hdr = QLabel(self._txt(
            "ENTRENAR LA IA CON TUS DOCUMENTOS",
            "TRAIN THE AI WITH YOUR DOCUMENTS"
        ))
        lbl_hdr.setObjectName("lbl_section")
        layout.addWidget(lbl_hdr)

        # Explicacion
        info = QLabel(self._txt(
            "Sube documentos PDF, TXT o DOCX sobre redes y seguridad informatica. "
            "La IA aprende de ellos y podra responder preguntas usando ese conocimiento. "
            "El entrenamiento se guarda automaticamente y persiste entre sesiones.\n"
            "IMPORTANTE: Solo se aceptan documentos relacionados con redes, seguridad o ciberseguridad.",
            "Upload PDF, TXT or DOCX documents about networks and computer security. "
            "The AI learns from them and can answer questions using that knowledge. "
            "Training is automatically saved and persists between sessions.\n"
            "IMPORTANT: Only documents related to networks, security or cybersecurity are accepted."
        ))
        info.setWordWrap(True)
        info.setStyleSheet(
            "font-size:11px; color:#8b949e; background:#161b22; "
            "border:1px solid #21262d; border-radius:6px; padding:10px;"
        )
        layout.addWidget(info)

        # Zona de accion
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.btn_upload_doc = QPushButton(self._txt(
            "SUBIR DOCUMENTO (PDF / TXT / DOCX)",
            "UPLOAD DOCUMENT (PDF / TXT / DOCX)"
        ))
        self.btn_upload_doc.setObjectName("btn_upload")
        self.btn_upload_doc.clicked.connect(self._upload_document)
        action_row.addWidget(self.btn_upload_doc)

        self.btn_remove_doc = QPushButton(self._txt("ELIMINAR SELECCIONADO", "REMOVE SELECTED"))
        self.btn_remove_doc.setObjectName("btn_remove")
        self.btn_remove_doc.clicked.connect(self._remove_selected_doc)
        action_row.addWidget(self.btn_remove_doc)

        action_row.addStretch()
        layout.addLayout(action_row)

        # Tabla de documentos
        self.doc_table = QTableWidget(0, 4)
        headers = [
            self._txt("Documento",  "Document"),
            self._txt("Fecha",      "Date"),
            self._txt("Tamano",     "Size"),
            self._txt("Relevancia", "Relevance"),
        ]
        self.doc_table.setHorizontalHeaderLabels(headers)
        self.doc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.doc_table.verticalHeader().setVisible(False)
        self.doc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.doc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.doc_table.setFixedHeight(200)
        layout.addWidget(self.doc_table)

        # Log de entrenamiento
        lbl_log = QLabel(self._txt("REGISTRO DE ENTRENAMIENTO", "TRAINING LOG"))
        lbl_log.setObjectName("lbl_section")
        layout.addWidget(lbl_log)

        self.doc_log = QTextEdit()
        self.doc_log.setObjectName("doc_log")
        self.doc_log.setReadOnly(True)
        layout.addWidget(self.doc_log, 1)

        # Estado del modelo de trafico
        traffic_frame = QFrame()
        traffic_frame.setStyleSheet(
            "QFrame { background:#161b22; border:1px solid #21262d; border-radius:6px; padding:4px; }"
        )
        tf_lay = QHBoxLayout(traffic_frame)
        tf_lay.setContentsMargins(12, 6, 12, 6)

        lbl_traf = QLabel(self._txt(
            "Modelo de deteccion de anomalias de trafico:",
            "Traffic anomaly detection model:"
        ))
        lbl_traf.setStyleSheet("font-size:11px; color:#8b949e;")
        tf_lay.addWidget(lbl_traf)

        self.lbl_traffic_model = QLabel(self._txt(
            "No entrenado — Inicia el monitoreo para recolectar muestras, luego entrena",
            "Not trained — Start monitoring to collect samples, then train"
        ))
        self.lbl_traffic_model.setStyleSheet("font-size:11px; color:#e3b341;")
        tf_lay.addWidget(self.lbl_traffic_model)
        tf_lay.addStretch()

        self.btn_train_here = QPushButton(self._txt("ENTRENAR AHORA", "TRAIN NOW"))
        self.btn_train_here.clicked.connect(self._train_traffic_model)
        tf_lay.addWidget(self.btn_train_here)

        layout.addWidget(traffic_frame)

        # Refrescar tabla
        self._refresh_doc_table()

        # Log inicial
        if self.anomaly_detector.is_trained:
            stats = self.anomaly_detector.get_stats()
            self._doc_log(self._txt(
                f"Modelo de trafico cargado: {stats.get('samples','?')} muestras, "
                f"entrenado el {stats.get('trained_at','?')[:10]}",
                f"Traffic model loaded: {stats.get('samples','?')} samples, "
                f"trained on {stats.get('trained_at','?')[:10]}"
            ), "#3fb950")

        n_docs = len(self.doc_trainer.documents)
        if n_docs:
            self._doc_log(self._txt(
                f"{n_docs} documento(s) cargado(s) de la sesion anterior.",
                f"{n_docs} document(s) loaded from previous session."
            ), "#3fb950")

    # ==========================================================
    # CONSOLA DE ANALISIS
    # ==========================================================

    def _con(self, text, color="#c9d1d9", bold=False):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.console.setTextCursor(cursor)
        safe = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        tag = f"<b>{safe}</b>" if bold else safe
        self.console.insertHtml(f"<font color='{color}'>{tag}</font><br>")
        self.console.ensureCursorVisible()

    def _con_cmd(self, cmd):
        self._con(f"$ {cmd}", "#e3b341", bold=True)
        self.lbl_cmd.setText(f"$ {cmd}")
        self.lbl_cmd.show()

    def _con_sep(self, title=""):
        self._con("─" * 58, "#30363d")
        if title:
            self._con(f"  {title}", "#58a6ff", bold=True)

    def _show_welcome(self):
        self._con_sep(self._txt(
            "NETGUARD  Sistema de Seguridad de Red con IA Local",
            "NETGUARD  Network Security System with Local AI"
        ))
        self._con(f"  IP: {self.scanner.get_local_ip()}  |  "
                  f"{self._txt('Rango','Range')}: {self.scanner.get_network_range()}",
                  "#58a6ff")
        self._con("─" * 58, "#30363d")
        self._con("  " + self._txt(
            "Presiona ESCANEAR para iniciar el analisis de tu red.",
            "Press SCAN to start your network analysis."
        ), "#8b949e")
        self._con("")

    # ==========================================================
    # LOG DE TRAFICO
    # ==========================================================

    def _tlog(self, text, color="#c9d1d9", bold=False):
        cursor = self.traffic_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.traffic_log.setTextCursor(cursor)
        safe = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        tag = f"<b>{safe}</b>" if bold else safe
        self.traffic_log.insertHtml(f"<font color='{color}'>{tag}</font><br>")
        self.traffic_log.ensureCursorVisible()

    # ==========================================================
    # LOG DE DOCUMENTOS
    # ==========================================================

    def _doc_log(self, text, color="#c9d1d9"):
        cursor = self.doc_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.doc_log.setTextCursor(cursor)
        safe = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        self.doc_log.insertHtml(f"<font color='{color}'>{safe}</font><br>")
        self.doc_log.ensureCursorVisible()

    # ==========================================================
    # SCANNER CALLBACKS
    # ==========================================================

    def _on_scanner_raw(self, message: str):
        self._scanner_msg.emit(message)

    def _display_scanner_msg(self, message: str):
        msg = message.strip()
        if not msg: return
        if any(x in msg for x in ("Encontrado", "completado", "encontrado")):
            color = "#3fb950"
            ips = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', msg)
            for ip in ips:
                if ip not in self.scanned_ips:
                    self.scanned_ips.add(ip)
                    self.lbl_devices.setText(
                        self._txt(f"Dispositivos: {len(self.scanned_ips)}",
                                  f"Devices: {len(self.scanned_ips)}")
                    )
        elif any(x in msg for x in ("Error","error","❌")):
            color = "#f85149"
        elif any(x in msg for x in ("ADVERTENCIA","Warning","⚠")):
            color = "#e3b341"
        elif "Escaneando" in msg or "Scanning" in msg:
            color = "#58a6ff"
            ips = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', msg)
            if ips: self.lbl_scanning.setText(f"-> {ips[0]}")
        elif "Puerto" in msg and ("abierto" in msg or "open" in msg):
            color = "#e3b341"
            self.total_ports_found += 1
            self.lbl_ports.setText(
                self._txt(f"Puertos: {self.total_ports_found}",
                          f"Ports: {self.total_ports_found}")
            )
        else:
            color = "#8b949e"
        self._con(msg, color)

    # ==========================================================
    # ESCANEO
    # ==========================================================

    def _run_scan(self):
        self.console.clear()
        self.scan_results      = []
        self.scanned_ips       = set()
        self.total_ports_found = 0
        self._devices_to_scan    = []
        self._devices_scanned    = 0
        self._port_threads       = []
        self._port_workers       = []
        self._port_threads_alive = []
        self._host_thread_alive  = False
        self.scan_active         = True
        self.lbl_devices.setText(self._txt("Dispositivos: 0", "Devices: 0"))
        self.lbl_ports.setText(self._txt("Puertos: 0",    "Ports: 0"))
        self.lbl_scanning.setText("")

        self._con_sep(self._txt("ANALISIS DE VULNERABILIDADES", "VULNERABILITY ANALYSIS"))
        self._con_cmd(f"nmap -sn -T4 {self.scanner.get_network_range()}")
        self._con("")

        self._set_controls(scanning=True)
        self.lbl_status.setText(self._txt("ESCANEANDO", "SCANNING"))
        self.lbl_status.setStyleSheet("QLabel#lbl_info { color:#e3b341; }")
        self.progress.show()

        self._host_thread = QThread()
        self._host_worker = ScanHostsWorker(self.scanner)
        self._host_worker.moveToThread(self._host_thread)
        self._host_thread.started.connect(self._host_worker.run)
        self._host_worker.device_found.connect(self._on_device_found)
        self._host_worker.finished.connect(self._on_hosts_finished)
        self._host_worker.error.connect(lambda m: self._con(m, "#f85149"))
        self._host_worker.finished.connect(self._host_thread.quit)
        # Marcar alive con flag Python — nunca llamar isRunning() sobre un objeto
        # que pudo haber sido destruido por Qt tras quit()+event loop
        self._host_thread_alive = True
        self._host_thread.finished.connect(lambda: setattr(self, '_host_thread_alive', False))
        self._host_thread.start()

    def _on_device_found(self, device):
        ip = device["ip"]
        if ip not in self.scanned_ips:
            self.scanned_ips.add(ip)
            self.lbl_devices.setText(
                self._txt(f"Dispositivos: {len(self.scanned_ips)}",
                          f"Devices: {len(self.scanned_ips)}")
            )

    def _on_hosts_finished(self, devices):
        if not self.scan_active: return
        if not devices:
            self._con(self._txt(
                "No se encontraron dispositivos en la red.",
                "No devices found on the network."
            ), "#f85149")
            self._finish_scan(); return

        self._con("")
        self._con(self._txt(
            f"  {len(devices)} dispositivo(s) encontrado(s). Analizando puertos...",
            f"  {len(devices)} device(s) found. Analyzing ports..."
        ), "#3fb950", bold=True)
        self._con("")
        self._devices_to_scan = devices
        self._devices_scanned = 0
        for device in devices:
            self._scan_device_ports(device)

    def _scan_device_ports(self, device):
        if not self.scan_active: return
        self._con_cmd(f"nmap -F -T4 {device['ip']}")

        thread = QThread()
        worker = ScanPortsWorker(self.scanner)
        # Referencias fuertes para evitar GC mientras el hilo corre
        self._port_threads.append(thread)
        self._port_workers.append(worker)
        # Flag Python por índice — evita llamar .isRunning() sobre C++ potencialmente destruido
        idx = len(self._port_threads_alive)
        self._port_threads_alive.append(True)
        thread.finished.connect(lambda i=idx: self._port_threads_alive.__setitem__(i, False))

        worker.moveToThread(thread)
        thread.started.connect(lambda: worker.scan_single_device(device["ip"], device["hostname"]))
        worker.finished.connect(self._on_ports_finished)
        worker.error.connect(lambda m: self._con(m, "#f85149"))
        worker.finished.connect(thread.quit)
        thread.start()

    def _on_ports_finished(self, ip, ports, classified, score, hostname):
        # Always called in the main thread via Qt queued connection — no mutex needed.
        if not self.scan_active: return
        self.scan_results.append({
            "ip": ip, "hostname": hostname,
            "ports": ports, "classified": classified, "score": score
        })
        self._devices_scanned += 1
        if self._devices_scanned >= len(self._devices_to_scan):
            self._show_results()

    def _show_results(self):
        if not self.scan_active: return
        self.scan_active = False

        self._con("")
        self._con_sep(self._txt("ANALISIS DE IA LOCAL", "LOCAL AI ANALYSIS"))
        self._con("  " + self._txt("Procesando resultados...", "Processing results..."), "#58a6ff")

        report = self.vuln_analyzer.analyze(self.scan_results)
        self._last_report = report
        self.chatbot.set_scan_report(report, self.scan_results)

        self._con("")
        self._con_sep(self._txt("RESULTADOS", "RESULTS"))

        s    = report["summary"]
        risk = report["overall_risk"]
        rc   = RISK_COLOR.get(risk, "#c9d1d9")

        # Mostrar nivel de riesgo con explicacion clara
        risk_explain = {
            "es": {
                "CRITICO": "CRITICO — Tu red tiene vulnerabilidades graves que pueden ser explotadas AHORA",
                "ALTO":    "ALTO — Hay problemas serios que debes corregir pronto",
                "MEDIO":   "MEDIO — Hay puntos a mejorar pero no son urgentes",
                "BAJO":    "BAJO — Tu red esta bien configurada",
            },
            "en": {
                "CRITICO": "CRITICAL — Your network has serious vulnerabilities that can be exploited NOW",
                "ALTO":    "HIGH — There are serious issues you should fix soon",
                "MEDIO":   "MEDIUM — There are areas to improve but not urgent",
                "BAJO":    "LOW — Your network is well configured",
            }
        }
        lang = SYSTEM_LANG if SYSTEM_LANG in ("es","en") else "es"
        self._con(f"  {risk_explain[lang].get(risk, risk)}", rc, bold=True)
        self._con("")
        self._con(f"  {self._txt('Dispositivos analizados','Devices analyzed')}: {s['total_devices']}", "#c9d1d9")
        self._con(f"  {self._txt('Puertos abiertos','Open ports')}: {s['total_ports']}", "#c9d1d9")
        if s['critical_ports']:
            self._con(f"  {self._txt('Puertos CRITICOS','CRITICAL ports')}: {s['critical_ports']} "
                      f"— {self._txt('requieren accion INMEDIATA','require IMMEDIATE action')}",
                      "#ff4444", bold=True)
        if s['high_ports']:
            self._con(f"  {self._txt('Puertos de ALTO riesgo','HIGH risk ports')}: {s['high_ports']}",
                      "#f85149")
        if s['dangerous_combos']:
            self._con(f"  {self._txt('Combinaciones peligrosas','Dangerous combinations')}: {s['dangerous_combos']} "
                      f"— {self._txt('ver detalles abajo','see details below')}",
                      "#ff4444", bold=True)
        self._con("")

        # Detalles por dispositivo
        for dev in report["devices"]:
            self._con(f"  {dev['ip']}  ({dev['hostname']})", "#58a6ff", bold=True)

            # Combos primero (mas importantes)
            for combo in dev.get("combos", []):
                cc = RISK_COLOR.get(combo["severity"], "#e3b341")
                self._con(f"  [PELIGRO] {combo['name']}", cc, bold=True)
                self._con(f"  {combo['plain']}", cc)
                self._con(f"  {self._txt('Que hacer','What to do')}: {combo['action']}", "#8b949e")
                self._con("")

            # Puertos con explicacion clara
            for f in dev.get("findings", []):
                risk_f = f.get("risk", "MEDIO")
                color  = RISK_COLOR.get(risk_f, "#c9d1d9")
                icons  = {"CRITICO":"[!!!]","ALTO":"[!!]","MEDIO":"[!]","BAJO":"[OK]"}
                icon   = icons.get(risk_f, "[ ]")

                self._con(
                    f"  {icon} Puerto {f['port']}  —  {f.get('service_name', f.get('service','?'))}  [{risk_f}]",
                    color, bold=(risk_f == "CRITICO")
                )
                # Explicacion en lenguaje claro
                if f.get("plain_risk"):
                    self._con(f"      {self._txt('Que significa','What it means')}: {f['plain_risk']}", "#8b949e")
                if f.get("plain_action"):
                    self._con(f"      {self._txt('Que hacer','What to do')}: {f['plain_action']}", "#6e7681")

            if not dev["findings"]:
                self._con(f"  {self._txt('Sin puertos abiertos detectados','No open ports detected')}", "#3fb950")
            self._con("")

        # Plan de accion
        plan = report.get("action_plan", [])
        if plan:
            self._con_sep(self._txt("PLAN DE ACCION PRIORITARIO", "PRIORITY ACTION PLAN"))
            for item in plan[:6]:
                urg_color = {
                    "INMEDIATA": "#ff4444", "HOY": "#f85149", "ESTA SEMANA": "#e3b341",
                    "IMMEDIATE": "#ff4444", "TODAY": "#f85149", "THIS WEEK": "#e3b341",
                }.get(item["urgency"], "#c9d1d9")
                self._con(
                    f"  [{item['urgency']}] {item['priority']}. {item['action']}",
                    urg_color
                )
            self._con("")

        # Notificar al chat
        self._chat_sys(self._txt(
            f"Analisis completado. Nivel de riesgo: {risk} | "
            f"{s['total_devices']} dispositivos | {s['total_ports']} puertos | "
            f"{s['critical_ports']} criticos.\n\n"
            "Usa los botones de abajo o escribe una pregunta. Te explico todo en lenguaje claro.",
            f"Analysis complete. Risk level: {risk} | "
            f"{s['total_devices']} devices | {s['total_ports']} ports | "
            f"{s['critical_ports']} critical.\n\n"
            "Use the buttons below or type a question. I'll explain everything in plain language."
        ))
        self._refresh_ports_table()
        self._finish_scan()

    def _refresh_ports_table(self):
        """Rellena la tabla de puertos abiertos en el monitor con los resultados del último escaneo."""
        if not hasattr(self, 'ports_table'):
            return
        RISK_COLOR_TABLE = {
            "CRITICO": "#ff4444",
            "ALTO":    "#f85149",
            "MEDIO":   "#e3b341",
            "BAJO":    "#3fb950",
        }
        self.ports_table.setRowCount(0)
        for dev in self.scan_results:
            ip = dev.get("ip", "?")
            for entry in dev.get("classified", []):
                row = self.ports_table.rowCount()
                self.ports_table.insertRow(row)
                self.ports_table.setItem(row, 0, QTableWidgetItem(ip))
                self.ports_table.setItem(row, 1, QTableWidgetItem(str(entry["port"])))
                self.ports_table.setItem(row, 2, QTableWidgetItem(entry.get("service", f"Puerto {entry['port']}")))
                risk = entry.get("risk", "MEDIO")
                risk_item = QTableWidgetItem(risk)
                risk_item.setForeground(QColor(RISK_COLOR_TABLE.get(risk, "#c9d1d9")))
                self.ports_table.setItem(row, 3, risk_item)
        # Actualizar IP card con la IP actual (puede haber cambiado)
        if hasattr(self, 'card_ip'):
            self.card_ip._value_label.setText(self.scanner.get_local_ip())

    def _finish_scan(self):
        self.scan_active = False
        self.progress.hide()
        self.lbl_cmd.hide()
        self.lbl_scanning.setText("")
        self.lbl_status.setText(self._txt("COMPLETADO", "COMPLETED"))
        self.lbl_status.setStyleSheet("QLabel#lbl_info { color:#3fb950; }")
        self._set_controls(scanning=False, monitoring=self.monitoring_active)

    def _cancel_scan(self):
        if not self.scan_active: return
        self.scan_active = False
        if hasattr(self, "_host_worker"):
            self._host_worker.cancel()
        self._con(self._txt("Escaneo cancelado.", "Scan cancelled."), "#e3b341", bold=True)
        self._finish_scan()

    # ==========================================================
    # MONITOREO
    # ==========================================================

    def _start_monitoring(self):
        if self.monitoring_active: return
        self._tlog(self._txt(
            "Monitoreo iniciado. Los datos se muestran cada 2 segundos.",
            "Monitoring started. Data is shown every 2 seconds."
        ), "#3fb950", bold=True)
        self._tlog(self._txt(
            "Verde = Normal | Amarillo = Atencion | Rojo = Alerta",
            "Green = Normal | Yellow = Attention | Red = Alert"
        ), "#8b949e")
        self._tlog("")
        self.monitoring_active = True
        self.btn_monitor.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText(self._txt("MONITOREANDO", "MONITORING"))
        self.lbl_status.setStyleSheet("QLabel#lbl_info { color:#58a6ff; }")
        self.card_status._value_label.setText(self._txt("Activo", "Active"))
        self.monitor.initialize()
        self.timer.start(2000)

    def _stop_monitoring(self):
        if not self.monitoring_active: return
        self.timer.stop()
        self.monitoring_active = False
        self.btn_monitor.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._tlog(self._txt("Monitoreo detenido.", "Monitoring stopped."), "#e3b341")
        self.lbl_status.setText(self._txt("LISTO", "READY"))
        self.lbl_status.setStyleSheet("QLabel#lbl_info { color:#8b949e; }")
        self.card_status._value_label.setText(self._txt("Detenido", "Stopped"))

    def _update_traffic(self):
        t_data = self.monitor.get_traffic()
        self.traffic_history.append([t_data["upload_kb"], t_data["download_kb"]])
        if len(self.traffic_history) > 1000:
            self.traffic_history = self.traffic_history[-1000:]

        base_risk = self.monitor.evaluate_risk(t_data["upload_kb"], t_data["download_kb"])

        if self.anomaly_detector.is_trained:
            result  = self.anomaly_detector.predict(t_data["upload_kb"], t_data["download_kb"])
            label   = result["label"]
            sev     = result["severity"]
            reasons = result["reasons"]
        else:
            label   = "ANOMALIA" if base_risk in ("ALTO",) else "NORMAL"
            sev     = base_risk
            reasons = [self._txt(
                f"Trafico {base_risk} sin modelo entrenado",
                f"{base_risk} traffic without trained model"
            )] if label == "ANOMALIA" else []

        col = RISK_COLOR.get(sev if label == "ANOMALIA" else base_risk, "#c9d1d9")

        # Actualizar cards
        self.card_upload._value_label.setText(f"{t_data['upload_kb']:.1f} KB/s")
        self.card_download._value_label.setText(f"{t_data['download_kb']:.1f} KB/s")
        self.card_total._value_label.setText(f"{t_data['total_kb']:.1f} KB/s")

        # Descripcion del estado en lenguaje claro
        status_texts = {
            "es": {
                "BAJO":   "Normal",
                "MEDIO":  "Atencion",
                "ALTO":   "Alerta",
                "CRITICO":"Critico",
            },
            "en": {
                "BAJO":   "Normal",
                "MEDIO":  "Attention",
                "ALTO":   "Alert",
                "CRITICO":"Critical",
            }
        }
        lang_key = SYSTEM_LANG if SYSTEM_LANG in ("es","en") else "es"
        status_txt = status_texts[lang_key].get(base_risk, base_risk)
        self.card_status._value_label.setText(status_txt)
        self.card_status._value_label.setStyleSheet(f"font-size:20px; font-weight:700; color:{col};")

        # Log de trafico con explicacion
        if label == "ANOMALIA":
            prefix = self._txt("[ANOMALIA]", "[ANOMALY]")
            self._tlog(
                f"  {prefix} {self._txt('Subida','Upload')}: {t_data['upload_kb']:7.1f} KB/s  "
                f"{self._txt('Bajada','Download')}: {t_data['download_kb']:7.1f} KB/s  "
                f"{self._txt('Total','Total')}: {t_data['total_kb']:7.1f} KB/s",
                col, bold=True
            )
            for r in reasons:
                self._tlog(f"    {self._txt('Detalle','Detail')}: {r}", "#f85149")
            # Avisar al chat
            self._chat_sys(
                self._txt("Anomalia de trafico detectada:\n","Traffic anomaly detected:\n") +
                "\n".join(f"  - {r}" for r in reasons)
            )
        else:
            level_explain = {
                "es": {
                    "BAJO":  "(Normal — trafico habitual)",
                    "MEDIO": "(Atencion — trafico algo alto, verifica si hay descargas en curso)",
                    "ALTO":  "(ALERTA — trafico muy alto, verifica actividad en la red)",
                },
                "en": {
                    "BAJO":  "(Normal — usual traffic)",
                    "MEDIO": "(Attention — traffic somewhat high, check if downloads are in progress)",
                    "ALTO":  "(ALERT — very high traffic, check network activity)",
                }
            }
            explain = level_explain[lang_key].get(base_risk, "")
            self._tlog(
                f"  {self._txt('Subida','Upload')}: {t_data['upload_kb']:7.1f} KB/s  "
                f"{self._txt('Bajada','Download')}: {t_data['download_kb']:7.1f} KB/s  "
                f"{self._txt('Total','Total')}: {t_data['total_kb']:7.1f} KB/s  {explain}",
                col
            )

    # ==========================================================
    # ENTRENAMIENTO MODELO DE TRAFICO
    # ==========================================================

    def _train_traffic_model(self):
        n = len(self.traffic_history)
        if n < 10:
            msg = self._txt(
                f"Necesitas al menos 10 muestras de trafico ({n} disponibles). "
                "Inicia el monitoreo de trafico primero.",
                f"You need at least 10 traffic samples ({n} available). "
                "Start traffic monitoring first."
            )
            self._con(msg, "#e3b341")
            self._doc_log(msg, "#e3b341")
            return

        msg_start = self._txt(
            "Entrenando modelo de deteccion de anomalias...",
            "Training anomaly detection model..."
        )
        self._con(msg_start, "#58a6ff")
        self._doc_log(msg_start, "#58a6ff")
        QApplication.processEvents()

        ok = self.anomaly_detector.train(self.traffic_history)

        if ok:
            stats = self.anomaly_detector.get_stats()
            msg_ok = self._txt(
                f"Modelo entrenado y GUARDADO con {n} muestras. "
                f"Se cargara automaticamente la proxima vez.",
                f"Model trained and SAVED with {n} samples. "
                f"It will load automatically next time."
            )
            self._con(msg_ok, "#3fb950", bold=True)
            self._doc_log(msg_ok, "#3fb950")
            trained_lbl = self._txt(f"IA: entrenada ({n} muestras)", f"AI: trained ({n} samples)")
            self.lbl_ai_status.setText(trained_lbl)
            self.lbl_ai_status.setStyleSheet("QLabel#lbl_info { color:#3fb950; }")
            self.lbl_traffic_model.setText(
                self._txt(
                    f"Entrenado — {n} muestras | "
                    f"Upload media: {stats.get('upload_mean','?')} KB/s | "
                    f"Download media: {stats.get('download_mean','?')} KB/s",
                    f"Trained — {n} samples | "
                    f"Upload avg: {stats.get('upload_mean','?')} KB/s | "
                    f"Download avg: {stats.get('download_mean','?')} KB/s"
                )
            )
            self.lbl_traffic_model.setStyleSheet("font-size:11px; color:#3fb950;")
        else:
            msg_fail = self._txt(
                "Error al entrenar. Verifica que sklearn este instalado: pip install scikit-learn",
                "Training error. Check sklearn is installed: pip install scikit-learn"
            )
            self._con(msg_fail, "#f85149")
            self._doc_log(msg_fail, "#f85149")

    # ==========================================================
    # GESTION DE DOCUMENTOS
    # ==========================================================

    def _upload_document(self):
        filters = "Documentos (*.pdf *.txt *.docx);;PDF (*.pdf);;Texto (*.txt);;Word (*.docx)"
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            self._txt("Seleccionar documento de seguridad/redes",
                      "Select security/network document"),
            "",
            filters
        )
        if not filepath:
            return

        fname = os.path.basename(filepath)
        self._doc_log(self._txt(
            f"Procesando: {fname}...",
            f"Processing: {fname}..."
        ), "#58a6ff")
        QApplication.processEvents()

        success, message = self.doc_trainer.add_document(filepath)

        if success:
            self._doc_log(f"OK: {message}", "#3fb950")
            self._refresh_doc_table()
            # Informar al chatbot
            self._chat_sys(self._txt(
                f"Nuevo documento agregado a mi conocimiento: {fname}\n"
                "Ahora puedo responder preguntas usando la informacion de ese documento.",
                f"New document added to my knowledge: {fname}\n"
                "I can now answer questions using the information from that document."
            ))
        else:
            self._doc_log(self._txt(f"RECHAZADO: {message}", f"REJECTED: {message}"), "#f85149")
            # Mostrar mensaje al usuario
            if SYSTEM_LANG == "es":
                detail = (
                    "El documento fue rechazado porque no contiene suficiente informacion "
                    "relacionada con redes o seguridad informatica.\n\n"
                    f"Motivo: {message}"
                )
            else:
                detail = (
                    "The document was rejected because it does not contain enough information "
                    "related to networks or computer security.\n\n"
                    f"Reason: {message}"
                )
            QMessageBox.warning(
                self,
                self._txt("Documento rechazado", "Document rejected"),
                detail
            )

    def _remove_selected_doc(self):
        row = self.doc_table.currentRow()
        if row < 0:
            return
        fname = self.doc_table.item(row, 0).text()
        ok = self.doc_trainer.remove_document(fname)
        if ok:
            self._doc_log(self._txt(
                f"Documento eliminado: {fname}",
                f"Document removed: {fname}"
            ), "#e3b341")
            self._refresh_doc_table()

    def _refresh_doc_table(self):
        docs = self.doc_trainer.list_documents()
        self.doc_table.setRowCount(0)
        for doc in docs:
            row = self.doc_table.rowCount()
            self.doc_table.insertRow(row)
            self.doc_table.setItem(row, 0, QTableWidgetItem(doc["filename"]))
            self.doc_table.setItem(row, 1, QTableWidgetItem(doc["date"]))
            self.doc_table.setItem(row, 2, QTableWidgetItem(f"{doc['chars']:,} chars"))
            self.doc_table.setItem(row, 3, QTableWidgetItem(f"{doc['score']*100:.1f}%"))

    # ==========================================================
    # CHAT IA
    # ==========================================================

    def _chat_append(self, role: str, text: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)

        formatted = re.sub(
            r'\*\*(.+?)\*\*', r'<b>\1</b>',
            text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                .replace("\n","<br>")
        )

        if role == "user":
            label = self._txt("Tú", "You")
            self.chat_display.insertHtml(
                f"<div style='margin:10px 0 2px 0;'>"
                f"<span style='color:#58a6ff; font-weight:700; font-size:11px;'>{label}</span>"
                f"</div>"
                f"<div style='margin:0 0 8px 12px; color:#c9d1d9; font-size:11px;'>{formatted}</div>"
            )
        elif role == "assistant":
            label = self._txt("IA Local", "Local AI")
            self.chat_display.insertHtml(
                f"<div style='margin:10px 0 2px 0;'>"
                f"<span style='color:#3fb950; font-weight:700; font-size:11px;'>{label}</span>"
                f"</div>"
                f"<div style='margin:0 0 8px 12px; padding:8px 12px; "
                f"background:#1c2128; border-left:3px solid #238636; border-radius:4px; "
                f"color:#c9d1d9; font-size:11px;'>{formatted}</div>"
            )
        else:
            # mensajes de sistema: solo texto gris, sin etiqueta
            self.chat_display.insertHtml(
                f"<div style='margin:4px 0 4px 0; color:#8b949e; "
                f"font-style:italic; font-size:10px;'>{formatted}</div>"
            )
        self.chat_display.ensureCursorVisible()

    def _chat_sys(self, text: str):
        self._chat_append("sistema", text)

    def _on_chat_send(self):
        msg = self.chat_input.text().strip()
        if not msg: return
        self.chat_input.clear()
        self._chat_append("user", msg)
        self._send_to_chat(msg)

    def _send_to_chat(self, msg: str):
        response = self.chatbot.ask(msg)
        self._chat_append("assistant", response)

    # ==========================================================
    # CONTROLES
    # ==========================================================

    def _set_controls(self, scanning=False, monitoring=False):
        self.btn_scan.setEnabled(not scanning)
        self.btn_cancel.setEnabled(scanning)
        self.btn_train.setEnabled(not scanning)

    def _clear_output(self):
        self.console.clear()
        self._show_welcome()
        self.lbl_status.setText(self._txt("LISTO","READY"))
        self.lbl_status.setStyleSheet("QLabel#lbl_info { color:#8b949e; }")
        self.lbl_devices.setText(self._txt("Dispositivos: 0","Devices: 0"))
        self.lbl_ports.setText(self._txt("Puertos: 0","Ports: 0"))

    def closeEvent(self, event):
        # ── 1. Señalizar a todo el código que debe parar ──────────────
        self.scan_active    = False
        self.monitoring_active = False

        # ── 2. Detener timer de monitoreo ─────────────────────────────
        try:
            self.timer.stop()
        except Exception:
            pass

        # ── 3. Cancelar workers (sólo marcan su flag interno, no tocan C++) ──
        try:
            if hasattr(self, "_host_worker"):
                self._host_worker.cancel()
        except Exception:
            pass

        for w in getattr(self, "_port_workers", []):
            try:
                w.cancel()
            except Exception:
                pass

        # ── 4. Esperar port threads usando flag Python ─────────────────
        # NUNCA llamar .isRunning() aquí: el objeto C++ puede haber sido
        # destruido por Qt tras quit()+event loop → RuntimeError/IOT.
        # En cambio usamos la lista _port_threads_alive que actualizamos
        # con thread.finished en el momento en que el hilo termina.
        for i, t in enumerate(getattr(self, "_port_threads", [])):
            alive = getattr(self, "_port_threads_alive", [])
            if i < len(alive) and alive[i]:
                try:
                    t.quit()
                    t.wait(1000)
                except RuntimeError:
                    pass

        # ── 5. Esperar host thread usando flag Python ──────────────────
        if getattr(self, "_host_thread_alive", False):
            try:
                self._host_thread.quit()
                self._host_thread.wait(1500)
            except RuntimeError:
                pass

        event.accept()