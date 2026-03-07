"""
Encrypted API Key Storage for NexusRetail OS.

Uses cryptography.fernet.Fernet (AES-128-CBC + HMAC-SHA256) to persist
API keys to {BASE_DIR}/keys.enc — industry-standard, audited encryption.
"""

import os
import json
import base64
import hashlib
import platform
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("NexusAI_Backend")

_SALT = b"NexusRetailOS_KeyStore_v1"
_ITERATIONS = 480_000  # OWASP recommendation for PBKDF2-SHA256


def _get_machine_id() -> bytes:
    """Stable machine identifier, consistent across all processes."""
    if os.path.exists("/etc/machine-id"):
        with open("/etc/machine-id", "r") as f:
            return f.read().strip().encode()

    if os.name == "nt":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            return val.encode()
        except Exception:
            pass

    return f"{platform.node()}-{platform.system()}-{platform.machine()}".encode()


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the machine ID using PBKDF2."""
    raw_key = hashlib.pbkdf2_hmac("sha256", _get_machine_id(), _SALT, _ITERATIONS)
    # Fernet requires a 32-byte url-safe base64-encoded key
    fernet_key = base64.urlsafe_b64encode(raw_key[:32])
    return Fernet(fernet_key)


def save_keys(keys: dict, base_dir: str) -> bool:
    """Encrypt and save API keys to {base_dir}/keys.enc"""
    try:
        f = _get_fernet()
        token = f.encrypt(json.dumps(keys).encode("utf-8"))

        file_path = os.path.join(base_dir, "keys.enc")
        with open(file_path, "wb") as fp:
            fp.write(token)

        logger.info("🔐 API keys encrypted and saved to disk.")
        return True
    except Exception as e:
        logger.error(f"Failed to save encrypted keys: {e}")
        return False


def load_keys(base_dir: str) -> dict:
    """Decrypt and return API keys from {base_dir}/keys.enc"""
    file_path = os.path.join(base_dir, "keys.enc")

    if not os.path.exists(file_path):
        return {}

    try:
        f = _get_fernet()
        with open(file_path, "rb") as fp:
            token = fp.read()
        plaintext = f.decrypt(token)
        logger.info("🔓 API keys loaded from encrypted store.")
        return json.loads(plaintext.decode("utf-8"))
    except InvalidToken:
        logger.warning("🔒 Encrypted key file failed integrity check. Ignoring.")
        return {}
    except Exception as e:
        logger.error(f"Failed to load encrypted keys: {e}")
        return {}
