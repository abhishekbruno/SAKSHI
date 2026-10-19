"""
MOD-11: Key Provider Abstraction & Implementations for SAKSHI Investigation Platform.
Phase 3 — Security & Integrity.

Architectural Design:
    Enforces per-case key isolation for AES-256-GCM authenticated encryption at rest.
    Keeps the implementation honest by providing a pluggable IKeyProvider interface:

                    MOD-11
                       │
             ┌─────────┴─────────┐
             │                   │
       Key Provider         AES-256-GCM
             │                   │
       ┌─────┴─────┐             │
       │           │             │
    Dev/Test    HSM/KMS          │
    LocalKey    Production       │
       │        (Documented)     │
       └──────────┬──────────────┘
                  ▼
          Encrypted Evidence

Implementations:
    - IKeyProvider: Abstract interface defining the key provider contract.
    - LocalKeyProvider: Case-isolated key management for Dev/Test/Staging.
      Persists 256-bit keys in case-isolated storage with restricted permissions
      and enforces strict cross-case access prevention.
    - ProductionHSMKMSProvider: Documented architectural contract for AWS KMS,
      GCP Cloud KMS, HashiCorp Vault Transit, or PKCS#11 HSM integration.
"""
import os
import stat
import json
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse

from app.core.errors import (
    CaseKeyIsolationException,
    KeyProviderException,
)

logger = logging.getLogger("sakshi.mod11.key_provider")

KEY_STORAGE_DIR_NAME = ".keys"
KEY_VERSION_DEFAULT = "v1"


# ═══════════════════════════════════════════════════════════════════════════
# IKeyProvider — Pluggable Key Management Interface
# ═══════════════════════════════════════════════════════════════════════════

class IKeyProvider(ABC):
    """
    Abstract interface for SAKSHI Key Providers.
    Guarantees per-case key isolation and secure 256-bit symmetric key handling.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Canonical identifier of the key provider backend."""
        pass

    @abstractmethod
    def get_or_create_case_key(
        self,
        case_id: str,
        case_workspace_path: Optional[str] = None,
        key_version: str = KEY_VERSION_DEFAULT,
    ) -> Tuple[bytes, str]:
        """
        Retrieves or generates an isolated 256-bit (32 bytes) symmetric key for a specific case.

        Returns:
            Tuple[bytes, str]: (raw_key_bytes: 32 bytes, canonical_key_reference_uri)
        """
        pass

    @abstractmethod
    def get_case_key(
        self,
        key_reference: str,
        case_id: str,
        case_workspace_path: Optional[str] = None,
    ) -> bytes:
        """
        Retrieves the 256-bit key bytes for the specified key reference.

        Strict Security Invariant:
            Must verify that key_reference belongs strictly to case_id.
            Attempts to access a key for Case A using Case B's ID must raise
            CaseKeyIsolationException.
        """
        pass

    @abstractmethod
    def get_key_reference(self, case_id: str, key_version: str = KEY_VERSION_DEFAULT) -> str:
        """Construct the canonical key reference URI for a case."""
        pass

    @abstractmethod
    def rotate_case_key(
        self,
        case_id: str,
        case_workspace_path: Optional[str] = None,
    ) -> Tuple[bytes, str]:
        """
        Generates a new key version for the case (cryptographic key rotation).
        Returns: (new_key_bytes, new_key_reference_uri)
        """
        pass


# ═══════════════════════════════════════════════════════════════════════════
# LocalKeyProvider — Phase 3 Local / Dev / Test Implementation
# ═══════════════════════════════════════════════════════════════════════════

