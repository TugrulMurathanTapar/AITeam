"""
Cryptographic Engine for the Multi-AI Orchestrator.

Provides authenticated AES-256-GCM encryption with PBKDF2-HMAC-SHA256 key derivation.
Ensures cross-platform synchronization token compatibility with JavaScript Web Crypto API.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoEngine:
    """
    AES-256-GCM encryption engine with PBKDF2 key derivation.

    Format of encrypted token:
        Base64( Salt [16 bytes] + Nonce [12 bytes] + Ciphertext + Tag [16 bytes] )
    """

    SALT_SIZE: int = 16  # 128-bit salt
    NONCE_SIZE: int = 12  # 96-bit nonce for GCM
    KEY_LENGTH: int = 32  # 256 bits
    ITERATIONS: int = 100_000  # PBKDF2 iterations
    TAG_SIZE: int = 16  # 128-bit GCM authentication tag

    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """
        Derive a 256-bit symmetric encryption key using PBKDF2-HMAC-SHA256.

        Args:
            password: User-provided passphrase.
            salt: 16-byte cryptographic salt.

        Returns:
            32-byte derived symmetric key.

        Raises:
            ValueError: If salt length does not match SALT_SIZE or password is empty.
        """
        if not password:
            raise ValueError("Password cannot be empty.")
        if len(salt) != CryptoEngine.SALT_SIZE:
            raise ValueError(f"Salt must be exactly {CryptoEngine.SALT_SIZE} bytes.")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=CryptoEngine.KEY_LENGTH,
            salt=salt,
            iterations=CryptoEngine.ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8"))

    @staticmethod
    def encrypt(plaintext: str, password: str) -> str:
        """
        Encrypt a plaintext string using AES-256-GCM.

        Generates a fresh random 16-byte salt and 12-byte nonce, derives
        the key using PBKDF2-HMAC-SHA256 (100k iterations), encrypts the plaintext,
        and packs salt + nonce + ciphertext/tag into a Base64-encoded string.

        Args:
            plaintext: Text to encrypt.
            password: User-provided encryption password.

        Returns:
            Base64-encoded string: base64(salt + nonce + ciphertext_with_tag).

        Raises:
            ValueError: If password is empty.
        """
        if not password:
            raise ValueError("Password cannot be empty.")

        salt = os.urandom(CryptoEngine.SALT_SIZE)
        nonce = os.urandom(CryptoEngine.NONCE_SIZE)
        key = CryptoEngine.derive_key(password, salt)

        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)

        payload = salt + nonce + ciphertext
        return base64.b64encode(payload).decode("utf-8")

    @staticmethod
    def decrypt(token: str, password: str) -> str:
        """
        Decrypt a Base64-encoded AES-256-GCM token using a password.

        Extracts salt, nonce, and ciphertext, derives the key with PBKDF2,
        and performs authenticated decryption.

        Args:
            token: Base64-encoded token string.
            password: Passphrase used for decryption.

        Returns:
            Decrypted plaintext string.

        Raises:
            ValueError: If token is malformed, payload too short, or decryption fails.
        """
        if not password:
            raise ValueError("Password cannot be empty.")
        if not token:
            raise ValueError("Token cannot be empty.")

        try:
            payload = base64.b64decode(token.strip())
        except Exception as exc:
            raise ValueError(f"Invalid Base64 token encoding: {exc}") from exc

        min_length = CryptoEngine.SALT_SIZE + CryptoEngine.NONCE_SIZE + CryptoEngine.TAG_SIZE
        if len(payload) < min_length:
            raise ValueError(
                f"Encrypted token too short (length {len(payload)} < minimum {min_length} bytes)."
            )

        salt = payload[:CryptoEngine.SALT_SIZE]
        nonce = payload[CryptoEngine.SALT_SIZE : CryptoEngine.SALT_SIZE + CryptoEngine.NONCE_SIZE]
        ciphertext = payload[CryptoEngine.SALT_SIZE + CryptoEngine.NONCE_SIZE :]

        key = CryptoEngine.derive_key(password, salt)
        aesgcm = AESGCM(key)

        try:
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
            return plaintext_bytes.decode("utf-8")
        except Exception as exc:
            raise ValueError("Decryption failed: incorrect password or corrupted ciphertext.") from exc

    @staticmethod
    def generate_sync_token(
        memory_data: dict[str, Any],
        api_configs: list[dict[str, Any]],
        password: str,
    ) -> str:
        """
        Bundle memory data and API configurations into an encrypted sync token.

        Args:
            memory_data: Full dictionary of memory store data.
            api_configs: List of API configuration dictionaries.
            password: Encryption password.

        Returns:
            Base64-encoded encrypted token string.
        """
        payload = {
            "memory": memory_data,
            "api_configs": api_configs,
        }
        json_str = json.dumps(payload, ensure_ascii=False)
        return CryptoEngine.encrypt(json_str, password)

    @staticmethod
    def parse_sync_token(token: str, password: str) -> dict[str, Any]:
        """
        Decrypt and parse an encrypted sync token back into its structured components.

        Args:
            token: Base64-encoded encrypted sync token.
            password: Password to decrypt the token.

        Returns:
            Dictionary containing 'memory' (dict) and 'api_configs' (list).

        Raises:
            ValueError: If decryption fails or payload structure is invalid.
        """
        json_str = CryptoEngine.decrypt(token, password)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Decrypted payload is not valid JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Decrypted token payload must be a JSON object.")

        if "memory" not in data or "api_configs" not in data:
            raise ValueError(
                "Invalid sync token format: payload must contain 'memory' and 'api_configs' keys."
            )

        return data

    @staticmethod
    def encrypt_file(filepath: str, password: str) -> None:
        """
        Encrypt file contents and write output to filepath + '.enc'.

        Args:
            filepath: Source file path.
            password: Password used for encryption.

        Raises:
            FileNotFoundError: If filepath does not exist.
        """
        src_path = Path(filepath).resolve()
        if not src_path.exists() or not src_path.is_file():
            raise FileNotFoundError(f"Source file not found: {filepath}")

        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        token = CryptoEngine.encrypt(content, password)
        dest_path = Path(f"{filepath}.enc")
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(token)

    @staticmethod
    def decrypt_file(filepath: str, password: str) -> str:
        """
        Read and decrypt an encrypted file (.enc) returning original contents.

        Args:
            filepath: Path to the encrypted file.
            password: Password used for decryption.

        Returns:
            Decrypted plaintext string.

        Raises:
            FileNotFoundError: If filepath does not exist.
        """
        src_path = Path(filepath).resolve()
        if not src_path.exists() or not src_path.is_file():
            raise FileNotFoundError(f"Encrypted file not found: {filepath}")

        with open(src_path, "r", encoding="utf-8") as f:
            token = f.read().strip()

        return CryptoEngine.decrypt(token, password)

    @staticmethod
    async def encrypt_file_async(filepath: str, password: str) -> None:
        """
        Asynchronously encrypt a file and write to filepath + '.enc'.

        Args:
            filepath: Source file path.
            password: Password for encryption.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, CryptoEngine.encrypt_file, filepath, password)

    @staticmethod
    async def decrypt_file_async(filepath: str, password: str) -> str:
        """
        Asynchronously decrypt an encrypted file and return its plaintext contents.

        Args:
            filepath: Path to encrypted file.
            password: Decryption password.

        Returns:
            Decrypted plaintext string.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, CryptoEngine.decrypt_file, filepath, password)
