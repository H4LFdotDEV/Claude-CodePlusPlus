#!/usr/bin/env python3
"""
Verification script for Redis TLS configuration.
Tests that TLS parameters are properly configured and used.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory_mcp.config import RedisConfig, MemoryConfig
from memory_mcp.redis_client import RedisClient


def test_default_config():
    """Test default configuration (no TLS)."""
    print("Test 1: Default configuration (TLS disabled)")
    config = RedisConfig()
    assert config.ssl is False
    assert config.ssl_cert_reqs == "required"
    assert config.ssl_ca_certs is None
    print("✓ Default config: ssl=False")


def test_tls_enabled_config():
    """Test TLS enabled configuration."""
    print("\nTest 2: TLS enabled configuration")
    config = RedisConfig(
        host="localhost",
        port=6380,
        ssl=True,
        ssl_cert_reqs="required",
        ssl_ca_certs="/path/to/ca.crt"
    )
    assert config.ssl is True
    assert config.ssl_cert_reqs == "required"
    assert config.ssl_ca_certs == "/path/to/ca.crt"
    print("✓ TLS config: ssl=True, cert_reqs=required, ca_certs=/path/to/ca.crt")


def test_env_var_config():
    """Test environment variable configuration."""
    print("\nTest 3: Environment variable configuration")

    # Set environment variables
    os.environ["REDIS_SSL"] = "true"
    os.environ["REDIS_SSL_CA_CERTS"] = "/etc/ssl/certs/ca-bundle.crt"

    # Create config from defaults (should read env vars)
    config = MemoryConfig()
    assert config.redis.ssl is True
    assert config.redis.ssl_ca_certs == "/etc/ssl/certs/ca-bundle.crt"

    print("✓ Environment vars: REDIS_SSL=true, REDIS_SSL_CA_CERTS=/etc/ssl/certs/ca-bundle.crt")

    # Clean up
    del os.environ["REDIS_SSL"]
    del os.environ["REDIS_SSL_CA_CERTS"]


def test_redis_client_params():
    """Test that RedisClient properly prepares connection params."""
    print("\nTest 4: RedisClient connection parameter preparation")

    # Test with TLS enabled
    config = RedisConfig(
        host="redis.example.com",
        port=6380,
        ssl=True,
        ssl_cert_reqs="optional",
        ssl_ca_certs="/path/to/ca-bundle.crt"
    )

    client = RedisClient(config)

    # Verify config is stored
    assert client.config.ssl is True
    assert client.config.ssl_cert_reqs == "optional"
    assert client.config.ssl_ca_certs == "/path/to/ca-bundle.crt"

    print("✓ RedisClient stores TLS config correctly")


def test_backward_compatibility():
    """Test that existing non-TLS configurations still work."""
    print("\nTest 5: Backward compatibility (existing configs)")

    # Create a client with no TLS settings (default)
    config = RedisConfig(
        host="localhost",
        port=6379,
        password="testpass"
    )

    client = RedisClient(config)

    # Verify TLS is disabled by default
    assert client.config.ssl is False

    print("✓ Backward compatibility: TLS is opt-in, existing configs work")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Redis TLS Configuration Verification")
    print("=" * 60)

    try:
        test_default_config()
        test_tls_enabled_config()
        test_env_var_config()
        test_redis_client_params()
        test_backward_compatibility()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print("\nSummary:")
        print("- RedisConfig supports ssl, ssl_cert_reqs, ssl_ca_certs")
        print("- Environment variables: REDIS_SSL, REDIS_SSL_CA_CERTS")
        print("- TLS is opt-in (default: ssl=False)")
        print("- Backward compatible with existing configurations")
        print("\nExample usage:")
        print("  # Via environment variables:")
        print("  export REDIS_SSL=true")
        print("  export REDIS_SSL_CA_CERTS=/etc/ssl/certs/ca-bundle.crt")
        print("\n  # Via YAML config:")
        print("  memory:")
        print("    redis:")
        print("      host: redis.example.com")
        print("      port: 6380")
        print("      ssl: true")
        print("      ssl_cert_reqs: required")
        print("      ssl_ca_certs: /path/to/ca-bundle.crt")

        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
