"""Example usage of EncryptedBackupManager.

This demonstrates how to use the encrypted backup system with system keyring
for key management.
"""

import os
import json
from memory_mcp.backup_manager import EncryptedBackupManager, BackupConfig


def main():
    """Run encrypted backup examples."""

    # Check if encryption is available
    if not EncryptedBackupManager.is_available():
        print("Error: Encrypted backups require 'cryptography' and 'keyring' packages")
        print("Install with: pip install cryptography keyring")
        return

    print("=== Encrypted Backup Manager Example ===\n")

    # Create manager with custom config
    config = BackupConfig(
        retention_days=30,
        max_backups=10,
        compress=False,  # EncryptedBackupManager handles its own format
        verify_integrity=True
    )

    backup_dir = os.path.expanduser("~/.claude-code-pp/examples/encrypted_backups")
    manager = EncryptedBackupManager(
        backup_config=config,
        backup_path=backup_dir
    )

    print(f"Backup directory: {backup_dir}")
    print(f"Encryption available: {EncryptedBackupManager.is_available()}\n")

    # Example 1: Backup some data
    print("1. Creating encrypted backup...")
    test_data = b"This is sensitive data that needs encryption.\nLine 2\nLine 3"
    metadata = {
        "type": "example",
        "component": "test_db",
        "version": "1.0"
    }

    backup_path = manager.backup(
        test_data,
        metadata=metadata,
        filename_prefix="example_backup"
    )
    print(f"   Backup created: {os.path.basename(backup_path)}")
    print(f"   Size: {os.path.getsize(backup_path)} bytes\n")

    # Example 2: List backups
    print("2. Listing backups...")
    backups = manager.list_backups()
    for backup in backups:
        print(f"   - {backup['filename']}")
        print(f"     Size: {backup['size_mb']} MB")
        print(f"     Created: {backup.get('created_at', 'N/A')}")
        if backup.get('metadata'):
            print(f"     Metadata: {json.dumps(backup['metadata'], indent=8)}")
        print()

    # Example 3: Restore backup
    print("3. Restoring backup...")
    restored_data, restored_metadata = manager.restore(backup_path)
    print(f"   Restored {len(restored_data)} bytes")
    print(f"   Data: {restored_data.decode()}")
    print(f"   Metadata: {json.dumps(restored_metadata, indent=6)}\n")

    # Example 4: Verify roundtrip
    print("4. Verifying data integrity...")
    if restored_data == test_data:
        print("   ✓ Data integrity verified!\n")
    else:
        print("   ✗ Data mismatch!\n")

    # Example 5: Multiple backups
    print("5. Creating multiple backups...")
    for i in range(3):
        data = f"Backup number {i}".encode()
        path = manager.backup(data, filename_prefix=f"multi_backup_{i}")
        print(f"   Created: {os.path.basename(path)}")
    print()

    # Example 6: List all backups
    print("6. All backups:")
    all_backups = manager.list_backups()
    print(f"   Total: {len(all_backups)} backups")
    for backup in all_backups:
        print(f"   - {backup['filename']} ({backup['size_bytes']} bytes)")
    print()

    # Example 7: Key rotation (optional - usually done periodically)
    print("7. Key rotation example (without re-encryption)...")
    print("   Note: Key rotation with re-encryption is recommended but slower")
    print("   Skipping for this example to keep it fast\n")
    # Uncomment to test key rotation:
    # manager.rotate_key(re_encrypt_existing=False)
    # print("   ✓ Key rotated successfully\n")

    # Example 8: Clean up (delete backups)
    print("8. Cleaning up...")
    for backup in all_backups:
        manager.delete_backup(backup['path'])
        print(f"   Deleted: {backup['filename']}")
    print()

    print("=== Example Complete ===")
    print("\nKey points:")
    print("- Encryption key is stored securely in system keyring")
    print("- Uses ChaCha20-Poly1305 for authenticated encryption")
    print("- Backup format includes metadata header + nonce + ciphertext")
    print("- Automatic key generation on first use")
    print("- Support for key rotation with optional re-encryption")


if __name__ == "__main__":
    main()
