#!/usr/bin/env python3
"""
Permission Broker Daemon

A host-side daemon that handles access requests from sandboxed containers.
Validates requests against deny lists, queues for user approval, and creates
temporary mounts with TTL on approval.

Requires Python 3.10+

Usage:
    python permission-broker.py [--socket PATH] [--config PATH] [--debug]
"""

import argparse
import asyncio
import datetime
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

# Constants
DEFAULT_SOCKET_PATH = "/var/run/claude-broker.sock"
DEFAULT_CONFIG_PATH = Path.home() / ".claude-code-pp" / "config" / "permissions.yaml"
DEFAULT_LOG_PATH = Path.home() / ".claude-code-pp" / "logs" / "access-requests.jsonl"
DEFAULT_MOUNT_BASE = Path("/tmp/claude-mounts")
DEFAULT_TTL_SECONDS = 3600  # 1 hour

# Hardcoded deny list - these paths are NEVER accessible
HARDCODED_DENY_PATTERNS = [
    r"^~?/?\.ssh(/|$)",
    r"^~?/?\.aws(/|$)",
    r"^~?/?\.gnupg(/|$)",
    r"^~?/?\.gpg(/|$)",
    r"\.env$",
    r"\.env\.",
    r"/\.env$",
    r"/\.env\.",
    r"secrets?\.ya?ml$",
    r"secrets?\.json$",
    r"credentials\.json$",
    r"\.pem$",
    r"\.key$",
    r"id_rsa",
    r"id_ed25519",
    r"id_ecdsa",
    r"id_dsa",
    r"\.kube/config",
    r"\.docker/config\.json",
    r"\.netrc",
    r"\.npmrc",
    r"\.pypirc",
]


class RequestStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    AUTO_DENIED = "auto_denied"


