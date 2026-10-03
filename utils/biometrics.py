import requests
import xml.etree.ElementTree as ET

class BiometricEngine:
    def __init__(self):
        # Automatically find the scanner when the app boots
        self.device_port = self._scan_for_device()

    def _scan_for_device(self):
        """Silently finds which port the Mantra scanner is running on."""
        for port in range(11100, 11106):
            try:
                response = requests.request("RDSERVICE", f"http://127.0.0.1:{port}", timeout=1)
                if "READY" in response.text:
                    return port
            except requests.exceptions.RequestException:
                continue
        return None

    def is_ready(self):
        """Returns True if the scanner is plugged in and recognized."""
        return self.device_port is not None

    def capture_fingerprint(self):
        """Triggers the physical scanner and extracts the biometric key."""
        if not self.is_ready():
            return False, "Scanner not detected. Please ensure it is plugged in."

        # The industry-standard XML command to wake the laser and capture a print
        xml_command = '<PidOptions ver="1.0"><Opts fCount="1" fType="0" iCount="0" pCount="0" format="0" pidVer="2.0" timeout="10000" posh="UNKNOWN" env="P" /></PidOptions>'
        headers = {'Content-Type': 'text/xml'}

        try:
            response = requests.request(
                "CAPTURE", 
                f"http://127.0.0.1:{self.device_port}/rd/capture", 
                data=xml_command, 
                headers=headers,
                timeout=12
            )
            
            return self._parse_payload(response.text)
            
        except Exception as e:
            return False, f"Hardware communication failed: {str(e)}"

    def _parse_payload(self, xml_data):
        """Strips away the XML tags to get the raw biometric data and quality score."""
        try:
            root = ET.fromstring(xml_data)
            
            # 1. Check for hardware errors
            resp = root.find('Resp')
            if resp is None or resp.get('errCode') != "0":
                error_msg = resp.get('errInfo') if resp is not None else "Unknown hardware error."
                return False, f"Scan Failed: {error_msg}"
            
            # 2. Check fingerprint quality (Reject blurry or partial scans)
            quality = int(resp.get('qScore', 0))
            if quality < 60:
                return False, f"Poor scan quality ({quality}%). Please press finger firmly on the glass."
            
            # 3. Extract the encrypted biometric payload
            data_block = root.find('Data')
            if data_block is None or not data_block.text:
                return False, "Biometric data missing from scanner payload."
                
            # Success! Return the extracted biometric text string
            return True, data_block.text
            
        except ET.ParseError:
            return False, "Failed to read scanner data (Corrupt XML)."