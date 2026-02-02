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
from typing import Optional, List, Dict, Any
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
        """Ensure backup directory exists."""
        Path(self.backup_path).mkdir(parents=True, exist_ok=True)

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
            if '\x00' in part:
                raise ValueError("Path contains null bytes (path injection detected)")

        base_real = os.path.realpath(base)
        result = os.path.realpath(os.path.join(base_real, *parts))

        # Verify result is within base directory
        if not (result == base_real or result.startswith(base_real + os.sep)):
            raise ValueError(
                f"Path traversal detected: {'/'.join(parts)} escapes base {base}"
            )

        return result

    def _get_backup_dir(self, backup_id: str) -> str:
        """Get directory for a specific backup."""
        return self._safe_join(self.backup_path, backup_id)

    def backup(self, metadata: BackupMetadata) -> bool:
        """Execute local backup."""
        try:
            backup_dir = self._get_backup_dir(metadata.backup_id)
            Path(backup_dir).mkdir(parents=True, exist_ok=True)

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
            metadata.compression_ratio = compressed_size / original_size if original_size > 0 else None

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

            # Handle compressed backup
            if os.path.exists(tar_path):
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(os.path.dirname(backup_dir))
                    logger.info(f"Extracted backup from {tar_path}")

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
                    os.makedirs(os.path.dirname(source_path), exist_ok=True)
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


class BackupManager:
    """Orchestrates backup operations across memory system."""

    def __init__(
        self,
        backup_config: Optional[BackupConfig] = None,
        strategy: Optional[BackupStrategy] = None,
        memory_config: Optional[Dict[str, Any]] = None
    ):
        self.backup_config = backup_config or BackupConfig()
        self.strategy = strategy or LocalBackupStrategy(self.backup_config)
        self.memory_config = memory_config or {}

    def _get_source_paths(self) -> Dict[str, str]:
        """Get all source paths to backup."""
        sources = {}

        if self.backup_config.include_sqlite:
            sources["sqlite"] = self.memory_config.get("sqlite_path", "~/.claude-code-pp/memory/metadata.db")

        if self.backup_config.include_vault:
            sources["vault"] = self.memory_config.get("vault_path", "~/.claude-code-pp/memory/vault")

        return sources

    def backup(self) -> bool:
        """Execute full backup."""
        backup_id = datetime.now(timezone.utc).isoformat().replace(":", "-")
        sources = self._get_source_paths()

        metadata = BackupMetadata(
            backup_id=backup_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            backup_type="full",
            source_paths=sources
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
            "newest_backup": max((b.timestamp for b in backups), default=None)
        }
