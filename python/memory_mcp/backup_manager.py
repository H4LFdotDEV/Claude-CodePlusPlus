# backup_manager.py
# Backup System for Claude Code++ Memory
# Jeremiah Kroesche | Halfservers LLC
#
# Automated backups of SQLite metadata storage and Obsidian vault
# with local filesystem rotation and cloud backup support

import os
import json
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod
import tarfile

logger = logging.getLogger("memory_mcp.backup")


@dataclass
class BackupMetadata:
    """Metadata for a backup."""

    backup_id: str
    timestamp: str
    backup_type: str  # "full" or "incremental"
    source_paths: Dict[str, str]  # component -> path
    file_hashes: Dict[str, str] = field(default_factory=dict)  # filename -> sha256
    size_bytes: int = 0
    duration_seconds: float = 0.0
    status: str = "pending"  # "success", "failed", "partial"
    error_message: Optional[str] = None
    compressed: bool = False
    compression_ratio: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupMetadata":
        return cls(**data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class BackupConfig:
    """Configuration for backup strategy."""

    retention_days: int = 30
    max_backups: int = 10
    compress: bool = True
    compression_level: int = 6
    verify_integrity: bool = True
    include_sqlite: bool = True
    include_vault: bool = True  # Archive tier - human-readable export


class BackupStrategy(ABC):
    """Abstract strategy for backup operations."""

    def __init__(self, config: BackupConfig):
        self.config = config

    @abstractmethod
    def backup(self, metadata: BackupMetadata) -> bool:
        """Execute backup operation."""
        pass

    @abstractmethod
    def restore(self, backup_id: str) -> bool:
        """Restore from backup."""
        pass

    @abstractmethod
    def list_backups(self) -> List[BackupMetadata]:
        """List available backups."""
        pass

    @abstractmethod
    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        pass

    @abstractmethod
    def verify_backup(self, backup_id: str) -> bool:
        """Verify backup integrity."""
        pass


class LocalBackupStrategy(BackupStrategy):
    """Local filesystem backup strategy with rotation."""

    def __init__(self, config: BackupConfig, backup_path: str = None):
        super().__init__(config)
        self.backup_path = backup_path or "~/.claude-code-pp/backups"
        self.backup_path = os.path.expanduser(self.backup_path)
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        """Ensure backup directory exists with secure permissions."""
        path = Path(self.backup_path)
        path.mkdir(parents=True, exist_ok=True)
        # Ensure secure permissions (owner only)
        os.chmod(path, 0o700)

    def _safe_join(self, base: str, *parts: str) -> str:
        """
        Safely join paths, preventing directory traversal.

        Args:
            base: Base directory that must contain the result
            *parts: Path components to join

        Returns:
            Resolved absolute path within base

        Raises:
            ValueError: If path traversal is detected
        """
        # Validate inputs
        for part in parts:
            if not isinstance(part, str):
                raise TypeError(f"Path component must be string, got {type(part).__name__}")
            if "\x00" in part:
                raise ValueError("Path contains null bytes (path injection detected)")

        base_real = os.path.realpath(base)
        result = os.path.realpath(os.path.join(base_real, *parts))

        # Verify result is within base directory
        if not (result == base_real or result.startswith(base_real + os.sep)):
            raise ValueError(f"Path traversal detected: {'/'.join(parts)} escapes base {base}")

        return result

    def _get_backup_dir(self, backup_id: str) -> str:
        """Get directory for a specific backup."""
        return self._safe_join(self.backup_path, backup_id)

    def _safe_extract_tar(self, tar_path: str, dest_dir: str) -> None:
        """
        Safely extract tarfile, validating all members to prevent path traversal.

        This prevents "Tar Slip" attacks (CVE-2007-4559) where malicious archives
        contain entries with absolute paths or '../' sequences that could write
        files outside the intended destination.

        Args:
            tar_path: Path to the tar.gz file to extract
            dest_dir: Destination directory for extraction

        Raises:
            ValueError: If path traversal or symlink escape is detected
        """
        dest_real = os.path.realpath(dest_dir)
        os.makedirs(dest_real, mode=0o700, exist_ok=True)
        # Ensure secure permissions (owner only)
        os.chmod(dest_real, 0o700)

        with tarfile.open(tar_path, "r:gz") as tar:
            # First pass: validate all members before extracting any
            for member in tar.getmembers():
                # Check for null bytes in member name
                if "\x00" in member.name:
                    raise ValueError(f"Tar member contains null bytes: {member.name}")

                # Resolve the final path
                member_path = os.path.realpath(os.path.join(dest_real, member.name))

                # Verify it stays within destination
                if not (member_path == dest_real or member_path.startswith(dest_real + os.sep)):
                    raise ValueError(f"Tar path traversal detected: {member.name}")

                # Check symlinks don't point outside
                if member.issym() or member.islnk():
                    link_target = member.linkname
                    if os.path.isabs(link_target):
                        link_resolved = os.path.realpath(link_target)
                    else:
                        link_resolved = os.path.realpath(
                            os.path.join(os.path.dirname(member_path), link_target)
                        )
                    if not link_resolved.startswith(dest_real + os.sep):
                        raise ValueError(f"Tar symlink escape detected: {member.name} -> {link_target}")

            # Second pass: extract (all members validated)
            # Use filter='data' on Python 3.12+ for additional safety
            import sys
            if sys.version_info >= (3, 12):
                tar.extractall(dest_real, filter='data')
            else:
                tar.extractall(dest_real)

        logger.info(f"Safely extracted backup from {tar_path} to {dest_real}")

    def backup(self, metadata: BackupMetadata) -> bool:
        """Execute local backup."""
        try:
            backup_dir = self._get_backup_dir(metadata.backup_id)
            path = Path(backup_dir)
            path.mkdir(parents=True, exist_ok=True)
            # Ensure secure permissions (owner only)
            os.chmod(path, 0o700)

            # Copy source files
            for component, source_path in metadata.source_paths.items():
                source_path = os.path.expanduser(source_path)
                if not os.path.exists(source_path):
                    logger.warning(f"Source {component} not found: {source_path}")
                    continue

                dest = self._safe_join(backup_dir, component)
                if os.path.isfile(source_path):
                    shutil.copy2(source_path, dest)
                else:
                    shutil.copytree(source_path, dest, dirs_exist_ok=True)

                # Calculate hash
                file_hash = self._calculate_hash(dest)
                metadata.file_hashes[component] = file_hash

            # Update size
            metadata.size_bytes = self._get_dir_size(backup_dir)

            # Write manifest (before compression, so it's included in tar)
            metadata.status = "success"
            manifest_path = self._safe_join(backup_dir, "manifest.json")
            with open(manifest_path, "w") as f:
                f.write(metadata.to_json())

            # Optionally compress
            if self.config.compress:
                self._compress_backup(backup_dir, metadata)
            self._enforce_retention_policy()
            logger.info(f"Backup {metadata.backup_id} completed successfully")
            return True

        except Exception as e:
            metadata.status = "failed"
            metadata.error_message = str(e)
            logger.error(f"Backup failed: {e}")
            return False

    def _calculate_hash(self, path: str) -> str:
        """Calculate SHA256 hash of file or directory."""
        hash_obj = hashlib.sha256()

        if os.path.isfile(path):
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
        else:
            # For directories, hash all files
            for root, _, files in os.walk(path):
                for file in sorted(files):
                    file_path = self._safe_join(root, file)
                    with open(file_path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_obj.update(chunk)

        return hash_obj.hexdigest()

    def _compress_backup(self, backup_dir: str, metadata: BackupMetadata):
        """Compress backup directory."""
        tar_path = f"{backup_dir}.tar.gz"
        original_size = self._get_dir_size(backup_dir)

        try:
            with tarfile.open(tar_path, "w:gz", compresslevel=self.config.compression_level) as tar:
                tar.add(backup_dir, arcname=os.path.basename(backup_dir))

            compressed_size = os.path.getsize(tar_path)
            metadata.compression_ratio = (
                compressed_size / original_size if original_size > 0 else None
            )

            # Remove original directory
            shutil.rmtree(backup_dir)
            metadata.compressed = True

            logger.info(f"Backup compressed: {original_size} -> {compressed_size} bytes")

        except Exception as e:
            logger.error(f"Compression failed: {e}")
            if os.path.exists(tar_path):
                os.remove(tar_path)
            raise

    def _get_dir_size(self, path: str) -> int:
        """Calculate directory size."""
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                filepath = self._safe_join(dirpath, filename)
                total += os.path.getsize(filepath)
        return total

    def _enforce_retention_policy(self):
        """Enforce retention policy: max backups and age."""
        backups = self._get_all_backups()

        # Sort by timestamp
        backups.sort(key=lambda m: m.timestamp, reverse=True)

        # Remove old backups
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)

        for metadata in backups[:]:
            timestamp = datetime.fromisoformat(metadata.timestamp)

            if len(backups) > self.config.max_backups or timestamp < cutoff_date:
                self.delete_backup(metadata.backup_id)
                backups.remove(metadata)

    def _get_all_backups(self) -> List[BackupMetadata]:
        """Get all backups."""
        backups = []
        for item in os.listdir(self.backup_path):
            try:
                item_path = self._safe_join(self.backup_path, item)
            except ValueError as e:
                logger.warning(f"Skipping suspicious backup entry {item}: {e}")
                continue

            # Handle both uncompressed directories and tar files
            manifest_path = None
            if os.path.isdir(item_path):
                manifest_path = self._safe_join(item_path, "manifest.json")
            elif item.endswith(".tar.gz"):
                # Extract manifest from tar
                try:
                    with tarfile.open(item_path, "r:gz") as tar:
                        manifest_member = None
                        for member in tar.getmembers():
                            if member.name.endswith("manifest.json"):
                                manifest_member = member
                                break

                        if manifest_member:
                            f = tar.extractfile(manifest_member)
                            metadata = BackupMetadata.from_dict(json.loads(f.read()))
                            backups.append(metadata)
                            continue
                except Exception as e:
                    logger.warning(f"Failed to read tar manifest: {e}")
                    continue

            if manifest_path and os.path.exists(manifest_path):
                try:
                    with open(manifest_path) as f:
                        metadata = BackupMetadata.from_dict(json.load(f))
                        backups.append(metadata)
                except Exception as e:
                    logger.warning(f"Failed to read manifest: {e}")

        return backups

    def restore(self, backup_id: str) -> bool:
        """Restore from backup."""
        try:
            backup_dir = self._get_backup_dir(backup_id)
            tar_path = f"{backup_dir}.tar.gz"

            # Handle compressed backup with safe extraction
            if os.path.exists(tar_path):
                self._safe_extract_tar(tar_path, os.path.dirname(backup_dir))

            if not os.path.exists(backup_dir):
                logger.error(f"Backup directory not found: {backup_dir}")
                return False

            # Read manifest
            manifest_path = self._safe_join(backup_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                logger.error(f"Manifest not found in backup")
                return False

            with open(manifest_path) as f:
                metadata = BackupMetadata.from_dict(json.load(f))

            # Restore files
            for component, source_path in metadata.source_paths.items():
                source_path = os.path.expanduser(source_path)
                backup_component_path = self._safe_join(backup_dir, component)

                if not os.path.exists(backup_component_path):
                    logger.warning(f"Component not in backup: {component}")
                    continue

                # Create backup of current file
                if os.path.exists(source_path):
                    backup_suffix = datetime.now(timezone.utc).isoformat().replace(":", "-")
                    if os.path.isfile(source_path):
                        shutil.copy2(source_path, f"{source_path}.pre-restore-{backup_suffix}")
                    else:
                        shutil.copytree(source_path, f"{source_path}.pre-restore-{backup_suffix}")

                # Restore from backup
                if os.path.isfile(backup_component_path):
                    parent_dir = os.path.dirname(source_path)
                    os.makedirs(parent_dir, mode=0o700, exist_ok=True)
                    # Ensure secure permissions (owner only)
                    os.chmod(parent_dir, 0o700)
                    shutil.copy2(backup_component_path, source_path)
                else:
                    shutil.copytree(backup_component_path, source_path, dirs_exist_ok=True)

            logger.info(f"Restored from backup {backup_id}")
            return True

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def list_backups(self) -> List[BackupMetadata]:
        """List available backups."""
        return self._get_all_backups()

    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup."""
        try:
            backup_dir = self._get_backup_dir(backup_id)
            tar_path = f"{backup_dir}.tar.gz"

            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)

            if os.path.exists(tar_path):
                os.remove(tar_path)

            logger.info(f"Deleted backup {backup_id}")
            return True

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def verify_backup(self, backup_id: str) -> bool:
        """Verify backup integrity."""
        try:
            backup_dir = self._get_backup_dir(backup_id)
            tar_path = f"{backup_dir}.tar.gz"

            # Handle compressed backup
            if os.path.exists(tar_path):
                with tarfile.open(tar_path, "r:gz") as tar:
                    # Verify tarfile integrity
                    for member in tar.getmembers():
                        if member.isfile():
                            tar.extractfile(member).read()
                    logger.info(f"Backup {backup_id} tar verification passed")
                    return True

            if not os.path.exists(backup_dir):
                logger.error(f"Backup not found: {backup_id}")
                return False

            # Read manifest and verify hashes
            manifest_path = self._safe_join(backup_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                logger.error(f"Manifest not found")
                return False

            with open(manifest_path) as f:
                metadata = BackupMetadata.from_dict(json.load(f))

            # Verify file hashes
            for component, stored_hash in metadata.file_hashes.items():
                component_path = self._safe_join(backup_dir, component)

                if not os.path.exists(component_path):
                    logger.error(f"Component missing: {component}")
                    return False

                calculated_hash = self._calculate_hash(component_path)
                if calculated_hash != stored_hash:
                    logger.error(f"Hash mismatch for {component}")
                    return False

            logger.info(f"Backup {backup_id} verification passed")
            return True

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False


class CloudBackupStrategy(BackupStrategy):
    """Cloud backup strategy (S3/GCS pattern - placeholder for future implementation)."""

    def __init__(self, config: BackupConfig, cloud_config: Dict[str, Any]):
        super().__init__(config)
        self.cloud_config = cloud_config
        self._validate_config()

    def _validate_config(self):
        """Validate cloud configuration."""
        required = ["provider", "bucket"]
        for key in required:
            if key not in self.cloud_config:
                raise ValueError(f"Missing required config: {key}")

    def backup(self, metadata: BackupMetadata) -> bool:
        """Upload backup to cloud (S3/GCS) - not implemented."""
        logger.info(f"Cloud backup not yet implemented for {self.cloud_config['provider']}")
        return False

    def restore(self, backup_id: str) -> bool:
        """Download and restore from cloud - not implemented."""
        logger.info("Cloud restore not yet implemented")
        return False

    def list_backups(self) -> List[BackupMetadata]:
        """List cloud backups - not implemented."""
        logger.info("Cloud listing not yet implemented")
        return []

    def delete_backup(self, backup_id: str) -> bool:
        """Delete cloud backup - not implemented."""
        logger.info("Cloud delete not yet implemented")
        return False

    def verify_backup(self, backup_id: str) -> bool:
        """Verify cloud backup - not implemented."""
        logger.info("Cloud verification not yet implemented")
        return False


# Check for optional encryption dependencies
try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False


KEYRING_SERVICE = "claude-code-pp"
KEYRING_KEY_NAME = "backup-encryption-key"
KEYRING_NONCE_COUNTER = "backup-nonce-counter"


class EncryptedBackupManager:
    """Backup manager with encryption support using system keyring.

    Uses ChaCha20-Poly1305 for encryption with key stored in system keyring.
    Provides the same interface as BackupManager for backwards compatibility.
    """

    def __init__(
        self,
        backup_config: Optional[BackupConfig] = None,
        backup_path: Optional[str] = None,
        base_manager: Optional["BackupManager"] = None,
    ):
        """Initialize encrypted backup manager.

        Args:
            backup_config: Backup configuration
            backup_path: Path to store encrypted backups
            base_manager: Optional BackupManager for delegation

        Raises:
            ImportError: If cryptography or keyring packages are not installed
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography package required for encrypted backups. "
                "Install with: pip install cryptography"
            )
        if not KEYRING_AVAILABLE:
            raise ImportError(
                "keyring package required for encrypted backups. "
                "Install with: pip install keyring"
            )

        self.backup_config = backup_config or BackupConfig()
        self.backup_path = backup_path or "~/.claude-code-pp/backups/encrypted"
        self.backup_path = os.path.expanduser(self.backup_path)
        os.makedirs(self.backup_path, mode=0o700, exist_ok=True)
        # Ensure secure permissions (owner only)
        os.chmod(self.backup_path, 0o700)

        self._base = base_manager
        self._key = self._get_or_create_key()
        logger.info(f"Encrypted backup manager initialized: {self.backup_path}")

    def _get_or_create_key(self) -> bytes:
        """Get encryption key from system keyring, or create if not exists.

        Returns:
            32-byte encryption key
        """
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
        if stored:
            logger.debug("Loaded encryption key from system keyring")
            return bytes.fromhex(stored)

        # Generate new 256-bit key and store in keyring
        key = os.urandom(32)
        keyring.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, key.hex())
        logger.info("Generated new encryption key and stored in system keyring")
        return key

    def _get_and_increment_counter(self) -> int:
        """Get and atomically increment the nonce counter from keyring.

        Returns:
            Current counter value (before increment)
        """
        counter_str = keyring.get_password(KEYRING_SERVICE, KEYRING_NONCE_COUNTER)
        if counter_str:
            counter = int(counter_str)
        else:
            counter = 0

        # Increment and store, wrapping at 32-bit max
        next_counter = (counter + 1) % (2**32)
        keyring.set_password(KEYRING_SERVICE, KEYRING_NONCE_COUNTER, str(next_counter))
        return counter

    def _get_unique_nonce(self) -> bytes:
        """Generate a unique 12-byte nonce using hybrid approach.

        Combines:
        - 4 bytes: Unix timestamp (seconds) for temporal uniqueness
        - 4 bytes: Monotonic counter for collision resistance
        - 4 bytes: Random bytes for additional entropy

        This ensures uniqueness even if:
        - System clock is wrong (counter protects)
        - RNG has low entropy (timestamp + counter protect)
        - Many backups created quickly (timestamp + counter protect)

        Returns:
            12-byte unique nonce
        """
        import struct
        import time

        # 4 bytes: timestamp (seconds since epoch)
        timestamp = int(time.time())
        timestamp_bytes = struct.pack(">I", timestamp)

        # 4 bytes: monotonic counter
        counter = self._get_and_increment_counter()
        counter_bytes = struct.pack(">I", counter)  # Counter already wrapped in _get_and_increment_counter

        # 4 bytes: random
        random_bytes = os.urandom(4)

        nonce = timestamp_bytes + counter_bytes + random_bytes
        return nonce

    def _encrypt(self, data: bytes) -> Tuple[bytes, bytes]:
        """Encrypt data using ChaCha20-Poly1305.

        Args:
            data: Raw data to encrypt

        Returns:
            Tuple of (nonce, ciphertext) where ciphertext includes authentication tag
        """
        nonce = self._get_unique_nonce()
        cipher = ChaCha20Poly1305(self._key)
        ciphertext = cipher.encrypt(nonce, data, None)
        return nonce, ciphertext

    def _decrypt(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """Decrypt data using ChaCha20-Poly1305.

        Args:
            nonce: 12-byte nonce
            ciphertext: Encrypted data with authentication tag

        Returns:
            Decrypted plaintext

        Raises:
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        cipher = ChaCha20Poly1305(self._key)
        return cipher.decrypt(nonce, ciphertext, None)

    def backup(
        self,
        data: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        filename_prefix: str = "backup",
    ) -> str:
        """Create an encrypted backup.

        Args:
            data: Raw backup data to encrypt
            metadata: Optional metadata dict (stored in header)
            filename_prefix: Prefix for backup filename

        Returns:
            Path to the encrypted backup file

        Raises:
            Exception: If backup creation fails
        """
        try:
            # Encrypt the data
            nonce, ciphertext = self._encrypt(data)

            # Create backup file with metadata header
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.enc"
            backup_path = os.path.join(self.backup_path, filename)

            # File format: [4-byte header len][JSON header][12-byte nonce][ciphertext]
            header = {
                "version": 1,
                "algorithm": "chacha20-poly1305",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {},
            }
            header_bytes = json.dumps(header).encode("utf-8")
            header_len = len(header_bytes).to_bytes(4, "big")

            with open(backup_path, "wb") as f:
                f.write(header_len)
                f.write(header_bytes)
                f.write(nonce)
                f.write(ciphertext)

            size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            logger.info(f"Encrypted backup created: {filename} ({size_mb:.2f} MB)")
            return backup_path

        except Exception as e:
            logger.error(f"Encrypted backup failed: {e}")
            raise

    def restore(self, backup_path: str) -> Tuple[bytes, Dict[str, Any]]:
        """Restore from an encrypted backup.

        Args:
            backup_path: Path to the encrypted backup file

        Returns:
            Tuple of (decrypted data, metadata dict)

        Raises:
            ValueError: If backup format is invalid or unsupported
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        try:
            with open(backup_path, "rb") as f:
                # Read header
                header_len = int.from_bytes(f.read(4), "big")
                header_bytes = f.read(header_len)
                header = json.loads(header_bytes.decode("utf-8"))

                # Verify algorithm
                if header.get("algorithm") != "chacha20-poly1305":
                    raise ValueError(f"Unsupported algorithm: {header.get('algorithm')}")

                # Read nonce and ciphertext
                nonce = f.read(12)
                ciphertext = f.read()

            # Decrypt
            data = self._decrypt(nonce, ciphertext)

            logger.info(f"Encrypted backup restored: {os.path.basename(backup_path)}")
            return data, header.get("metadata", {})

        except Exception as e:
            logger.error(f"Encrypted restore failed: {e}")
            raise

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available encrypted backups.

        Returns:
            List of backup info dicts with filename, path, size, modified time
        """
        backups = []
        for filename in os.listdir(self.backup_path):
            if filename.endswith(".enc"):
                path = os.path.join(self.backup_path, filename)
                stat = os.stat(path)

                # Try to read metadata from header
                metadata = None
                try:
                    with open(path, "rb") as f:
                        header_len = int.from_bytes(f.read(4), "big")
                        header_bytes = f.read(header_len)
                        header = json.loads(header_bytes.decode("utf-8"))
                        metadata = header.get("metadata")
                except Exception:
                    pass  # Ignore errors reading metadata

                backups.append(
                    {
                        "filename": filename,
                        "path": path,
                        "size_bytes": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "modified": stat.st_mtime,
                        "created_at": header.get("created_at") if metadata is not None else None,
                        "metadata": metadata,
                    }
                )

        return sorted(backups, key=lambda x: x["modified"], reverse=True)

    def delete_backup(self, backup_path: str) -> bool:
        """Delete an encrypted backup.

        Args:
            backup_path: Path to backup file to delete

        Returns:
            True if successful
        """
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
                logger.info(f"Deleted encrypted backup: {os.path.basename(backup_path)}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return False

    def rotate_key(self, re_encrypt_existing: bool = True) -> bool:
        """Rotate the encryption key.

        Args:
            re_encrypt_existing: If True, re-encrypt all existing backups with new key

        Returns:
            True if successful

        Raises:
            RuntimeError: If key rotation fails
        """
        old_key = self._key
        new_key = os.urandom(32)

        if re_encrypt_existing:
            try:
                # Re-encrypt all existing backups
                for backup in self.list_backups():
                    # Decrypt with old key
                    self._key = old_key
                    data, metadata = self.restore(backup["path"])

                    # Encrypt with new key
                    self._key = new_key
                    nonce, ciphertext = self._encrypt(data)

                    # Overwrite the file
                    header = {
                        "version": 1,
                        "algorithm": "chacha20-poly1305",
                        "created_at": metadata.get(
                            "created_at", datetime.now(timezone.utc).isoformat()
                        ),
                        "metadata": metadata,
                    }
                    header_bytes = json.dumps(header).encode("utf-8")
                    header_len = len(header_bytes).to_bytes(4, "big")

                    with open(backup["path"], "wb") as f:
                        f.write(header_len)
                        f.write(header_bytes)
                        f.write(nonce)
                        f.write(ciphertext)

                    logger.info(f"Re-encrypted backup: {backup['filename']}")

            except Exception as e:
                # Restore old key on failure
                self._key = old_key
                raise RuntimeError(f"Key rotation failed: {e}")

        # Store new key in keyring
        keyring.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, new_key.hex())
        self._key = new_key

        logger.info("Encryption key rotated successfully")
        return True

    @staticmethod
    def is_available() -> bool:
        """Check if encrypted backups are available.

        Returns:
            True if both cryptography and keyring packages are installed
        """
        return CRYPTO_AVAILABLE and KEYRING_AVAILABLE


class BackupManager:
    """Orchestrates backup operations across memory system."""

    def __init__(
        self,
        backup_config: Optional[BackupConfig] = None,
        strategy: Optional[BackupStrategy] = None,
        memory_config: Optional[Dict[str, Any]] = None,
    ):
        self.backup_config = backup_config or BackupConfig()
        self.strategy = strategy or LocalBackupStrategy(self.backup_config)
        self.memory_config = memory_config or {}

    def _get_source_paths(self) -> Dict[str, str]:
        """Get all source paths to backup."""
        sources = {}

        if self.backup_config.include_sqlite:
            sources["sqlite"] = self.memory_config.get(
                "sqlite_path", "~/.claude-code-pp/memory/metadata.db"
            )

        if self.backup_config.include_vault:
            sources["vault"] = self.memory_config.get(
                "vault_path", "~/.claude-code-pp/memory/vault"
            )

        return sources

    def backup(self) -> bool:
        """Execute full backup."""
        backup_id = datetime.now(timezone.utc).isoformat().replace(":", "-")
        sources = self._get_source_paths()

        metadata = BackupMetadata(
            backup_id=backup_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            backup_type="full",
            source_paths=sources,
        )

        start_time = datetime.now(timezone.utc)

        # Execute backup
        success = self.strategy.backup(metadata)

        end_time = datetime.now(timezone.utc)
        metadata.duration_seconds = (end_time - start_time).total_seconds()

        # Verify if configured
        if success and self.backup_config.verify_integrity:
            success = self.strategy.verify_backup(backup_id)

        return success

    def restore_latest(self) -> bool:
        """Restore from latest backup."""
        backups = self.strategy.list_backups()

        if not backups:
            logger.error("No backups available")
            return False

        # Sort by timestamp, get latest
        latest = max(backups, key=lambda m: m.timestamp)

        logger.info(f"Restoring from backup {latest.backup_id} ({latest.timestamp})")
        return self.strategy.restore(latest.backup_id)

    def restore(self, backup_id: str) -> bool:
        """Restore specific backup."""
        return self.strategy.restore(backup_id)

    def list_backups(self) -> List[BackupMetadata]:
        """List all backups."""
        return self.strategy.list_backups()

    def delete_backup(self, backup_id: str) -> bool:
        """Delete backup."""
        return self.strategy.delete_backup(backup_id)

    def verify_backup(self, backup_id: str) -> bool:
        """Verify backup integrity."""
        return self.strategy.verify_backup(backup_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get backup statistics."""
        backups = self.strategy.list_backups()

        total_size = sum(b.size_bytes for b in backups)
        successful = sum(1 for b in backups if b.status == "success")

        return {
            "total_backups": len(backups),
            "successful_backups": successful,
            "failed_backups": len(backups) - successful,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_backup": min((b.timestamp for b in backups), default=None),
            "newest_backup": max((b.timestamp for b in backups), default=None),
        }
