"""Windows DPAPI Credential Vault (Spec §61).

Hardware/OS-backed encrypted secret storage using Windows Data Protection API (DPAPI).
Protects API keys and credentials so they are encrypted with the user's Windows login master key.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import sys
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger
from app.utils.paths import get_paths

log = get_logger("security.vault")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _crypt_protect_data(data: bytes, entropy: bytes = b"JARVIS_VAULT_ENTROPY") -> bytes:
    """Encrypt byte payload using Windows DPAPI."""
    if sys.platform != "win32":
        # Non-windows fallback for testing (base64 with marker)
        return b"NON_WIN_VAULT:" + base64.b64encode(data)

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    entropy_blob = DATA_BLOB(len(entropy), ctypes.cast(ctypes.create_string_buffer(entropy), ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    # CRYPTPROTECT_UI_FORBIDDEN = 0x01
    res = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "JARVIS_CREDENTIAL",
        ctypes.byref(entropy_blob),
        None,
        None,
        0x01,
        ctypes.byref(out_blob),
    )
    if not res:
        raise OSError("DPAPI encryption failed")

    try:
        encrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return encrypted_bytes
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _crypt_unprotect_data(encrypted_data: bytes, entropy: bytes = b"JARVIS_VAULT_ENTROPY") -> bytes:
    """Decrypt byte payload using Windows DPAPI."""
    if sys.platform != "win32":
        if encrypted_data.startswith(b"NON_WIN_VAULT:"):
            return base64.b64decode(encrypted_data[len(b"NON_WIN_VAULT:"):])
        return encrypted_data

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = DATA_BLOB(len(encrypted_data), ctypes.cast(ctypes.create_string_buffer(encrypted_data), ctypes.POINTER(ctypes.c_byte)))
    entropy_blob = DATA_BLOB(len(entropy), ctypes.cast(ctypes.create_string_buffer(entropy), ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    res = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0x01,
        ctypes.byref(out_blob),
    )
    if not res:
        raise OSError("DPAPI decryption failed")

    try:
        decrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return decrypted_bytes
    finally:
        kernel32.LocalFree(out_blob.pbData)


class CredentialVault:
    """Secure encrypted vault stored at data/vault.enc."""

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        self.vault_path = vault_path or (get_paths().data / "vault.enc")

    def set_secret(self, key: str, value: str) -> None:
        """Encrypt and store a secret in the vault."""
        secrets = self._read_vault()
        secrets[key] = value
        self._write_vault(secrets)
        log.info("stored encrypted secret '%s' in DPAPI vault", key)

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve and decrypt a secret from the vault."""
        secrets = self._read_vault()
        return secrets.get(key, default)

    def delete_secret(self, key: str) -> bool:
        """Remove a secret from the vault."""
        secrets = self._read_vault()
        if key in secrets:
            del secrets[key]
            self._write_vault(secrets)
            return True
        return False

    def _read_vault(self) -> dict[str, str]:
        if not self.vault_path.exists():
            return {}
        try:
            raw_encrypted = self.vault_path.read_bytes()
            if not raw_encrypted:
                return {}
            decrypted_json = _crypt_unprotect_data(raw_encrypted).decode("utf-8")
            return json.loads(decrypted_json)
        except Exception as exc:
            log.warning("failed to read credential vault: %s", exc)
            return {}

    def _write_vault(self, secrets: dict[str, str]) -> None:
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(secrets).encode("utf-8")
        encrypted = _crypt_protect_data(payload)
        self.vault_path.write_bytes(encrypted)