class AccessLevel(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


@dataclass
class AccessRequest:
    """Represents a request for file/directory access from a container."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    container_id: str = ""
    container_name: str = ""
    requested_path: str = ""
    resolved_path: str = ""
    access_level: str = "read"
    reason: str = ""
    status: str = RequestStatus.PENDING.value
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    mount_path: str = ""
    expires_at: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""
    deny_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccessRequest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BrokerConfig:
    """Configuration for the permission broker."""

    socket_path: str = DEFAULT_SOCKET_PATH
    log_path: str = str(DEFAULT_LOG_PATH)
    mount_base: str = str(DEFAULT_MOUNT_BASE)
    default_ttl: int = DEFAULT_TTL_SECONDS
    ntfy_topic: str = ""
    ntfy_server: str = "https://ntfy.sh"
    auto_approve_patterns: list[str] = field(default_factory=list)
    additional_deny_patterns: list[str] = field(default_factory=list)
    max_pending_requests: int = 100
    cleanup_interval: int = 300  # 5 minutes

    @classmethod
    def from_yaml(cls, path: Path) -> "BrokerConfig":
        """Load configuration from YAML file."""
        try:
            import yaml
        except ImportError:
            print("Warning: PyYAML not installed, using defaults", file=sys.stderr)
            return cls()

        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        broker_config = data.get("permission_broker", {})
        return cls(
            socket_path=broker_config.get("socket_path", DEFAULT_SOCKET_PATH),
            log_path=broker_config.get("log_path", str(DEFAULT_LOG_PATH)),
            mount_base=broker_config.get("mount_base", str(DEFAULT_MOUNT_BASE)),
            default_ttl=broker_config.get("default_ttl", DEFAULT_TTL_SECONDS),
            ntfy_topic=broker_config.get("ntfy_topic", ""),
            ntfy_server=broker_config.get("ntfy_server", "https://ntfy.sh"),
            auto_approve_patterns=broker_config.get("auto_approve_patterns", []),
            additional_deny_patterns=broker_config.get("additional_deny_patterns", []),
            max_pending_requests=broker_config.get("max_pending_requests", 100),
            cleanup_interval=broker_config.get("cleanup_interval", 300),
        )


class AuditLogger:
    """Append-only audit logger for access requests."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, request: AccessRequest, event: str, details: dict[str, Any] | None = None) -> None:
        """Log an event for a request."""
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": event,
            "request_id": request.id,
            "request": request.to_dict(),
            "details": details or {},
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_recent(self, count: int = 50) -> list[dict[str, Any]]:
        """Get recent log entries."""
        if not self.log_path.exists():
            return []

        entries = []
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return entries[-count:]


class PathValidator:
    """Validates paths against deny and allow lists."""

    def __init__(self, config: BrokerConfig):
        self.config = config
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        all_deny = HARDCODED_DENY_PATTERNS + self.config.additional_deny_patterns
        self.deny_patterns = [re.compile(p, re.IGNORECASE) for p in all_deny]
        self.auto_approve_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.auto_approve_patterns
        ]

    def resolve_path(self, path: str) -> Path:
        """Resolve path to absolute, expanding ~ and symlinks."""
        expanded = os.path.expanduser(path)
        resolved = Path(expanded).resolve()
        return resolved

    def is_denied(self, path: str) -> tuple[bool, str]:
        """Check if path matches any deny pattern."""
        # Check both original and resolved paths
        paths_to_check = [path]

        try:
            resolved = str(self.resolve_path(path))
            paths_to_check.append(resolved)
        except (OSError, ValueError):
            pass

        for check_path in paths_to_check:
            for pattern in self.deny_patterns:
                if pattern.search(check_path):
                    return True, f"Path matches deny pattern: {pattern.pattern}"

        return False, ""

    def should_auto_approve(self, path: str) -> bool:
        """Check if path matches auto-approve patterns."""
        try:
            resolved = str(self.resolve_path(path))
        except (OSError, ValueError):
            resolved = path

        for pattern in self.auto_approve_patterns:
            if pattern.search(path) or pattern.search(resolved):
                return True

        return False

    def validate_path_exists(self, path: str) -> tuple[bool, str]:
        """Check if path exists and is accessible."""
        try:
            resolved = self.resolve_path(path)
            if not resolved.exists():
                return False, f"Path does not exist: {resolved}"
            return True, str(resolved)
        except (OSError, PermissionError) as e:
            return False, f"Cannot access path: {e}"


class NotificationService:
    """Sends notifications for pending requests."""

    def __init__(self, config: BrokerConfig):
        self.config = config

    async def notify(self, request: AccessRequest) -> bool:
        """Send notification about pending request."""
        message = self._format_message(request)

        # Always print to console
        print(f"\n{'='*60}")
        print("ACCESS REQUEST PENDING")
        print(f"{'='*60}")
        print(message)
        print(f"{'='*60}")
        print(f"Approve: claude-broker approve {request.id}")
        print(f"Deny:    claude-broker deny {request.id}")
        print(f"{'='*60}\n")

        # Send to ntfy if configured
        if self.config.ntfy_topic:
            await self._send_ntfy(request, message)

        return True

    def _format_message(self, request: AccessRequest) -> str:
        """Format request as human-readable message."""
        return (
            f"Container: {request.container_name or request.container_id}\n"
            f"Path: {request.requested_path}\n"
            f"Resolved: {request.resolved_path}\n"
            f"Access: {request.access_level}\n"
            f"Reason: {request.reason}\n"
            f"Request ID: {request.id}"
        )

    async def _send_ntfy(self, request: AccessRequest, message: str) -> None:
        """Send notification via ntfy.sh."""
        try:
            import aiohttp
        except ImportError:
            print("Warning: aiohttp not installed, skipping ntfy notification", file=sys.stderr)
            return

        url = f"{self.config.ntfy_server}/{self.config.ntfy_topic}"
        headers = {
            "Title": "Claude Permission Request",
            "Priority": "high",
            "Tags": "warning,lock",
            "Actions": (
                f"view, Approve, {self.config.ntfy_server}/approve/{request.id}; "
                f"view, Deny, {self.config.ntfy_server}/deny/{request.id}"
            ),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=message, headers=headers) as resp:
                    if resp.status != 200:
                        print(f"Warning: ntfy notification failed: {resp.status}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: ntfy notification error: {e}", file=sys.stderr)


