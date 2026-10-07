import subprocess
import hashlib
import os

SALT = "LedgerEvents_MasterKey_2026!"

# Tell the app to save the verified license key in a hidden Windows folder
APPDATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'LedgerEventsApp')
LICENSE_FILE = os.path.join(APPDATA_DIR, 'license.key')

def get_current_hardware():
    """Fetches all 3 IDs using modern CIM instances to eliminate boot timeouts."""
    ps_command = (
        "$mb = (Get-CimInstance Win32_BaseBoard).SerialNumber; "
        "$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).ProcessorId; "
        "$hdd = (Get-CimInstance Win32_DiskDrive | Select-Object -First 1).SerialNumber; "
        "Write-Output \"$mb|$cpu|$hdd\""
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            creationflags=0x08000000,
            timeout=8
        )
        val = result.stdout.strip()
        
        if "|" in val:
            mb, cpu, hdd = val.split("|")
            mb_clean = mb.strip() if mb.strip() else "UNKNOWN"
            cpu_clean = cpu.strip() if cpu.strip() else "UNKNOWN"
            hdd_clean = hdd.strip() if hdd.strip() else "UNKNOWN"
            return mb_clean, cpu_clean, hdd_clean
    except Exception as e:
        print(f"Crash during fast hardware fetch: {e}")
        
    return "UNKNOWN", "UNKNOWN", "UNKNOWN"

def hash_hardware(hw_string):
    if not hw_string or hw_string == "UNKNOWN":
        return "0000"
    raw_data = (hw_string + SALT).encode('utf-8')
    return hashlib.md5(raw_data).hexdigest()[:4].upper()

def verify_key(entered_key):
    """The 66% Smart Lock Engine"""
    entered_key = entered_key.strip().upper()
    blocks = entered_key.split('-')
    if len(blocks) != 3:
        return False
        
    mb, cpu, hdd = get_current_hardware()
    
    score = 0
    if hash_hardware(mb) == blocks[0]: score += 1
    if hash_hardware(cpu) == blocks[1]: score += 1
    if hash_hardware(hdd) == blocks[2]: score += 1
    
    # Unlock if 2 out of 3 pieces of hardware match!
    return score >= 2

def save_license(key):
    os.makedirs(APPDATA_DIR, exist_ok=True)
    with open(LICENSE_FILE, 'w') as f:
        f.write(key.strip().upper())

def is_activated():
    """Checks if a valid key is already saved so the user doesn't have to re-type it."""
    if not os.path.exists(LICENSE_FILE):
        return False
    try:
        with open(LICENSE_FILE, 'r') as f:
            saved_key = f.read().strip()
        return verify_key(saved_key)
    except:
        return False