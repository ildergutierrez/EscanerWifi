#!/usr/bin/env python3
import os
import time
import json
import signal
import argparse
import logging
from datetime import datetime
from threading import Thread, Event, Lock
from scapy.all import sniff, PcapWriter, get_if_list
from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.layers.l2 import Ether
import psutil   # pip install psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


class WindowsPacketCollector:
    def __init__(self, iface, out_dir="captures", rotate_seconds=300, max_files=48, metadata=True):
        self.iface = iface
        self.out_dir = out_dir
        self.rotate_seconds = int(rotate_seconds)
        self.max_files = int(max_files)
        self.metadata_enabled = metadata

        os.makedirs(self.out_dir, exist_ok=True)

        self._stop_event = Event()
        self._pcap_writer = None
        self._meta_f = None
        self._file_start = 0
        self._rotation_thread = None
        self._sniff_thread = None
        self._lock = Lock()

    def _timestamp_str(self):
        return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    def _open_new_files(self):
        with self._lock:
            self._close_files()
            ts = self._timestamp_str()
            base = f"capture_{ts}"
            pcap_path = os.path.join(self.out_dir, f"{base}.pcap")
            meta_path = os.path.join(self.out_dir, f"{base}.jsonl")

            logging.info("Creating pcap: %s", pcap_path)
            self._pcap_writer = PcapWriter(pcap_path, append=False, sync=True)
            if self.metadata_enabled:
                self._meta_f = open(meta_path, "a", encoding="utf-8")
            self._file_start = time.time()
            self._enforce_max_files()

    def _close_files(self):
        try:
            if self._pcap_writer:
                self._pcap_writer.close()
                self._pcap_writer = None
        except Exception:
            logging.exception("Error closing pcap writer")
        try:
            if self._meta_f:
                self._meta_f.close()
                self._meta_f = None
        except Exception:
            logging.exception("Error closing metadata file")

    def _enforce_max_files(self):
        files = sorted([f for f in os.listdir(self.out_dir) if f.startswith("capture_")])
        if len(files) > self.max_files * 2:
            to_remove = len(files) - (self.max_files * 2)
            logging.info("Pruning %d old files", to_remove)
            for i in range(to_remove):
                fpath = os.path.join(self.out_dir, files[i])
                try:
                    os.remove(fpath)
                except Exception:
                    logging.exception("Removing old file failed: %s", fpath)

    def _extract_meta_ip(self, pkt):
        meta = {}
        try:
            meta["ts"] = datetime.utcfromtimestamp(pkt.time).isoformat() + "Z"
            meta["len"] = len(pkt)
            meta["iface"] = self.iface

            if pkt.haslayer(Ether):
                eth = pkt.getlayer(Ether)
                meta["src_mac"] = (eth.src or "").upper()
                meta["dst_mac"] = (eth.dst or "").upper()

            if pkt.haslayer(IP):
                ip = pkt.getlayer(IP)
                meta["src_ip"] = ip.src
                meta["dst_ip"] = ip.dst
                meta["ip_proto"] = int(ip.proto) if ip.proto is not None else None

                if pkt.haslayer(TCP):
                    tcp = pkt.getlayer(TCP)
                    meta["src_port"] = int(tcp.sport)
                    meta["dst_port"] = int(tcp.dport)
                    meta["l4"] = "TCP"
                elif pkt.haslayer(UDP):
                    udp = pkt.getlayer(UDP)
                    meta["src_port"] = int(udp.sport)
                    meta["dst_port"] = int(udp.dport)
                    meta["l4"] = "UDP"
                elif pkt.haslayer(ICMP):
                    meta["l4"] = "ICMP"
                else:
                    meta["l4"] = "OTHER"
            else:
                meta["note"] = "non-ip"
            return meta
        except Exception:
            logging.exception("Failed to extract meta")
            return meta

    def _handle_pkt(self, pkt):
        with self._lock:
            try:
                if self._pcap_writer:
                    self._pcap_writer.write(pkt)
            except Exception:
                logging.exception("Error writing packet to pcap")

            if self.metadata_enabled:
                try:
                    meta = self._extract_meta_ip(pkt)
                    self._meta_f.write(json.dumps(meta, default=str) + "\n")
                except Exception:
                    logging.exception("Error writing metadata")

    def _rotation_worker(self):
        while not self._stop_event.is_set():
            elapsed = time.time() - self._file_start if self._file_start else None
            if (elapsed is None) or (elapsed >= self.rotate_seconds):
                self._open_new_files()
            time.sleep(1)

    def _sniff_worker(self):
        logging.info("Sniffing on iface %s ...", self.iface)
        try:
            # En Windows sin WinPcap API solo podemos capturar a nivel IP
            sniff(
                iface=self.iface,
                prn=self._handle_pkt,
                store=False,
                filter="ip",  # asegura solo tráfico IP
                stop_filter=lambda x: self._stop_event.is_set()
            )
        except Exception as e:
            logging.exception("Sniffer error: %s", e)
            self.stop()

    def start(self):
        self._open_new_files()
        self._stop_event.clear()
        self._rotation_thread = Thread(target=self._rotation_worker, daemon=True)
        self._rotation_thread.start()
        self._sniff_thread = Thread(target=self._sniff_worker, daemon=True)
        self._sniff_thread.start()

    def stop(self):
        logging.info("Stopping collector...")
        self._stop_event.set()
        if self._sniff_thread:
            self._sniff_thread.join(timeout=5)
        if self._rotation_thread:
            self._rotation_thread.join(timeout=2)
        self._close_files()
        logging.info("Collector stopped.")


def auto_select_iface():
    candidates = get_if_list()
    logging.info("Interfaces detectadas: %s", candidates)

    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    for iface in candidates:
        if iface in stats and stats[iface].isup and iface in addrs:
            if any(addr.family.name in ("AF_INET", "AF_INET6") for addr in addrs[iface]):
                logging.info("Interfaz activa seleccionada: %s", iface)
                return iface

    logging.warning("No se encontró interfaz activa con IP, usando la primera: %s", candidates[0])
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description="Windows packet collector (pcap + metadata jsonl)")
    parser.add_argument("--iface", help="interface device")
    parser.add_argument("--out-dir", default="captures", help="output directory")
    parser.add_argument("--rotate-seconds", default=300, type=int, help="rotate files every N seconds")
    parser.add_argument("--max-files", default=48, type=int, help="keep last N pcap/jsonl pairs")
    parser.add_argument("--no-meta", dest="meta", action="store_false", help="disable metadata jsonl output")
    parser.add_argument("--list-ifaces", action="store_true", help="list available interfaces and exit")
    args = parser.parse_args()

    if args.list_ifaces:
        print("Available interfaces (use the exact string with --iface):")
        for i in get_if_list():
            print(repr(i))
        return

    # ✅ Por defecto siempre intenta auto
    iface = args.iface if args.iface else auto_select_iface()

    collector = WindowsPacketCollector(
        iface=iface,
        out_dir=args.out_dir,
        rotate_seconds=args.rotate_seconds,
        max_files=args.max_files,
        metadata=args.meta
    )

    def handle_sigint(sig, frame):
        logging.info("SIGINT received")
        collector.stop()

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    try:
        collector.start()
        while not collector._stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        collector.stop()


if __name__ == "__main__":
    main()