class MountManager:
    """Manages temporary bind mounts for approved requests."""

    def __init__(self, config: BrokerConfig):
        self.config = config
        self.mount_base = Path(config.mount_base)
        self.active_mounts: dict[str, AccessRequest] = {}

    def _ensure_mount_base(self) -> None:
        """Ensure mount base directory exists."""
        self.mount_base.mkdir(parents=True, exist_ok=True)

    def create_mount(self, request: AccessRequest) -> tuple[bool, str]:
        """Create a temporary mount for approved request."""
        self._ensure_mount_base()

        # Generate unique mount point
        mount_hash = hashlib.sha256(
            f"{request.id}{request.resolved_path}".encode()
        ).hexdigest()[:12]
        mount_point = self.mount_base / mount_hash

        try:
            # Create mount directory
            mount_point.mkdir(exist_ok=True)

            # Create symlink (safer than actual bind mount for user-level daemon)
            source = Path(request.resolved_path)
            target = mount_point / source.name

            if target.exists() or target.is_symlink():
                target.unlink()

            target.symlink_to(source)

            # Record active mount
            request.mount_path = str(target)
            request.expires_at = (
                datetime.datetime.now(datetime.timezone.utc) +
                datetime.timedelta(seconds=request.ttl_seconds)
            ).isoformat()

            self.active_mounts[request.id] = request

            return True, str(target)

        except (OSError, PermissionError) as e:
            return False, f"Failed to create mount: {e}"

    def remove_mount(self, request_id: str) -> bool:
        """Remove a mount for a request."""
        if request_id not in self.active_mounts:
            return False

        request = self.active_mounts[request_id]
        try:
            mount_path = Path(request.mount_path)
            if mount_path.is_symlink():
                mount_path.unlink()

            # Try to remove parent directory if empty
            parent = mount_path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()

            del self.active_mounts[request_id]
            return True

        except (OSError, PermissionError):
            return False

    def cleanup_expired(self) -> list[str]:
        """Remove all expired mounts."""
        now = datetime.datetime.now(datetime.timezone.utc)
        expired = []

        for request_id, request in list(self.active_mounts.items()):
            if request.expires_at:
                expires = datetime.datetime.fromisoformat(request.expires_at)
                if now >= expires:
                    if self.remove_mount(request_id):
                        expired.append(request_id)

        return expired

    def list_active(self) -> list[AccessRequest]:
        """List all active mounts."""
        return list(self.active_mounts.values())