class LocalKeyProvider(IKeyProvider):
    """
    Case-isolated Local Key Provider for development, testing, and single-host deployments.

    Security Properties:
        1. Per-Case Key Isolation: Every case receives a cryptographically distinct
           256-bit AES key. Keys are never shared across cases.
        2. Boundary Enforcement: Cross-case key retrieval raises CaseKeyIsolationException.
        3. Secure Storage: Keys are persisted into `<case_workspace>/.keys/` with
           read-only / restricted file permissions (0600).
        4. In-Memory Thread-Safe Cache: Facilitates high-performance lookups and
           supports in-memory test environments where workspaces are ephemeral.
    """

    BACKEND_NAME: str = "LOCAL_DEV_KEY_PROVIDER"
    URI_SCHEME: str = "localkms"

    def __init__(self, fallback_storage_root: Optional[str] = None):
        self._fallback_storage_root = fallback_storage_root or os.path.join(
            os.path.dirname(__file__), "..", "..", ".keystore"
        )
        # Thread-safe in-memory cache: {case_id: {key_reference: key_bytes}}
        self._cache: Dict[str, Dict[str, bytes]] = {}
        # Key version counter per case: {case_id: latest_version_int}
        self._case_versions: Dict[str, int] = {}
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return self.BACKEND_NAME

    def get_key_reference(self, case_id: str, key_version: str = KEY_VERSION_DEFAULT) -> str:
        """
        Generates the canonical URI for a case key:
        localkms://cases/<case_id>/keys/aes-256-<key_version>
        """
        return f"{self.URI_SCHEME}://cases/{case_id}/keys/aes-256-{key_version}"

    @classmethod
    def parse_case_id_from_reference(cls, key_reference: str) -> str:
        """
        Extract the case_id encoded within a canonical key reference URI.
        Expected format: localkms://cases/<case_id>/keys/<key_name>
        """
        if not key_reference.startswith(f"{cls.URI_SCHEME}://"):
            raise KeyProviderException(
                f"Invalid key reference scheme. Expected '{cls.URI_SCHEME}://', got '{key_reference}'."
            )
        # Parse path
        parsed = urlparse(key_reference)
        # netloc may be 'cases' and path is '/<case_id>/keys/...'
        if parsed.netloc == "cases":
            parts = parsed.path.strip("/").split("/")
            if parts and parts[0]:
                return parts[0]
        # In case URI parsed as path: localkms://cases/...
        path_clean = key_reference[len(cls.URI_SCHEME) + 3:]
        parts = path_clean.split("/")
        if len(parts) >= 2 and parts[0] == "cases":
            return parts[1]
        raise KeyProviderException(
            f"Cannot extract case_id from key reference '{key_reference}'."
        )

    def get_or_create_case_key(
        self,
        case_id: str,
        case_workspace_path: Optional[str] = None,
        key_version: str = KEY_VERSION_DEFAULT,
    ) -> Tuple[bytes, str]:
        """
        Retrieves or generates an isolated 256-bit symmetric key for case_id.
        """
        if not case_id:
            raise KeyProviderException("case_id must be provided for key derivation.")

        key_ref = self.get_key_reference(case_id, key_version)

        with self._lock:
            # 1. Check cache first
            if case_id in self._cache and key_ref in self._cache[case_id]:
                return self._cache[case_id][key_ref], key_ref

            # 2. Check disk storage if workspace provided
            key_bytes = self._load_key_from_disk(case_id, key_version, case_workspace_path)
            if key_bytes:
                if case_id not in self._cache:
                    self._cache[case_id] = {}
                self._cache[case_id][key_ref] = key_bytes
                return key_bytes, key_ref

            # 3. Generate a new cryptographically secure 256-bit (32 bytes) key
            new_key = os.urandom(32)

            # 4. Save to disk if workspace path is available
            self._save_key_to_disk(case_id, key_version, new_key, case_workspace_path)

            # 5. Populate cache
            if case_id not in self._cache:
                self._cache[case_id] = {}
            self._cache[case_id][key_ref] = new_key
            self._case_versions[case_id] = max(self._case_versions.get(case_id, 1), 1)

            logger.info("Generated new isolated 256-bit key for case '%s' (ref: %s)", case_id, key_ref)
            return new_key, key_ref

    def get_case_key(
        self,
        key_reference: str,
        case_id: str,
        case_workspace_path: Optional[str] = None,
    ) -> bytes:
        """
        Retrieves key bytes for key_reference, enforcing case boundary isolation.
        """
        # Strict Isolation Check: Verify key_reference belongs to the requested case
        ref_case_id = self.parse_case_id_from_reference(key_reference)
        if ref_case_id != case_id:
            logger.error(
                "CROSS-CASE KEY ACCESS ATTEMPT DETECTED: key_ref '%s' belongs to case '%s', "
                "but access was requested for case '%s'. Access denied.",
                key_reference, ref_case_id, case_id
            )
            raise CaseKeyIsolationException(
                f"Cross-case key access denied: key reference '{key_reference}' belongs to "
                f"case '{ref_case_id}', but access was requested for case '{case_id}'."
            )

        with self._lock:
            # 1. Check cache
            if case_id in self._cache and key_reference in self._cache[case_id]:
                return self._cache[case_id][key_reference]

            # 2. Check disk
            key_version = key_reference.split("-")[-1] if "-" in key_reference else KEY_VERSION_DEFAULT
            key_bytes = self._load_key_from_disk(case_id, key_version, case_workspace_path)
            if key_bytes:
                if case_id not in self._cache:
                    self._cache[case_id] = {}
                self._cache[case_id][key_reference] = key_bytes
                return key_bytes

        raise KeyProviderException(
            f"Key with reference '{key_reference}' not found for case '{case_id}'."
        )

    def rotate_case_key(
        self,
        case_id: str,
        case_workspace_path: Optional[str] = None,
    ) -> Tuple[bytes, str]:
        """
        Creates a new sequential key version for the case (e.g. v2, v3).
        """
        with self._lock:
            current_ver = self._case_versions.get(case_id, 1)
            next_ver_int = current_ver + 1
            next_version = f"v{next_ver_int}"
            self._case_versions[case_id] = next_ver_int

        new_key, key_ref = self.get_or_create_case_key(
            case_id=case_id,
            case_workspace_path=case_workspace_path,
            key_version=next_version,
        )
        logger.info("Rotated key for case '%s' to version '%s' (ref: %s)", case_id, next_version, key_ref)
        return new_key, key_ref

    # ─── Internal File Storage Helpers ─────────────────────────────────────

    def _resolve_keys_dir(self, case_id: str, case_workspace_path: Optional[str]) -> str:
        if case_workspace_path and os.path.exists(case_workspace_path):
            keys_dir = os.path.join(case_workspace_path, KEY_STORAGE_DIR_NAME)
        else:
            keys_dir = os.path.join(self._fallback_storage_root, case_id, KEY_STORAGE_DIR_NAME)
        os.makedirs(keys_dir, exist_ok=True)
        return keys_dir

    def _load_key_from_disk(
        self,
        case_id: str,
        key_version: str,
        case_workspace_path: Optional[str]
    ) -> Optional[bytes]:
        try:
            keys_dir = self._resolve_keys_dir(case_id, case_workspace_path)
            key_file = os.path.join(keys_dir, f"aes256_{key_version}.key")
            if os.path.exists(key_file):
                with open(key_file, "rb") as f:
                    data = f.read()
                if len(data) == 32:
                    return data
        except Exception as e:
            logger.warning("Could not read key from disk for case %s: %s", case_id, e)
        return None

    def _save_key_to_disk(
        self,
        case_id: str,
        key_version: str,
        key_bytes: bytes,
        case_workspace_path: Optional[str]
    ) -> None:
        try:
            keys_dir = self._resolve_keys_dir(case_id, case_workspace_path)
            key_file = os.path.join(keys_dir, f"aes256_{key_version}.key")
            # Write key with restricted permissions
            with open(key_file, "wb") as f:
                f.write(key_bytes)
            try:
                os.chmod(key_file, stat.S_IREAD | stat.S_IWRITE)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Could not persist key to disk for case %s: %s", case_id, e)


