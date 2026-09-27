"""
Orbi Driver - Netgear Orbi Router Integration

Talks to Orbi routers via:
1. SOAP API (device list, settings)
2. Web interface scraping (when SOAP fails)
3. Telnet (if enabled, for deep access)

WiFi Sensing:
- Connected devices
- Device-to-satellite mapping (rough location)
- Signal strength
- Traffic patterns

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import base64
import hashlib
import json
import re
import socket
import time
import urllib.request
import urllib.parse
import ssl
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET


@dataclass
class OrbiDevice:
    """A device connected to the Orbi network."""
    mac: str
    ip: str
    name: str = ""
    connection_type: str = ""  # 2.4GHz, 5GHz, Ethernet
    satellite_mac: str = ""  # Which satellite it's connected to
    satellite_name: str = ""
    signal_strength: int = 0  # dBm or percentage
    link_rate: int = 0  # Mbps
    first_seen: float = 0.0
    last_seen: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrbiSatellite:
    """An Orbi satellite unit."""
    mac: str
    ip: str
    name: str = ""
    model: str = ""
    firmware: str = ""
    connection_type: str = ""  # backhaul type
    signal_strength: int = 0
    status: str = "unknown"
    location: str = ""  # User-defined location name

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrbiStatus:
    """Overall Orbi system status."""
    router_ip: str
    router_mac: str = ""
    router_name: str = ""
    model: str = ""
    firmware: str = ""
    wan_ip: str = ""
    satellites: List[OrbiSatellite] = field(default_factory=list)
    connected_devices: List[OrbiDevice] = field(default_factory=list)
    uptime_sec: int = 0
    last_updated: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "satellites": [s.to_dict() for s in self.satellites],
            "connected_devices": [d.to_dict() for d in self.connected_devices],
        }


class OrbiDriver:
    """
    Driver for Netgear Orbi routers.

    Provides:
    - Device enumeration
    - Satellite mapping (for location)
    - Traffic monitoring
    - Presence detection
    """

    # SOAP endpoints
    SOAP_DEVICE_INFO = "urn:NETGEAR-ROUTER:service:DeviceInfo:1"
    SOAP_DEVICE_CONFIG = "urn:NETGEAR-ROUTER:service:DeviceConfig:1"
    SOAP_WLAN_CONFIG = "urn:NETGEAR-ROUTER:service:WLANConfiguration:1"
    SOAP_PARENTAL = "urn:NETGEAR-ROUTER:service:ParentalControl:1"

    def __init__(self, router_ip: str, username: str = "admin", password: str = ""):
        self.router_ip = router_ip
        self.username = username
        self.password = password

        self._session_id: Optional[str] = None
        self._authenticated = False
        self._last_status: Optional[OrbiStatus] = None

        # SSL context for HTTPS
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    def authenticate(self) -> bool:
        """
        Authenticate with the Orbi router.

        Tries multiple methods:
        1. SOAP with session ID
        2. Basic auth on web interface
        """
        # Try SOAP authentication
        try:
            result = self._soap_request(
                self.SOAP_DEVICE_INFO,
                "Authenticate",
                {"Username": self.username, "Password": self.password}
            )
            if result and "ResponseCode" in result:
                self._authenticated = True
                return True
        except Exception:
            pass

        # Try basic auth test
        try:
            auth_string = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()

            req = urllib.request.Request(
                f"http://{self.router_ip}/",
                headers={"Authorization": f"Basic {auth_string}"}
            )
            response = urllib.request.urlopen(req, timeout=5)
            if response.status == 200:
                self._authenticated = True
                return True
        except Exception:
            pass

        return False

    # =========================================================================
    # SOAP API
    # =========================================================================

    def _soap_request(
        self,
        service: str,
        action: str,
        params: Dict[str, str] = None
    ) -> Optional[Dict[str, Any]]:
        """Make a SOAP request to the Orbi."""
        url = f"http://{self.router_ip}:80/soap/server_sa/"

        # Build SOAP body
        params_xml = ""
        if params:
            for key, value in params.items():
                params_xml += f"<{key}>{value}</{key}>"

        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
        <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header>
                <SessionID>{self._session_id or "DEF00000000"}</SessionID>
            </SOAP-ENV:Header>
            <SOAP-ENV:Body>
                <M1:{action} xmlns:M1="{service}">
                    {params_xml}
                </M1:{action}>
            </SOAP-ENV:Body>
        </SOAP-ENV:Envelope>"""

        try:
            req = urllib.request.Request(
                url,
                data=soap_body.encode('utf-8'),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": f"{service}#{action}",
                }
            )

            # Add basic auth if we have password
            if self.password:
                auth_string = base64.b64encode(
                    f"{self.username}:{self.password}".encode()
                ).decode()
                req.add_header("Authorization", f"Basic {auth_string}")

            response = urllib.request.urlopen(req, timeout=10)
            body = response.read().decode('utf-8')

            # Parse response
            return self._parse_soap_response(body)

        except Exception as e:
            print(f"[OrbiDriver] SOAP error: {e}")
            return None

    def _parse_soap_response(self, xml_body: str) -> Dict[str, Any]:
        """Parse SOAP XML response into dict."""
        result = {}

        try:
            # Remove namespaces for easier parsing
            xml_clean = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_body)
            xml_clean = re.sub(r'<[^:>]+:', '<', xml_clean)
            xml_clean = re.sub(r'</[^:>]+:', '</', xml_clean)

            root = ET.fromstring(xml_clean)

            # Find Body element
            body = root.find('.//Body')
            if body is not None:
                # Get all child elements
                for child in body.iter():
                    if child.text and child.text.strip():
                        result[child.tag] = child.text.strip()

        except Exception as e:
            print(f"[OrbiDriver] XML parse error: {e}")

        return result

    # =========================================================================
    # DEVICE ENUMERATION
    # =========================================================================

    def get_attached_devices(self) -> List[OrbiDevice]:
        """Get all devices attached to the Orbi network."""
        devices = []

        # Try SOAP API first
        result = self._soap_request(
            self.SOAP_DEVICE_INFO,
            "GetAttachDevice"
        )

        if result and "NewAttachDevice" in result:
            devices = self._parse_attached_devices(result["NewAttachDevice"])
        else:
            # Fallback: try GetAttachDevice2 (newer API)
            result = self._soap_request(
                self.SOAP_DEVICE_INFO,
                "GetAttachDevice2"
            )
            if result and "NewAttachDevice" in result:
                devices = self._parse_attached_devices(result["NewAttachDevice"])

        return devices

    def _parse_attached_devices(self, raw: str) -> List[OrbiDevice]:
        """Parse the attached device string from SOAP."""
        devices = []

        # Format varies by firmware, common format:
        # "IP;MAC;Name;ConnectionType;..."
        # or XML-like structure

        if raw.startswith("@"):
            # New format: @MAC@IP@NAME@TYPE@...
            entries = raw.split("@")
            i = 1
            while i < len(entries) - 3:
                try:
                    device = OrbiDevice(
                        mac=entries[i],
                        ip=entries[i + 1] if i + 1 < len(entries) else "",
                        name=entries[i + 2] if i + 2 < len(entries) else "",
                        last_seen=time.time(),
                    )
                    devices.append(device)
                    i += 4  # Skip to next device
                except:
                    i += 1
        else:
            # Try semicolon-separated format
            for line in raw.split(";"):
                parts = line.split(",")
                if len(parts) >= 2:
                    device = OrbiDevice(
                        ip=parts[0].strip(),
                        mac=parts[1].strip() if len(parts) > 1 else "",
                        name=parts[2].strip() if len(parts) > 2 else "",
                        last_seen=time.time(),
                    )
                    devices.append(device)

        return devices

    # =========================================================================
    # SATELLITE DISCOVERY
    # =========================================================================

    def get_satellites(self) -> List[OrbiSatellite]:
        """Get all Orbi satellites."""
        satellites = []

        # Try GetSatelliteInfo
        result = self._soap_request(
            self.SOAP_DEVICE_INFO,
            "GetSatelliteInfo"
        )

        if result:
            # Parse satellite info
            for key, value in result.items():
                if "satellite" in key.lower() or "mac" in key.lower():
                    # Build satellite object
                    pass

        return satellites

    def get_device_satellite_mapping(self) -> Dict[str, str]:
        """Map each device MAC to its connected satellite."""
        mapping = {}

        # This requires either:
        # 1. Web interface scraping
        # 2. Telnet access to run internal commands
        # 3. Newer SOAP API with satellite info

        # Try GetTopology if available
        result = self._soap_request(
            self.SOAP_DEVICE_INFO,
            "GetSystemTopology"
        )

        if result:
            # Parse topology to get mappings
            pass

        return mapping

    # =========================================================================
    # TRAFFIC & PRESENCE
    # =========================================================================

    def get_traffic_stats(self) -> Dict[str, Any]:
        """Get traffic statistics."""
        result = self._soap_request(
            self.SOAP_DEVICE_INFO,
            "GetTrafficMeter"
        )

        if result:
            return {
                "today_upload_mb": float(result.get("NewTodayUpload", 0)) / 1024 / 1024,
                "today_download_mb": float(result.get("NewTodayDownload", 0)) / 1024 / 1024,
                "month_upload_mb": float(result.get("NewMonthUpload", 0)) / 1024 / 1024,
                "month_download_mb": float(result.get("NewMonthDownload", 0)) / 1024 / 1024,
            }

        return {}

    def detect_presence(self, known_devices: List[str]) -> Dict[str, Any]:
        """
        Detect presence based on known device MACs.

        Args:
            known_devices: List of MAC addresses for "Ace's devices"

        Returns:
            Presence info including location
        """
        attached = self.get_attached_devices()

        present_devices = []
        location = "unknown"

        for device in attached:
            if device.mac.upper() in [m.upper() for m in known_devices]:
                present_devices.append(device)

                # Use satellite mapping for location
                if device.satellite_name:
                    location = device.satellite_name

        return {
            "home": len(present_devices) > 0,
            "devices_present": [d.to_dict() for d in present_devices],
            "location": location,
            "confidence": min(0.95, 0.4 * len(present_devices)),
            "timestamp": time.time(),
        }

    # =========================================================================
    # SYSTEM INFO
    # =========================================================================

    def get_system_info(self) -> Dict[str, Any]:
        """Get Orbi system information."""
        result = self._soap_request(
            self.SOAP_DEVICE_INFO,
            "GetInfo"
        )

        if result:
            return {
                "model": result.get("ModelName", "Orbi"),
                "firmware": result.get("Firmwareversion", ""),
                "serial": result.get("SerialNumber", ""),
                "mac": result.get("DeviceMac", ""),
                "description": result.get("Description", ""),
            }

        return {}

    def get_status(self) -> OrbiStatus:
        """Get complete Orbi status."""
        status = OrbiStatus(
            router_ip=self.router_ip,
            last_updated=time.time(),
        )

        # Get system info
        sys_info = self.get_system_info()
        status.model = sys_info.get("model", "")
        status.firmware = sys_info.get("firmware", "")
        status.router_mac = sys_info.get("mac", "")

        # Get attached devices
        status.connected_devices = self.get_attached_devices()

        # Get satellites
        status.satellites = self.get_satellites()

        self._last_status = status
        return status

    # =========================================================================
    # WEB INTERFACE SCRAPING (fallback)
    # =========================================================================

    def _scrape_attached_devices(self) -> List[OrbiDevice]:
        """Scrape attached devices from web interface."""
        devices = []

        try:
            auth_string = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()

            # Try common endpoints
            endpoints = [
                "/DEV_device_info.htm",
                "/attached_devices.htm",
                "/DEV_show_device.htm",
            ]

            for endpoint in endpoints:
                try:
                    req = urllib.request.Request(
                        f"http://{self.router_ip}{endpoint}",
                        headers={"Authorization": f"Basic {auth_string}"}
                    )
                    response = urllib.request.urlopen(req, timeout=5)
                    html = response.read().decode('utf-8')

                    # Parse HTML for device info
                    devices = self._parse_device_html(html)
                    if devices:
                        break
                except:
                    continue

        except Exception as e:
            print(f"[OrbiDriver] Scrape error: {e}")

        return devices

    def _parse_device_html(self, html: str) -> List[OrbiDevice]:
        """Parse device list from HTML."""
        devices = []

        # Look for common patterns in Orbi HTML
        # This is firmware-dependent and may need adjustment

        # Pattern 1: JSON embedded in script
        json_match = re.search(r'var\s+\w+\s*=\s*(\[.*?\]);', html, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                for item in data:
                    if isinstance(item, dict):
                        device = OrbiDevice(
                            mac=item.get("mac", item.get("MAC", "")),
                            ip=item.get("ip", item.get("IP", "")),
                            name=item.get("name", item.get("Name", "")),
                            last_seen=time.time(),
                        )
                        devices.append(device)
            except:
                pass

        # Pattern 2: Table rows
        if not devices:
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
            for row in rows:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
                if len(cells) >= 2:
                    # Try to find IP and MAC in cells
                    ip = ""
                    mac = ""
                    name = ""

                    for cell in cells:
                        cell_clean = re.sub(r'<[^>]+>', '', cell).strip()
                        if re.match(r'\d+\.\d+\.\d+\.\d+', cell_clean):
                            ip = cell_clean
                        elif re.match(r'[0-9a-fA-F:]{17}', cell_clean):
                            mac = cell_clean
                        elif cell_clean and not ip and not mac:
                            name = cell_clean

                    if ip or mac:
                        devices.append(OrbiDevice(
                            mac=mac,
                            ip=ip,
                            name=name,
                            last_seen=time.time(),
                        ))

        return devices

    # =========================================================================
    # TELNET ACCESS (for deep control)
    # =========================================================================

    def enable_telnet(self) -> bool:
        """
        Try to enable telnet on the Orbi.

        This requires a special SOAP call or web request.
        Once enabled, we can run internal commands.
        """
        # Method 1: SOAP EnableTelnet
        result = self._soap_request(
            self.SOAP_DEVICE_CONFIG,
            "EnableTelnet"
        )

        if result:
            return True

        # Method 2: Magic packet to enable debug mode
        # (Firmware-specific, may not work)

        return False

    def telnet_command(self, command: str) -> Optional[str]:
        """Run a command via telnet."""
        try:
            import telnetlib

            tn = telnetlib.Telnet(self.router_ip, 23, timeout=5)

            # Login
            tn.read_until(b"login: ", timeout=5)
            tn.write(f"{self.username}\n".encode())
            tn.read_until(b"Password: ", timeout=5)
            tn.write(f"{self.password}\n".encode())

            # Wait for prompt
            tn.read_until(b"# ", timeout=5)

            # Run command
            tn.write(f"{command}\n".encode())
            time.sleep(0.5)
            output = tn.read_very_eager().decode()

            tn.close()
            return output

        except Exception as e:
            print(f"[OrbiDriver] Telnet error: {e}")
            return None


# =============================================================================
# FACTORY
# =============================================================================

def create_orbi_driver(router_ip: str, password: str = "") -> OrbiDriver:
    """Create an Orbi driver instance."""
    return OrbiDriver(router_ip, password=password)


def auto_detect_orbi() -> Optional[str]:
    """
    Try to auto-detect Orbi router on the network.

    Looks for common Orbi IP patterns and SOAP endpoints.
    """
    common_ips = [
        "192.168.1.1",
        "192.168.0.1",
        "10.0.0.1",
        "orbilogin.com",
        "www.orbilogin.com",
    ]

    for ip in common_ips:
        try:
            # Quick port check
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, 80))
            sock.close()

            if result == 0:
                # Try SOAP endpoint
                driver = OrbiDriver(ip)
                info = driver.get_system_info()
                if info and "orbi" in info.get("model", "").lower():
                    return ip

        except:
            continue

    return None


if __name__ == "__main__":
    # Test auto-detection
    print("Searching for Orbi router...")
    orbi_ip = auto_detect_orbi()

    if orbi_ip:
        print(f"Found Orbi at {orbi_ip}")
        driver = OrbiDriver(orbi_ip)

        print("\nSystem Info:")
        print(json.dumps(driver.get_system_info(), indent=2))

        print("\nAttached Devices:")
        devices = driver.get_attached_devices()
        for d in devices:
            print(f"  {d.ip:15} {d.mac:17} {d.name or 'Unknown'}")
    else:
        print("No Orbi found. Try specifying IP manually.")