class PermissionBroker:
    """Main permission broker daemon."""

    def __init__(self, config: BrokerConfig, debug: bool = False):
        self.config = config
        self.debug = debug
        self.validator = PathValidator(config)
        self.logger = AuditLogger(Path(config.log_path))
        self.notifier = NotificationService(config)
        self.mount_manager = MountManager(config)
        self.pending_requests: dict[str, AccessRequest] = {}
        self.server: asyncio.Server | None = None
        self._running = False

    def _debug(self, message: str) -> None:
        """Print debug message if debug mode is enabled."""
        if self.debug:
            print(f"[DEBUG] {message}", file=sys.stderr)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle a client connection."""
        try:
            data = await reader.read(65536)
            if not data:
                return

            try:
                message = json.loads(data.decode())
            except json.JSONDecodeError as e:
                await self._send_response(writer, {"error": f"Invalid JSON: {e}"})
                return

            self._debug(f"Received: {message}")

            command = message.get("command")
            response = await self._dispatch_command(command, message)

            await self._send_response(writer, response)

        except Exception as e:
            self._debug(f"Error handling client: {e}")
            await self._send_response(writer, {"error": str(e)})
        finally:
            writer.close()
            await writer.wait_closed()

    async def _send_response(self, writer: asyncio.StreamWriter, response: dict[str, Any]) -> None:
        """Send JSON response to client."""
        data = json.dumps(response).encode() + b"\n"
        writer.write(data)
        await writer.drain()

    async def _dispatch_command(self, command: str | None, message: dict[str, Any]) -> dict[str, Any]:
        """Dispatch command to appropriate handler."""
        handlers = {
            "request_access": self._handle_request_access,
            "approve": self._handle_approve,
            "deny": self._handle_deny,
            "status": self._handle_status,
            "list_pending": self._handle_list_pending,
            "list_active": self._handle_list_active,
            "revoke": self._handle_revoke,
            "health": self._handle_health,
        }

        handler = handlers.get(command)
        if not handler:
            return {"error": f"Unknown command: {command}"}

        return await handler(message)

    async def _handle_request_access(self, message: dict[str, Any]) -> dict[str, Any]:
        """Handle access request from container."""
        # Check pending limit
        if len(self.pending_requests) >= self.config.max_pending_requests:
            return {"error": "Too many pending requests"}

        # Create request object
        request = AccessRequest(
            container_id=message.get("container_id", "unknown"),
            container_name=message.get("container_name", ""),
            requested_path=message.get("path", ""),
            access_level=message.get("access_level", "read"),
            reason=message.get("reason", ""),
            ttl_seconds=message.get("ttl", self.config.default_ttl),
        )

        # Validate path is not empty
        if not request.requested_path:
            return {"error": "Path is required"}

        # Check deny list first
        denied, deny_reason = self.validator.is_denied(request.requested_path)
        if denied:
            request.status = RequestStatus.AUTO_DENIED.value
            request.deny_reason = deny_reason
            self.logger.log(request, "auto_denied", {"reason": deny_reason})
            return {
                "status": "denied",
                "reason": deny_reason,
                "request_id": request.id,
            }

        # Resolve and validate path
        exists, resolved_or_error = self.validator.validate_path_exists(request.requested_path)
        if not exists:
            return {"error": resolved_or_error}

        request.resolved_path = resolved_or_error

        # Check auto-approve
        if self.validator.should_auto_approve(request.requested_path):
            request.status = RequestStatus.APPROVED.value
            request.reviewed_by = "auto"
            request.reviewed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

            success, mount_or_error = self.mount_manager.create_mount(request)
            if not success:
                return {"error": mount_or_error}

            self.logger.log(request, "auto_approved")
            return {
                "status": "approved",
                "request_id": request.id,
                "mount_path": request.mount_path,
                "expires_at": request.expires_at,
            }

        # Queue for manual approval
        self.pending_requests[request.id] = request
        self.logger.log(request, "pending")

        # Send notification
        await self.notifier.notify(request)

        return {
            "status": "pending",
            "request_id": request.id,
            "message": "Request queued for approval",
        }

    async def _handle_approve(self, message: dict[str, Any]) -> dict[str, Any]:
        """Handle approval of pending request."""
        request_id = message.get("request_id")
        if not request_id:
            return {"error": "request_id is required"}

        request = self.pending_requests.get(request_id)
        if not request:
            return {"error": f"No pending request with ID: {request_id}"}

        # Update request status
        request.status = RequestStatus.APPROVED.value
        request.reviewed_by = message.get("reviewed_by", "user")
        request.reviewed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Custom TTL if provided
        if "ttl" in message:
            request.ttl_seconds = message["ttl"]

        # Create mount
        success, mount_or_error = self.mount_manager.create_mount(request)
        if not success:
            return {"error": mount_or_error}

        # Remove from pending
        del self.pending_requests[request_id]

        self.logger.log(request, "approved")

        return {
            "status": "approved",
            "request_id": request_id,
            "mount_path": request.mount_path,
            "expires_at": request.expires_at,
        }

    async def _handle_deny(self, message: dict[str, Any]) -> dict[str, Any]:
        """Handle denial of pending request."""
        request_id = message.get("request_id")
        if not request_id:
            return {"error": "request_id is required"}

        request = self.pending_requests.get(request_id)
        if not request:
            return {"error": f"No pending request with ID: {request_id}"}

        # Update request status
        request.status = RequestStatus.DENIED.value
        request.deny_reason = message.get("reason", "Denied by user")
        request.reviewed_by = message.get("reviewed_by", "user")
        request.reviewed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Remove from pending
        del self.pending_requests[request_id]

        self.logger.log(request, "denied")

        return {
            "status": "denied",
            "request_id": request_id,
            "reason": request.deny_reason,
        }

    async def _handle_status(self, message: dict[str, Any]) -> dict[str, Any]:
        """Get status of a request."""
        request_id = message.get("request_id")
        if not request_id:
            return {"error": "request_id is required"}

        # Check pending
        if request_id in self.pending_requests:
            request = self.pending_requests[request_id]
            return {"status": request.status, "request": request.to_dict()}

        # Check active mounts
        if request_id in self.mount_manager.active_mounts:
            request = self.mount_manager.active_mounts[request_id]
            return {
                "status": request.status,
                "request": request.to_dict(),
                "mount_path": request.mount_path,
                "expires_at": request.expires_at,
            }

        return {"error": f"Request not found: {request_id}"}

    async def _handle_list_pending(self, message: dict[str, Any]) -> dict[str, Any]:
        """List all pending requests."""
        return {
            "pending": [r.to_dict() for r in self.pending_requests.values()]
        }

    async def _handle_list_active(self, message: dict[str, Any]) -> dict[str, Any]:
        """List all active mounts."""
        return {
            "active": [r.to_dict() for r in self.mount_manager.list_active()]
        }

    async def _handle_revoke(self, message: dict[str, Any]) -> dict[str, Any]:
        """Revoke an active mount."""
        request_id = message.get("request_id")
        if not request_id:
            return {"error": "request_id is required"}

        if request_id not in self.mount_manager.active_mounts:
            return {"error": f"No active mount for request: {request_id}"}

        request = self.mount_manager.active_mounts[request_id]
        if self.mount_manager.remove_mount(request_id):
            request.status = RequestStatus.EXPIRED.value
            self.logger.log(request, "revoked")
            return {"status": "revoked", "request_id": request_id}

        return {"error": "Failed to revoke mount"}

    async def _handle_health(self, message: dict[str, Any]) -> dict[str, Any]:
        """Health check."""
        return {
            "status": "healthy",
            "pending_count": len(self.pending_requests),
            "active_mounts": len(self.mount_manager.active_mounts),
            "uptime": "running",
        }

    async def _cleanup_task(self) -> None:
        """Periodic cleanup of expired mounts."""
        while self._running:
            await asyncio.sleep(self.config.cleanup_interval)
            expired = self.mount_manager.cleanup_expired()
            if expired:
                self._debug(f"Cleaned up {len(expired)} expired mounts")
                for request_id in expired:
                    self.logger.log(
                        AccessRequest(id=request_id),
                        "expired",
                        {"reason": "TTL exceeded"}
                    )

    async def start(self) -> None:
        """Start the broker daemon."""
        socket_path = Path(self.config.socket_path)

        # Remove existing socket
        if socket_path.exists():
            socket_path.unlink()

        # Ensure parent directory exists
        socket_path.parent.mkdir(parents=True, exist_ok=True)

        self.server = await asyncio.start_unix_server(
            self.handle_client,
            path=str(socket_path)
        )

        # Set socket permissions (user only)
        os.chmod(socket_path, 0o600)

        self._running = True
        print(f"Permission Broker listening on {socket_path}")

        # Start cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_task())

        try:
            async with self.server:
                await self.server.serve_forever()
        finally:
            self._running = False
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

    async def stop(self) -> None:
        """Stop the broker daemon."""
        self._running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Cleanup all active mounts
        for request_id in list(self.mount_manager.active_mounts.keys()):
            self.mount_manager.remove_mount(request_id)

        # Remove socket
        socket_path = Path(self.config.socket_path)
        if socket_path.exists():
            socket_path.unlink()


async def send_command(socket_path: str, command: dict[str, Any]) -> dict[str, Any]:
    """Send a command to the broker and return response."""
    reader, writer = await asyncio.open_unix_connection(socket_path)

    try:
        writer.write(json.dumps(command).encode())
        await writer.drain()

        data = await reader.read(65536)
        return json.loads(data.decode())
    finally:
        writer.close()
        await writer.wait_closed()


async def cli_main(args: argparse.Namespace) -> int:
    """CLI entry point for commands."""
    socket_path = args.socket

    if args.action == "start":
        config = BrokerConfig.from_yaml(Path(args.config))
        config.socket_path = socket_path

        broker = PermissionBroker(config, debug=args.debug)

        # Handle signals
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(broker.stop()))

        await broker.start()
        return 0

    # All other commands require connecting to running broker
    try:
        if args.action == "approve":
            response = await send_command(socket_path, {
                "command": "approve",
                "request_id": args.request_id,
                "ttl": args.ttl,
            })

        elif args.action == "deny":
            response = await send_command(socket_path, {
                "command": "deny",
                "request_id": args.request_id,
                "reason": args.reason,
            })

        elif args.action == "list":
            if args.active:
                response = await send_command(socket_path, {"command": "list_active"})
            else:
                response = await send_command(socket_path, {"command": "list_pending"})

        elif args.action == "status":
            response = await send_command(socket_path, {
                "command": "status",
                "request_id": args.request_id,
            })

        elif args.action == "revoke":
            response = await send_command(socket_path, {
                "command": "revoke",
                "request_id": args.request_id,
            })

        elif args.action == "health":
            response = await send_command(socket_path, {"command": "health"})

        else:
            print(f"Unknown action: {args.action}", file=sys.stderr)
            return 1

        print(json.dumps(response, indent=2))
        return 0 if "error" not in response else 1

    except FileNotFoundError:
        print(f"Error: Broker not running (socket not found: {socket_path})", file=sys.stderr)
        return 1
    except ConnectionRefusedError:
        print(f"Error: Cannot connect to broker at {socket_path}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Permission Broker - Host-side daemon for container access requests"
    )
    parser.add_argument(
        "--socket", "-s",
        default=DEFAULT_SOCKET_PATH,
        help=f"Unix socket path (default: {DEFAULT_SOCKET_PATH})"
    )
    parser.add_argument(
        "--config", "-c",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"Config file path (default: {DEFAULT_CONFIG_PATH})"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug output"
    )

    subparsers = parser.add_subparsers(dest="action", help="Command to execute")

    # Start daemon
    start_parser = subparsers.add_parser("start", help="Start the broker daemon")

    # Approve request
    approve_parser = subparsers.add_parser("approve", help="Approve a pending request")
    approve_parser.add_argument("request_id", help="Request ID to approve")
    approve_parser.add_argument("--ttl", type=int, help="Override TTL in seconds")

    # Deny request
    deny_parser = subparsers.add_parser("deny", help="Deny a pending request")
    deny_parser.add_argument("request_id", help="Request ID to deny")
    deny_parser.add_argument("--reason", "-r", default="", help="Reason for denial")

    # List requests
    list_parser = subparsers.add_parser("list", help="List requests")
    list_parser.add_argument("--active", "-a", action="store_true", help="Show active mounts instead of pending")

    # Status
    status_parser = subparsers.add_parser("status", help="Get request status")
    status_parser.add_argument("request_id", help="Request ID to check")

    # Revoke
    revoke_parser = subparsers.add_parser("revoke", help="Revoke an active mount")
    revoke_parser.add_argument("request_id", help="Request ID to revoke")

    # Health
    health_parser = subparsers.add_parser("health", help="Health check")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        return 1

    return asyncio.run(cli_main(args))


if __name__ == "__main__":
    sys.exit(main())