# ═══════════════════════════════════════════════════════════════════════════
# ProductionHSMKMSProvider — Documented Production Architecture
# ═══════════════════════════════════════════════════════════════════════════

class ProductionHSMKMSProvider(IKeyProvider):
    """
    Documented Architectural Contract for Production Cloud KMS / Hardware Security Module.

    Production Architecture:
        1. Cloud KMS Customer Master Key (CMK):
           A dedicated CMK / Key Encryption Key (KEK) is configured per tenant or per case.
        2. Cryptographic Envelope Encryption:
           - For encryption: Calls `kms:GenerateDataKey(KeyId=case_kek, KeySpec='AES_256')`.
             KMS returns plaintext Data Encryption Key (DEK) and ciphertext (encrypted DEK).
             The plaintext DEK encrypts the evidence payload in-memory and is securely wiped.
             The encrypted DEK is stored alongside the evidence metadata.
           - For decryption: Calls `kms:Decrypt(CiphertextBlob=encrypted_dek, EncryptionContext={'case_id': case_id})`.
             KMS validates the Encryption Context before returning the plaintext DEK.
        3. Hardware Security Module (HSM):
           In air-gapped on-premise deployments, integration occurs via PKCS#11
           with FIPS 140-2 Level 3 validated hardware modules.

    Development Safeguard:
        Raises KeyProviderException if instantiated without production credentials/config,
        instructing engineers to use LocalKeyProvider for dev/test workflows.
    """

    BACKEND_NAME: str = "PRODUCTION_HSM_KMS"
    URI_SCHEME: str = "kms"

    def __init__(
        self,
        kms_endpoint: Optional[str] = None,
        key_arn_template: Optional[str] = None,
        allow_mock: bool = False,
    ):
        self.kms_endpoint = kms_endpoint
        self.key_arn_template = key_arn_template or "arn:aws:kms:region:account:key/cases/{case_id}"
        self.allow_mock = allow_mock
        if not kms_endpoint and not allow_mock:
            logger.info(
                "ProductionHSMKMSProvider registered as architectural contract. "
                "Active provider in this environment is LocalKeyProvider."
            )

    @property
    def provider_name(self) -> str:
        return self.BACKEND_NAME

    def get_key_reference(self, case_id: str, key_version: str = KEY_VERSION_DEFAULT) -> str:
        return f"{self.URI_SCHEME}://sakshi/cases/{case_id}/keys/kek-{key_version}"

    def get_or_create_case_key(
        self,
        case_id: str,
        case_workspace_path: Optional[str] = None,
        key_version: str = KEY_VERSION_DEFAULT,
    ) -> Tuple[bytes, str]:
        if not self.allow_mock:
            raise KeyProviderException(
                "ProductionHSMKMSProvider requires live cloud KMS or HSM credentials. "
                "In local, test, or staging environments, configure LocalKeyProvider."
            )
        # Mock mode for testing architectural failovers
        mock_key = os.urandom(32)
        ref = self.get_key_reference(case_id, key_version)
        return mock_key, ref

    def get_case_key(
        self,
        key_reference: str,
        case_id: str,
        case_workspace_path: Optional[str] = None,
    ) -> bytes:
        if not self.allow_mock:
            raise KeyProviderException(
                "ProductionHSMKMSProvider requires live cloud KMS or HSM credentials. "
                "In local, test, or staging environments, configure LocalKeyProvider."
            )
        return os.urandom(32)

    def rotate_case_key(
        self,
        case_id: str,
        case_workspace_path: Optional[str] = None,
    ) -> Tuple[bytes, str]:
        if not self.allow_mock:
            raise KeyProviderException("ProductionHSMKMSProvider key rotation requires live KMS connection.")
        return os.urandom(32), self.get_key_reference(case_id, "v2")
