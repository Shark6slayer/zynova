import os
import time
import socket
import logging
import asyncio
from typing import Tuple, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.security_logger import log_security_event

logger = logging.getLogger("super_ai.scanner")

QUARANTINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage", "quarantine"))
os.makedirs(QUARANTINE_DIR, exist_ok=True)

# Standard EICAR test signature for testing malware detection without real viruses
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
SIMULATED_MALWARE_BYTE = b"MALWARE_TEST_SIGNATURE"

class ClamAVScanResult:
    def __init__(self, is_clean: bool, threat_name: Optional[str] = None, error: Optional[str] = None):
        self.is_clean = is_clean
        self.threat_name = threat_name
        self.error = error

async def _scan_with_clamd_tcp(file_path: str, host: str, port: int, timeout: float) -> ClamAVScanResult:
    """
    Connects to clamd daemon via TCP and uses INSTREAM protocol to scan file bytes.
    Protocol:
      Send: zINSTREAM\0
      Send chunks: <4-byte big-endian length><chunk>
      Send: <0000>
      Receive: stream: OK  OR  stream: <threat_name> FOUND
    """
    loop = asyncio.get_running_loop()

    def sync_scan():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            s.sendall(b"zINSTREAM\0")

            with open(file_path, "rb") as f:
                while chunk := f.read(32768):
                    chunk_len = len(chunk).to_bytes(4, byteorder="big")
                    s.sendall(chunk_len + chunk)
            s.sendall((0).to_bytes(4, byteorder="big"))

            response = s.recv(4096).decode("utf-8", errors="ignore")
            if "OK" in response:
                return ClamAVScanResult(is_clean=True)
            elif "FOUND" in response:
                threat = response.split("FOUND")[0].replace("stream:", "").strip()
                return ClamAVScanResult(is_clean=False, threat_name=threat)
            else:
                return ClamAVScanResult(is_clean=False, error=f"Unexpected clamd response: {response}")
        except Exception as e:
            return ClamAVScanResult(is_clean=False, error=str(e))
        finally:
            try:
                s.close()
            except Exception:
                pass

    return await loop.run_in_executor(None, sync_scan)

def _scan_with_mock_dev(file_path: str) -> ClamAVScanResult:
    """
    Deterministic development scanner adapter.
    Scans for EICAR test string and simulated malware test byte sequences.
    """
    try:
        with open(file_path, "rb") as f:
            content = f.read(65536)
            if EICAR_SIGNATURE in content or SIMULATED_MALWARE_BYTE in content:
                return ClamAVScanResult(is_clean=False, threat_name="Win.Test.EICAR_HDB-1")
        return ClamAVScanResult(is_clean=True)
    except Exception as e:
        return ClamAVScanResult(is_clean=False, error=str(e))

async def scan_quarantined_media(quarantine_path: str, original_filename: str) -> Tuple[bool, str]:
    """
    Scans a quarantined media file before promoting to public storage.
    Fails closed in production if ClamAV daemon is unreachable.
    Returns (is_clean, detail_message).
    """
    if not os.path.exists(quarantine_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File missing in quarantine")

    # 1. Real ClamAV scanner if configured
    if settings.CLAMAV_HOST:
        logger.info(f"Scanning file via ClamAV ({settings.CLAMAV_HOST}:{settings.CLAMAV_PORT})...")
        res = await _scan_with_clamd_tcp(
            quarantine_path,
            settings.CLAMAV_HOST,
            settings.CLAMAV_PORT,
            settings.CLAMAV_TIMEOUT_SECONDS
        )
        if res.error:
            logger.error(f"ClamAV scan error: {res.error}")
            if settings.ENVIRONMENT.lower() == "production" and settings.CLAMAV_REQUIRED_IN_PRODUCTION:
                log_security_event(
                    event_code="MALWARE_SCAN_UNAVAILABLE",
                    action="scan_media",
                    status="BLOCKED",
                    resource=original_filename,
                    details={"error": res.error}
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Malware scanning service unavailable. Upload rejected for security."
                )
            logger.warning("Falling back to local development mock scanner due to ClamAV connection failure.")
        else:
            if not res.is_clean:
                log_security_event(
                    event_code="MALWARE_SCAN_REJECTED",
                    action="scan_media",
                    status="BLOCKED",
                    resource=original_filename,
                    details={"threat": res.threat_name, "scanner": "ClamAV"}
                )
                return False, f"Malware detected ({res.threat_name}). File rejected."
            
            log_security_event(
                event_code="MALWARE_SCAN_SUCCESS",
                action="scan_media",
                status="SUCCESS",
                resource=original_filename,
                details={"scanner": "ClamAV"}
            )
            return True, "CLEAN"

    # 2. Production requirement check: if in production and ClamAV is missing
    if settings.ENVIRONMENT.lower() == "production" and settings.CLAMAV_REQUIRED_IN_PRODUCTION:
        log_security_event(
            event_code="MALWARE_SCAN_UNCONFIGURED",
            action="scan_media",
            status="BLOCKED",
            resource=original_filename,
            details={"reason": "ClamAV required in production"}
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Malware scanning service is not configured. Uploads are disabled in production."
        )

    # 3. Development mock scanner adapter
    mock_res = _scan_with_mock_dev(quarantine_path)
    if not mock_res.is_clean:
        log_security_event(
            event_code="MALWARE_SCAN_REJECTED",
            action="scan_media",
            status="BLOCKED",
            resource=original_filename,
            details={"threat": mock_res.threat_name, "scanner": "MockDevScanner"}
        )
        return False, f"Malware detected ({mock_res.threat_name}). File rejected."

    log_security_event(
        event_code="MALWARE_SCAN_SUCCESS",
        action="scan_media",
        status="SUCCESS",
        resource=original_filename,
        details={"scanner": "MockDevScanner"}
    )
    return True, "CLEAN"
