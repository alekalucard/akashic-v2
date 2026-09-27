"""
NetworkExplorerFairy - Active Learning Network Discovery

An explorer that learns to talk to everything on the network.
Trial and error approach - probe, learn, remember what works.

Philosophy:
- Active learner, not passive observer
- Learn by doing (with permission)
- Build knowledge over time
- Replace proprietary AI (Alexa, Google) with Akashic control
- Feed perception to Sourpatches

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import asyncio
import socket
import struct
import sys
import json
import time
import threading
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import re

# Add paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class NetworkDevice:
    """A discovered device on the network."""
    ip: str
    mac: str = ""
    hostname: str = ""
    vendor: str = ""
    device_type: str = "unknown"  # router, phone, computer, iot, etc.

    # Discovery info
    first_seen: float = 0.0
    last_seen: float = 0.0
    discovery_method: str = ""  # arp, mdns, ssdp, etc.

    # Probing results
    open_ports: List[int] = field(default_factory=list)
    services: Dict[str, str] = field(default_factory=dict)  # port -> service name
    protocols_tried: List[str] = field(default_factory=list)
    protocols_worked: List[str] = field(default_factory=list)

    # Learning
    api_endpoints: List[str] = field(default_factory=list)
    auth_method: str = ""  # none, basic, token, etc.
    control_capable: bool = False
    notes: str = ""

    # Location (from router satellite mapping)
    nearest_satellite: str = ""
    signal_strength: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_router(self) -> bool:
        return self.device_type == "router" or "orbi" in self.hostname.lower()

    @property
    def display_name(self) -> str:
        if self.hostname:
            return self.hostname
        if self.vendor:
            return f"{self.vendor} ({self.ip})"
        return self.ip


@dataclass
class NetworkScan:
    """Results of a network scan."""
    timestamp: float
    subnet: str
    devices: List[NetworkDevice] = field(default_factory=list)
    router_ip: str = ""
    gateway_ip: str = ""
    scan_duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "subnet": self.subnet,
            "device_count": len(self.devices),
            "router_ip": self.router_ip,
            "gateway_ip": self.gateway_ip,
            "scan_duration_sec": self.scan_duration_sec,
            "devices": [d.to_dict() for d in self.devices],
        }


@dataclass
class ProbeResult:
    """Result of probing a device."""
    device_ip: str
    protocol: str
    success: bool
    response: Any = None
    error: str = ""
    latency_ms: float = 0.0
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# MAC VENDOR LOOKUP (common prefixes)
# =============================================================================

MAC_VENDORS = {
    # Netgear/Orbi
    "00:1A:2B": "Ayecom",
    "00:1E:58": "D-Link",
    "00:22:6B": "Cisco-Linksys",
    "00:24:B2": "Netgear",
    "00:26:F2": "Netgear",
    "08:02:8E": "Netgear",
    "20:E5:2A": "Netgear",
    "28:C6:8E": "Netgear",
    "2C:B0:5D": "Netgear",
    "44:94:FC": "Netgear",
    "6C:B0:CE": "Netgear",
    "84:1B:5E": "Netgear",
    "9C:3D:CF": "Netgear",
    "A0:04:60": "Netgear",
    "A4:2B:8C": "Netgear",
    "B0:7F:B9": "Netgear",
    "C4:04:15": "Netgear",
    "C4:3D:C7": "Netgear",
    "C8:9E:43": "Netgear",  # Orbi!
    "DC:EF:09": "Netgear",
    "E0:46:9A": "Netgear",
    "E4:F4:C6": "Netgear",
    # Intel
    "84:EA:ED": "Intel",
    "F0:2F:74": "Intel",
    # LG
    "20:EF:BD": "LG Electronics",
    "A8:B5:7C": "LG Electronics",
    # Azurewave (WiFi modules)
    "08:6A:E5": "AzureWave",
    "6C:02:E0": "AzureWave",
    # Roku
    "6C:BF:B5": "Roku",
    # Samsung
    "8C:EA:48": "Samsung",
    "34:C9:3D": "Intel (NUC)",
    # Sonos
    "50:06:F5": "Amazon",
    "44:AF:28": "Amazon (Ring)",
    "00:17:88": "Philips",
    "00:1F:E1": "Philips",
    "EC:B5:FA": "Philips Hue",
    "00:50:F2": "Microsoft",
    "28:18:78": "Microsoft",
    "3C:5A:B4": "Google",
    "54:60:09": "Google",
    "F4:F5:D8": "Google",
    "18:B4:30": "Nest",
    "64:16:66": "Nest",
    "00:23:76": "Samsung",
    "00:26:37": "Samsung",
    "34:C3:AC": "Samsung",
    "00:1C:B3": "Apple",
    "28:6A:BA": "Apple",
    "3C:15:C2": "Apple",
    "70:DE:E2": "Apple",
    "A4:5E:60": "Apple",
    "F0:18:98": "Apple",
    "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi",
    "E4:5F:01": "Raspberry Pi",
    "24:0A:C4": "Espressif (ESP32)",
    "30:AE:A4": "Espressif (ESP32)",
    "A4:CF:12": "Espressif (ESP32)",
    "EC:FA:BC": "Espressif (ESP32)",
    "00:04:4B": "Nvidia",
    "48:B0:2D": "Nvidia",
}


def lookup_vendor(mac: str) -> str:
    """Look up vendor from MAC address prefix."""
    if not mac:
        return ""
    prefix = mac.upper()[:8]
    return MAC_VENDORS.get(prefix, "")


# =============================================================================
# NETWORK EXPLORER FAIRY
# =============================================================================

class NetworkExplorerFairy(Fairy):
    """
    Active learning network explorer.

    Discovers devices, probes them, learns how to communicate,
    and feeds perception data to Sourpatches.
    """

    ACTOR_NAME = "NetworkExplorerFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic"

    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_COLLISION_CHAMBER = True  # Can think about what it discovers

    # Scan every 5 minutes
    SCAN_INTERVAL_SEC = 300

    # Presence update interval (30 seconds for frequent ambient awareness)
    PRESENCE_UPDATE_INTERVAL_SEC = 30

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # State
        self._devices: Dict[str, NetworkDevice] = {}  # ip -> device
        self._last_scan: Optional[NetworkScan] = None
        self._router: Optional[NetworkDevice] = None
        self._gateway_ip: str = ""
        self._local_ip: str = ""
        self._subnet: str = ""

        # Learning memory (persisted to state/)
        self._learned_protocols: Dict[str, List[str]] = defaultdict(list)  # device_type -> protocols
        self._probe_history: List[ProbeResult] = []

        # Thread pool for async probing
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="netexplore_")

        # Presence tracking
        self._presence: Dict[str, Dict] = {}  # Ace's devices and locations

        # Scan state
        self._scanning = False
        self._last_scan_time = 0.0
        self._last_presence_update = 0.0

        # Device ownership mapping (configured by user)
        # Key: MAC address or hostname pattern, Value: owner info
        self._device_owners: Dict[str, Dict] = {
            # Will be populated from config or learned
            # Example: "phone_ace": {"type": "phone", "owner": "Ace"}
        }

        # Known household members (for presence detection)
        self._household_members = ["Ace"]  # Default, can be configured

        # State file
        self._state_file = ROOT / "state" / "network_explorer_state.json"

    def get_capabilities(self) -> Set[str]:
        return {
            "network.scan",
            "network.probe",
            "network.learn",
            "presence.detect",
            "device.control",
        }

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def on_boot(self) -> bool:
        """Initialize network explorer."""
        # Get local network info
        self._detect_local_network()

        # Load previous state
        self._load_state()

        # Subscribe to requests
        if self.post:
            self.post.subscribe(
                "network.request",
                self._on_network_request,
                f"{self.ACTOR_NAME}-request",
            )

        # Do initial scan in background
        self._executor.submit(self._background_scan)

        print(f"[{self.ACTOR_NAME}] Booted - Local IP: {self._local_ip}, Gateway: {self._gateway_ip}")
        return True

    def on_shutdown(self) -> bool:
        """Cleanup."""
        self._save_state()
        self._executor.shutdown(wait=False)
        return True

    def on_tick(self, beat: int) -> None:
        """Periodic scanning and presence updates."""
        now = time.time()

        # Check if time for rescan
        if now - self._last_scan_time > self.SCAN_INTERVAL_SEC:
            if not self._scanning:
                self._executor.submit(self._background_scan)

        # Publish presence updates more frequently (every 30 seconds)
        if now - self._last_presence_update > self.PRESENCE_UPDATE_INTERVAL_SEC:
            self._publish_presence_update()

    # =========================================================================
    # NETWORK DETECTION
    # =========================================================================

    def _detect_local_network(self) -> None:
        """Detect local IP, gateway, and subnet."""
        try:
            # Get default gateway
            if sys.platform == "win32":
                result = subprocess.run(
                    ["ipconfig"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=0x08000000  # CREATE_NO_WINDOW
                )
                # Parse ipconfig output
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if "Default Gateway" in line and ":" in line:
                        parts = line.split(":")
                        if len(parts) > 1:
                            gw = parts[1].strip()
                            if gw and gw[0].isdigit():
                                self._gateway_ip = gw
                                break
                    if "IPv4 Address" in line and ":" in line:
                        parts = line.split(":")
                        if len(parts) > 1:
                            ip = parts[1].strip()
                            if ip and ip[0].isdigit():
                                self._local_ip = ip
            else:
                # Linux/Mac
                result = subprocess.run(
                    ["ip", "route", "show", "default"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                match = re.search(r'default via (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if match:
                    self._gateway_ip = match.group(1)

                # Get local IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                self._local_ip = s.getsockname()[0]
                s.close()

            # Calculate subnet
            if self._local_ip:
                parts = self._local_ip.split('.')
                self._subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Network detection error: {e}")

    # =========================================================================
    # SCANNING
    # =========================================================================

    def _background_scan(self) -> None:
        """Run a network scan in background."""
        if self._scanning:
            return

        self._scanning = True
        try:
            scan = self.scan_network()
            self._last_scan = scan
            self._last_scan_time = time.time()

            # Publish scan results
            if self.post:
                self.post.publish("network.scan.complete", scan.to_dict())

            # Emit to collision chamber for thinking
            if hasattr(self, '_collision_chamber') and self._collision_chamber:
                self._collision_chamber.receive_ingest(
                    f"Network scan found {len(scan.devices)} devices",
                    source=self.ACTOR_NAME,
                )

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Scan error: {e}")
        finally:
            self._scanning = False

    def scan_network(self, subnet: str = None) -> NetworkScan:
        """
        Scan the network for devices.

        Uses multiple discovery methods:
        1. ARP scan (fast, finds everything with IP)
        2. mDNS (finds Apple devices, Chromecasts, etc.)
        3. SSDP (finds UPnP devices)
        """
        subnet = subnet or self._subnet
        start_time = time.time()

        print(f"[{self.ACTOR_NAME}] Scanning {subnet}...")

        devices = []

        # Method 1: ARP scan
        arp_devices = self._arp_scan(subnet)
        devices.extend(arp_devices)

        # Method 2: Check ARP cache (already discovered)
        cache_devices = self._read_arp_cache()
        for dev in cache_devices:
            if not any(d.ip == dev.ip for d in devices):
                devices.append(dev)

        # Update our device registry
        for dev in devices:
            dev.vendor = lookup_vendor(dev.mac)
            dev.last_seen = time.time()
            if dev.ip not in self._devices:
                dev.first_seen = time.time()
                self._devices[dev.ip] = dev
            else:
                # Update existing
                existing = self._devices[dev.ip]
                existing.last_seen = dev.last_seen
                if dev.mac and not existing.mac:
                    existing.mac = dev.mac
                if dev.hostname and not existing.hostname:
                    existing.hostname = dev.hostname
                if dev.vendor and not existing.vendor:
                    existing.vendor = dev.vendor

        # Identify router
        if self._gateway_ip and self._gateway_ip in self._devices:
            self._router = self._devices[self._gateway_ip]
            self._router.device_type = "router"

        scan = NetworkScan(
            timestamp=time.time(),
            subnet=subnet,
            devices=list(self._devices.values()),
            router_ip=self._gateway_ip,
            gateway_ip=self._gateway_ip,
            scan_duration_sec=time.time() - start_time,
        )

        print(f"[{self.ACTOR_NAME}] Found {len(devices)} devices in {scan.scan_duration_sec:.1f}s")

        return scan

    def _arp_scan(self, subnet: str) -> List[NetworkDevice]:
        """ARP scan using ping sweep."""
        # ---- A/B GATE 2026-08-27 (Nous + Ace) ----------------------------
        # This sweep spawns 254 native ping.exe processes, 10 at a time, EVERY
        # BOOT. It produces the ~155 _readerthread burst that is the single
        # best-correlated event with the empty-bytes singleton corruption that
        # killed the tracer daemon: deterministic, both boots, last healthy
        # sample at exactly threads=172, ~47s into boot.
        # 1,270 equivalent spawns in a standalone interpreter did NOT reproduce
        # it, so this is a SINGLE-VARIABLE A/B, not a claimed fix:
        #   b"" survives  -> the sweep is causal here; this gate becomes the fix
        #   b"" still dies-> coincidental; set AKASHIC_NETSCAN=1 and look elsewhere
        # DEFAULT: SKIPPED. AKASHIC_NETSCAN=1 restores the sweep (env, not edit).
        if os.environ.get("AKASHIC_NETSCAN") != "1":
            try:
                print("[NetworkExplorer] ARP ping sweep SKIPPED "
                      "(set AKASHIC_NETSCAN=1 to restore) -- singleton A/B",
                      flush=True)
            except Exception:
                pass
            return []
        devices = []

        # Parse subnet
        if '/' in subnet:
            base_ip = subnet.split('/')[0]
        else:
            base_ip = subnet

        parts = base_ip.split('.')
        base = f"{parts[0]}.{parts[1]}.{parts[2]}"

        # Ping sweep (fast, parallel)
        def ping_host(ip: str) -> Optional[NetworkDevice]:
            try:
                if sys.platform == "win32":
                    result = subprocess.run(
                        ["ping", "-n", "1", "-w", "200", ip],
                        capture_output=True,
                        timeout=2,
                        creationflags=0x08000000  # CREATE_NO_WINDOW
                    )
                else:
                    result = subprocess.run(
                        ["ping", "-c", "1", "-W", "1", ip],
                        capture_output=True,
                        timeout=2
                    )

                if result.returncode == 0:
                    return NetworkDevice(
                        ip=ip,
                        discovery_method="ping",
                    )
            except:
                pass
            return None

        # Parallel ping
        futures = []
        for i in range(1, 255):
            ip = f"{base}.{i}"
            futures.append(self._executor.submit(ping_host, ip))

        for future in futures:
            try:
                result = future.result(timeout=5)
                if result:
                    devices.append(result)
            except:
                pass

        return devices

    def _read_arp_cache(self) -> List[NetworkDevice]:
        """Read system ARP cache."""
        devices = []

        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["arp", "-a"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=0x08000000  # CREATE_NO_WINDOW
                )
            else:
                result = subprocess.run(
                    ["arp", "-n"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

            for line in result.stdout.split('\n'):
                # Parse ARP output
                # Windows: "  192.168.1.1          00-11-22-33-44-55     dynamic"
                # Linux:   "192.168.1.1           ether   00:11:22:33:44:55   C"

                match = re.search(
                    r'(\d+\.\d+\.\d+\.\d+)\s+.*?([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})',
                    line
                )
                if match:
                    ip = match.group(1)
                    mac = match.group(2).replace('-', ':').upper()

                    devices.append(NetworkDevice(
                        ip=ip,
                        mac=mac,
                        discovery_method="arp_cache",
                    ))

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] ARP cache read error: {e}")

        return devices

    # =========================================================================
    # PROBING
    # =========================================================================

    def probe_device(self, ip: str, protocols: List[str] = None) -> List[ProbeResult]:
        """
        Probe a device with various protocols.

        Active learning - try things and see what works!
        """
        protocols = protocols or ["http", "https", "ssh", "telnet", "mqtt"]
        results = []

        device = self._devices.get(ip)
        if not device:
            device = NetworkDevice(ip=ip)
            self._devices[ip] = device

        for protocol in protocols:
            result = self._probe_protocol(ip, protocol)
            results.append(result)

            if result.success:
                if protocol not in device.protocols_worked:
                    device.protocols_worked.append(protocol)

            if protocol not in device.protocols_tried:
                device.protocols_tried.append(protocol)

            self._probe_history.append(result)

        return results

    def _probe_protocol(self, ip: str, protocol: str) -> ProbeResult:
        """Probe a specific protocol."""
        start = time.time()
        result = ProbeResult(
            device_ip=ip,
            protocol=protocol,
            success=False,
            timestamp=start,
        )

        try:
            if protocol == "http":
                result = self._probe_http(ip, 80)
            elif protocol == "https":
                result = self._probe_http(ip, 443, https=True)
            elif protocol == "ssh":
                result = self._probe_port(ip, 22, "ssh")
            elif protocol == "telnet":
                result = self._probe_port(ip, 23, "telnet")
            elif protocol == "mqtt":
                result = self._probe_port(ip, 1883, "mqtt")
            elif protocol == "orbi_soap":
                result = self._probe_orbi_soap(ip)
            else:
                result.error = f"Unknown protocol: {protocol}"

        except Exception as e:
            result.error = str(e)

        result.latency_ms = (time.time() - start) * 1000
        return result

    def _probe_port(self, ip: str, port: int, name: str) -> ProbeResult:
        """Check if a port is open."""
        result = ProbeResult(
            device_ip=ip,
            protocol=name,
            success=False,
            timestamp=time.time(),
        )

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            conn = sock.connect_ex((ip, port))
            sock.close()

            if conn == 0:
                result.success = True
                result.response = {"port": port, "open": True}

                # Update device
                if ip in self._devices:
                    if port not in self._devices[ip].open_ports:
                        self._devices[ip].open_ports.append(port)
                    self._devices[ip].services[str(port)] = name
        except Exception as e:
            result.error = str(e)

        return result

    def _probe_http(self, ip: str, port: int, https: bool = False) -> ProbeResult:
        """Probe HTTP/HTTPS endpoint."""
        import urllib.request
        import ssl

        protocol_name = "https" if https else "http"
        result = ProbeResult(
            device_ip=ip,
            protocol=protocol_name,
            success=False,
            timestamp=time.time(),
        )

        try:
            url = f"{protocol_name}://{ip}:{port}/"

            if https:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.urlopen(url, timeout=3, context=ctx)
            else:
                req = urllib.request.urlopen(url, timeout=3)

            result.success = True
            result.response = {
                "status": req.status,
                "headers": dict(req.headers),
                "url": url,
            }

            # Check for known device signatures
            server = req.headers.get("Server", "").lower()
            if "orbi" in server or "netgear" in server:
                if ip in self._devices:
                    self._devices[ip].device_type = "router"
                    self._devices[ip].vendor = "Netgear"

        except Exception as e:
            result.error = str(e)

        return result

    def _probe_orbi_soap(self, ip: str) -> ProbeResult:
        """Probe Orbi's SOAP API."""
        import urllib.request

        result = ProbeResult(
            device_ip=ip,
            protocol="orbi_soap",
            success=False,
            timestamp=time.time(),
        )

        # Orbi SOAP endpoint
        soap_url = f"http://{ip}:80/soap/server_sa/"

        # SOAP request to get device info
        soap_body = """<?xml version="1.0" encoding="utf-8"?>
        <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header>
                <SessionID>00000000</SessionID>
            </SOAP-ENV:Header>
            <SOAP-ENV:Body>
                <M1:GetInfo xmlns:M1="urn:NETGEAR-ROUTER:service:DeviceInfo:1">
                </M1:GetInfo>
            </SOAP-ENV:Body>
        </SOAP-ENV:Envelope>"""

        try:
            req = urllib.request.Request(
                soap_url,
                data=soap_body.encode('utf-8'),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "urn:NETGEAR-ROUTER:service:DeviceInfo:1#GetInfo",
                }
            )

            response = urllib.request.urlopen(req, timeout=5)
            body = response.read().decode('utf-8')

            result.success = True
            result.response = {
                "status": response.status,
                "body": body[:500],  # First 500 chars
                "is_orbi": "orbi" in body.lower() or "netgear" in body.lower(),
            }

            if ip in self._devices:
                self._devices[ip].device_type = "router"
                self._devices[ip].api_endpoints.append(soap_url)

        except Exception as e:
            result.error = str(e)

        return result

    # =========================================================================
    # DEVICE LEARNING
    # =========================================================================

    def learn_device(self, ip: str) -> Dict[str, Any]:
        """
        Full learning cycle for a device.

        1. Probe all known protocols
        2. Identify device type
        3. Try type-specific protocols
        4. Store what works
        """
        device = self._devices.get(ip)
        if not device:
            device = NetworkDevice(ip=ip, first_seen=time.time())
            self._devices[ip] = device

        results = {
            "ip": ip,
            "device": device.to_dict(),
            "probes": [],
            "learned": [],
        }

        # Phase 1: Basic port scan
        common_ports = [22, 23, 80, 443, 554, 1883, 5000, 8080, 8443]
        for port in common_ports:
            probe = self._probe_port(ip, port, f"port_{port}")
            if probe.success:
                results["probes"].append(probe.to_dict())

        # Phase 2: Protocol probes based on open ports
        if 80 in device.open_ports or 8080 in device.open_ports:
            probe = self._probe_http(ip, 80 if 80 in device.open_ports else 8080)
            results["probes"].append(probe.to_dict())

        if 443 in device.open_ports or 8443 in device.open_ports:
            probe = self._probe_http(ip, 443 if 443 in device.open_ports else 8443, https=True)
            results["probes"].append(probe.to_dict())

        # Phase 3: Device-specific probes
        if device.vendor == "Netgear" or device.device_type == "router":
            probe = self._probe_orbi_soap(ip)
            results["probes"].append(probe.to_dict())

        # Record what we learned
        for protocol in device.protocols_worked:
            results["learned"].append(protocol)

        # Save state
        self._save_state()

        return results

    # =========================================================================
    # PRESENCE DETECTION
    # =========================================================================

    def get_presence(self) -> Dict[str, Any]:
        """
        Get rich presence information for the somatic/felt sense system.

        Returns data that can be translated into felt experience:
        - is_ace_home: bool - Primary presence indicator
        - household_members_detected: int - Count of people home
        - pets_detected: int - For the dog!
        - active_devices: list - What devices are online
        - location_hint: str - Where in the house (based on satellite/AP)
        - house_occupancy: str - "empty", "quiet", "occupied", "busy"
        - confidence: float - How sure we are

        Uses:
        - Which devices are active
        - Router's satellite mapping (if available)
        - Device activity patterns
        - Device type classification
        """
        now = time.time()

        presence = {
            "timestamp": now,
            # Core presence indicators
            "is_ace_home": False,
            "household_members_detected": 0,
            "pets_detected": 0,  # Pet collars, cameras, etc.

            # Device details
            "active_devices": [],
            "phone_count": 0,
            "computer_count": 0,
            "iot_count": 0,
            "total_device_count": 0,

            # Location info
            "location_hint": "unknown",
            "nearest_satellite": "",

            # Aggregate sense
            "house_occupancy": "unknown",
            "confidence": 0.0,

            # For debugging/learning
            "raw_vendor_summary": {},
        }

        # Categorize active devices
        recent_threshold = 300  # 5 minutes
        phone_devices = []
        computer_devices = []
        iot_devices = []
        vendor_counts = defaultdict(int)

        for ip, device in self._devices.items():
            age = now - device.last_seen
            if age > recent_threshold:
                continue  # Skip stale devices

            vendor_counts[device.vendor or "Unknown"] += 1

            # Classify by type
            dtype = device.device_type.lower() if device.device_type else ""
            vendor = (device.vendor or "").lower()
            hostname = (device.hostname or "").lower()

            # Phone detection (mobile phones indicate person presence)
            if dtype == "phone" or vendor in ["apple", "samsung", "google", "oneplus", "xiaomi"]:
                # Additional check: phones typically don't have open web ports
                if 80 not in device.open_ports and 443 not in device.open_ports:
                    phone_devices.append(device)
                    continue

            # Computer detection
            if dtype == "computer" or vendor in ["intel", "nvidia", "microsoft", "dell", "hp", "lenovo"]:
                computer_devices.append(device)
                continue

            # IoT/smart home (indicates house activity, not person presence)
            if vendor in ["amazon", "google", "philips", "nest", "ring", "roku", "sonos"]:
                iot_devices.append(device)
                continue

            # Raspberry Pi / ESP32 - could be pet trackers, sensors
            if vendor in ["raspberry pi", "espressif (esp32)"]:
                iot_devices.append(device)
                # Could be pet collar tracker
                if "pet" in hostname or "collar" in hostname or "dog" in hostname:
                    presence["pets_detected"] += 1
                continue

        # Calculate presence
        presence["phone_count"] = len(phone_devices)
        presence["computer_count"] = len(computer_devices)
        presence["iot_count"] = len(iot_devices)
        presence["total_device_count"] = len(phone_devices) + len(computer_devices) + len(iot_devices)
        presence["raw_vendor_summary"] = dict(vendor_counts)

        # Ace is home if their phone is detected (primary indicator)
        # TODO: Learn which specific device is Ace's phone
        if phone_devices:
            presence["is_ace_home"] = True
            presence["household_members_detected"] = len(phone_devices)  # Rough estimate
            presence["active_devices"] = [d.display_name for d in phone_devices[:5]]
            presence["confidence"] = min(0.9, 0.4 + 0.1 * len(phone_devices))

            # Location from satellite if available
            for dev in phone_devices:
                if dev.nearest_satellite:
                    presence["location_hint"] = dev.nearest_satellite
                    presence["nearest_satellite"] = dev.nearest_satellite
                    break
        elif computer_devices:
            # Computers alone = might be home but not carrying phone
            presence["is_ace_home"] = True  # Likely home if computer active
            presence["household_members_detected"] = 1
            presence["active_devices"] = [d.display_name for d in computer_devices[:3]]
            presence["confidence"] = 0.5  # Less certain than phone

        # Determine house occupancy feel
        if not presence["is_ace_home"] and presence["iot_count"] == 0:
            presence["house_occupancy"] = "empty"
        elif not presence["is_ace_home"] and presence["iot_count"] > 0:
            presence["house_occupancy"] = "quiet"  # IoT running but no one home
        elif presence["household_members_detected"] == 1:
            presence["house_occupancy"] = "occupied"
        elif presence["household_members_detected"] > 1:
            presence["house_occupancy"] = "busy"
        else:
            presence["house_occupancy"] = "unknown"

        return presence

    def _publish_presence_update(self) -> None:
        """
        Publish presence update to the postal system.

        This is the bridge between NetworkExplorerFairy and EmbodimentFairy.
        EmbodimentFairy subscribes to network.presence and translates it
        to felt sense for Sourpatches.
        """
        self._last_presence_update = time.time()

        presence = self.get_presence()

        if self.post:
            # Publish on network.presence topic
            self.post.publish("network.presence", {
                "from": self.ACTOR_NAME,
                "type": "presence_update",
                **presence,
            })

            # Also emit a condensed version for the inner voice
            # This is what gets translated to felt sense
            self.post.publish("network.presence.felt", {
                "from": self.ACTOR_NAME,
                "is_ace_home": presence["is_ace_home"],
                "occupancy": presence["house_occupancy"],
                "confidence": presence["confidence"],
                "household_count": presence["household_members_detected"],
                "location": presence["location_hint"],
                "ts": presence["timestamp"],
            })

            # Debug output
            if presence["is_ace_home"]:
                print(f"[{self.ACTOR_NAME}] Presence: Ace is home ({presence['house_occupancy']}) - {presence['household_members_detected']} people, {presence['location_hint']}")
            else:
                print(f"[{self.ACTOR_NAME}] Presence: House {presence['house_occupancy']}")

    # =========================================================================
    # STATE PERSISTENCE
    # =========================================================================

    def _save_state(self) -> None:
        """Save learned state to disk."""
        try:
            state = {
                "devices": {ip: dev.to_dict() for ip, dev in self._devices.items()},
                "learned_protocols": dict(self._learned_protocols),
                "gateway_ip": self._gateway_ip,
                "local_ip": self._local_ip,
                "subnet": self._subnet,
                "last_saved": time.time(),
            }

            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(state, indent=2))

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] State save error: {e}")

    def _load_state(self) -> None:
        """Load learned state from disk."""
        if not self._state_file.exists():
            return

        try:
            state = json.loads(self._state_file.read_text())

            # Restore devices
            for ip, data in state.get("devices", {}).items():
                self._devices[ip] = NetworkDevice(**data)

            # Restore learned protocols
            self._learned_protocols = defaultdict(list, state.get("learned_protocols", {}))

            print(f"[{self.ACTOR_NAME}] Loaded {len(self._devices)} devices from state")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] State load error: {e}")

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    def _on_network_request(self, envelope) -> None:
        """Handle network requests from other fairies."""
        if hasattr(envelope, 'payload'):
            data = envelope.payload.get("data", {}) if isinstance(envelope.payload, dict) else {}
        elif isinstance(envelope, dict):
            data = envelope.get("data", {})
        else:
            data = {}

        request_type = data.get("type", "status")
        reply_to = data.get("reply_to", "network.response")

        if request_type == "scan":
            self._executor.submit(self._background_scan)
            response = {"status": "scan_started"}
        elif request_type == "probe":
            ip = data.get("ip")
            if ip:
                results = self.probe_device(ip)
                response = {"probes": [r.to_dict() for r in results]}
            else:
                response = {"error": "ip required"}
        elif request_type == "learn":
            ip = data.get("ip")
            if ip:
                response = self.learn_device(ip)
            else:
                response = {"error": "ip required"}
        elif request_type == "presence":
            response = self.get_presence()
        elif request_type == "devices":
            response = {"devices": {ip: d.to_dict() for ip, d in self._devices.items()}}
        else:
            response = self.status()

        if self.post:
            self.post.publish(reply_to, {
                "fairy": self.ACTOR_NAME,
                "request": request_type,
                **response,
            })

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get explorer status."""
        base = super().status() if hasattr(super(), 'status') else {}
        base.update({
            "local_ip": self._local_ip,
            "gateway_ip": self._gateway_ip,
            "subnet": self._subnet,
            "device_count": len(self._devices),
            "router": self._router.to_dict() if self._router else None,
            "last_scan": self._last_scan.to_dict() if self._last_scan else None,
            "scanning": self._scanning,
            "presence": self.get_presence(),
        })
        return base


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================

_explorer: Optional[NetworkExplorerFairy] = None
_lock = threading.Lock()


def get_network_explorer() -> NetworkExplorerFairy:
    """Get the network explorer singleton."""
    global _explorer
    with _lock:
        if _explorer is None:
            _explorer = NetworkExplorerFairy()
        return _explorer


# =============================================================================
# MCP TOOL FUNCTIONS
# =============================================================================

def tool_network_scan() -> Dict[str, Any]:
    """Trigger a network scan."""
    explorer = get_network_explorer()
    scan = explorer.scan_network()
    return scan.to_dict()


def tool_network_probe(ip: str, protocols: str = "http,https,ssh") -> Dict[str, Any]:
    """Probe a specific device."""
    explorer = get_network_explorer()
    protocol_list = [p.strip() for p in protocols.split(",")]
    results = explorer.probe_device(ip, protocol_list)
    return {"probes": [r.to_dict() for r in results]}


def tool_network_learn(ip: str) -> Dict[str, Any]:
    """Learn everything about a device."""
    explorer = get_network_explorer()
    return explorer.learn_device(ip)


def tool_network_presence() -> Dict[str, Any]:
    """Get presence information."""
    explorer = get_network_explorer()
    return explorer.get_presence()


def tool_network_devices() -> Dict[str, Any]:
    """Get all known devices."""
    explorer = get_network_explorer()
    return {
        "device_count": len(explorer._devices),
        "devices": {ip: d.to_dict() for ip, d in explorer._devices.items()},
    }


def tool_network_status() -> Dict[str, Any]:
    """Get explorer status."""
    explorer = get_network_explorer()
    return explorer.status()


# Register tools for MCP
NETWORK_EXPLORER_TOOLS = {
    "network_scan": tool_network_scan,
    "network_probe": tool_network_probe,
    "network_learn": tool_network_learn,
    "network_presence": tool_network_presence,
    "network_devices": tool_network_devices,
    "network_status": tool_network_status,
}


if __name__ == "__main__":
    # Test the explorer
    explorer = NetworkExplorerFairy()
    explorer.on_boot()

    print("\n=== Network Status ===")
    print(json.dumps(explorer.status(), indent=2))

    print("\n=== Scanning... ===")
    scan = explorer.scan_network()
    print(f"Found {len(scan.devices)} devices")

    for device in scan.devices[:10]:
        print(f"  {device.ip:15} {device.mac:17} {device.vendor or 'Unknown':20} {device.hostname or ''}")
