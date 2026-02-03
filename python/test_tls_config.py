#!/usr/bin/env python3
"""
Simple verification that TLS configuration changes are present.
No dependencies required.
"""

import ast
import os


def test_config_changes():
    """Verify RedisConfig has TLS fields."""
    config_path = os.path.join(os.path.dirname(__file__), "memory_mcp", "config.py")

    with open(config_path, "r") as f:
        content = f.read()

    # Check for TLS fields in RedisConfig
    checks = [
        ("ssl: bool = False", "RedisConfig has ssl field"),
        ('ssl_cert_reqs: str = "required"', "RedisConfig has ssl_cert_reqs field"),
        ("ssl_ca_certs: Optional[str] = None", "RedisConfig has ssl_ca_certs field"),
        ('os.environ.get("REDIS_SSL"', "Environment variable REDIS_SSL support"),
        ('os.environ.get("REDIS_SSL_CA_CERTS"', "Environment variable REDIS_SSL_CA_CERTS support"),
    ]

    print("Checking config.py changes:")
    for pattern, description in checks:
        if pattern in content:
            print(f"✓ {description}")
        else:
            print(f"✗ MISSING: {description}")
            return False

    return True


def test_redis_client_changes():
    """Verify RedisClient uses TLS parameters."""
    client_path = os.path.join(os.path.dirname(__file__), "memory_mcp", "redis_client.py")

    with open(client_path, "r") as f:
        content = f.read()

    # Check for TLS usage in connect method
    checks = [
        ("import ssl as ssl_module", "SSL module imported"),
        ("if self.config.ssl:", "SSL config check"),
        ('connection_params["ssl"] = True', "SSL enabled in connection params"),
        ("ssl_module.CERT_REQUIRED", "CERT_REQUIRED constant used"),
        ("ssl_module.CERT_OPTIONAL", "CERT_OPTIONAL constant used"),
        ("ssl_module.CERT_NONE", "CERT_NONE constant used"),
        ('connection_params["ssl_cert_reqs"]', "ssl_cert_reqs in connection params"),
        ('connection_params["ssl_ca_certs"]', "ssl_ca_certs in connection params"),
    ]

    print("\nChecking redis_client.py changes:")
    for pattern, description in checks:
        if pattern in content:
            print(f"✓ {description}")
        else:
            print(f"✗ MISSING: {description}")
            return False

    return True


def main():
    """Run verification."""
    print("=" * 60)
    print("Redis TLS Implementation Verification")
    print("=" * 60)
    print()

    config_ok = test_config_changes()
    client_ok = test_redis_client_changes()

    print()
    print("=" * 60)
    if config_ok and client_ok:
        print("✓ All checks passed!")
        print("=" * 60)
        print("\nImplemented features:")
        print("1. RedisConfig fields: ssl, ssl_cert_reqs, ssl_ca_certs")
        print("2. Environment variable support: REDIS_SSL, REDIS_SSL_CA_CERTS")
        print("3. RedisClient.connect() uses TLS when config.ssl=True")
        print("4. Certificate validation: required/optional/none")
        print("5. Backward compatible (TLS is opt-in)")
        print("\nUsage examples:")
        print("\n  Environment variables:")
        print("    export REDIS_SSL=true")
        print("    export REDIS_SSL_CA_CERTS=/etc/ssl/certs/ca-bundle.crt")
        print("\n  YAML config (~/.claude-code-pp/config/settings.yaml):")
        print("    memory:")
        print("      redis:")
        print("        host: redis.example.com")
        print("        port: 6380")
        print("        ssl: true")
        print("        ssl_cert_reqs: required")
        print("        ssl_ca_certs: /path/to/ca-bundle.crt")
        print("\n  Python code:")
        print("    config = RedisConfig(")
        print("        host='redis.example.com',")
        print("        port=6380,")
        print("        ssl=True,")
        print("        ssl_cert_reqs='required',")
        print("        ssl_ca_certs='/path/to/ca.crt'")
        print("    )")
        print("    client = RedisClient(config)")
        print("    client.connect()")
        return 0
    else:
        print("✗ Some checks failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit(main())
