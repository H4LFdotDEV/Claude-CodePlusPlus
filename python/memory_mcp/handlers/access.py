# handlers/access.py
# Access request handler for Permission Broker communication
# Allows Memory MCP to request access to paths outside pre-mounted volumes

import json
import logging
import socket
import uuid
from typing import Dict, Any, Literal, Optional

from .base import BaseHandler

logger = logging.getLogger("memory_mcp")

# Default socket path for Permission Broker daemon
DEFAULT_BROKER_SOCKET = "/var/run/claude-broker.sock"

# Container name for identification
DEFAULT_CONTAINER_NAME = "memory-mcp"


class AccessHandler(BaseHandler):
    """Handler for dynamic filesystem access requests via Permission Broker.

    Communicates with the Permission Broker daemon to request access to paths
    outside the container's pre-mounted volumes. The broker prompts the user
    and, if approved, creates the mount and returns the mount path.
    """

    def __init__(
        self,
        *args,
        broker_socket: str = DEFAULT_BROKER_SOCKET,
        container_name: str = DEFAULT_CONTAINER_NAME,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._broker_socket = broker_socket
        self._container_name = container_name
        self._active_mounts: Dict[str, Dict[str, Any]] = {}

    def request_access(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Request access to a path outside pre-mounted volumes.

        Sends a request to the Permission Broker daemon, which prompts the user
        for approval. If approved, returns the mount path where the content is
        accessible within the container.

        Args:
            args: Dict containing:
                - path (required): Host path to request access to
                - reason (required): Human-readable reason for the request
                - access_type (optional): "read" or "write" (default: "read")
                - timeout (optional): Timeout in seconds (default: 30)

        Returns:
            Dict with:
                - approved: Boolean indicating if access was granted
                - mount_path: Path where content is mounted (if approved)
                - error: Error message (if denied or failed)
                - request_id: Unique identifier for this request
        """
        # Validate required parameters
        path = args.get("path")
        if not path or not isinstance(path, str):
            raise ValueError("path is required and must be a non-empty string")

        reason = args.get("reason")
        if not reason or not isinstance(reason, str):
            raise ValueError("reason is required and must be a non-empty string")

        access_type: Literal["read", "write"] = args.get("access_type", "read")
        if access_type not in ("read", "write"):
            raise ValueError("access_type must be 'read' or 'write'")

        timeout = args.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            timeout = 30

        request_id = str(uuid.uuid4())

        logger.info(
            f"Requesting {access_type} access to '{path}' "
            f"(reason: {reason[:50]}..., request_id: {request_id})"
        )

        # Build request payload
        request_payload = {
            "jsonrpc": "2.0",
            "method": "request_access",
            "id": request_id,
            "params": {
                "request_id": request_id,
                "path": path,
                "reason": reason,
                "access_type": access_type,
                "container": self._container_name
            }
        }

        # Send request to broker
        response = self._send_broker_request(request_payload, timeout)

        if response is None:
            logger.warning("Permission Broker not available or connection failed")
            return {
                "approved": False,
                "error": "Permission Broker daemon is not running or not reachable",
                "request_id": request_id,
                "hint": f"Ensure the broker is running and listening on {self._broker_socket}"
            }

        # Parse response
        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            logger.warning(f"Access request denied: {error_msg}")
            return {
                "approved": False,
                "error": error_msg,
                "request_id": request_id
            }

        result = response.get("result", {})
        approved = result.get("approved", False)

        if approved:
            mount_path = result.get("mount_path")
            logger.info(f"Access approved for '{path}' -> '{mount_path}'")

            # Track active mount
            self._active_mounts = {
                **self._active_mounts,
                request_id: {
                    "host_path": path,
                    "mount_path": mount_path,
                    "access_type": access_type,
                    "reason": reason
                }
            }

            return {
                "approved": True,
                "mount_path": mount_path,
                "request_id": request_id,
                "access_type": access_type
            }
        else:
            denial_reason = result.get("reason", "User denied the request")
            logger.info(f"Access denied for '{path}': {denial_reason}")
            return {
                "approved": False,
                "error": denial_reason,
                "request_id": request_id
            }

    def list_active_mounts(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List currently active mounts approved by the Permission Broker.

        Args:
            args: Dict (currently unused, reserved for future filters)

        Returns:
            Dict with:
                - mounts: List of active mount details
                - count: Number of active mounts
                - broker_status: Connection status to broker
        """
        logger.debug("Listing active mounts")

        # Check broker connectivity
        broker_status = self._check_broker_connection()

        # If broker is available, also query for server-side mount state
        server_mounts = None
        if broker_status["connected"]:
            server_mounts = self._query_server_mounts()

        mounts = [
            {
                "request_id": request_id,
                "host_path": mount_info["host_path"],
                "mount_path": mount_info["mount_path"],
                "access_type": mount_info["access_type"],
                "reason": mount_info["reason"]
            }
            for request_id, mount_info in self._active_mounts.items()
        ]

        result = {
            "mounts": mounts,
            "count": len(mounts),
            "broker_status": broker_status
        }

        # Include server-side mount info if available
        if server_mounts is not None:
            result = {**result, "server_mounts": server_mounts}

        return result

    def _send_broker_request(
        self,
        payload: Dict[str, Any],
        timeout: float
    ) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request to the Permission Broker daemon.

        Args:
            payload: JSON-RPC request payload
            timeout: Socket timeout in seconds

        Returns:
            Parsed JSON response, or None if connection failed
        """
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            try:
                sock.connect(self._broker_socket)

                # Send request
                request_data = json.dumps(payload).encode("utf-8")
                sock.sendall(request_data + b"\n")

                # Receive response (read until newline or timeout)
                response_data = self._recv_until_newline(sock)

                if not response_data:
                    logger.warning("Empty response from broker")
                    return None

                return json.loads(response_data.decode("utf-8"))

            finally:
                sock.close()

        except FileNotFoundError:
            logger.debug(f"Broker socket not found: {self._broker_socket}")
            return None
        except ConnectionRefusedError:
            logger.debug("Broker connection refused")
            return None
        except socket.timeout:
            logger.warning("Broker request timed out")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from broker: {e}")
            return None
        except Exception as e:
            logger.error(f"Broker communication error: {e}")
            return None

    def _recv_until_newline(self, sock: socket.socket, max_size: int = 65536) -> bytes:
        """Receive data from socket until newline is encountered.

        Args:
            sock: Connected socket
            max_size: Maximum bytes to receive

        Returns:
            Received data (without trailing newline)
        """
        data = b""
        while len(data) < max_size:
            chunk = sock.recv(1024)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

        # Strip trailing newline
        return data.rstrip(b"\n")

    def _check_broker_connection(self) -> Dict[str, Any]:
        """Check if the Permission Broker daemon is reachable.

        Returns:
            Dict with connection status and details
        """
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2.0)

            try:
                sock.connect(self._broker_socket)
                return {
                    "connected": True,
                    "socket": self._broker_socket
                }
            finally:
                sock.close()

        except FileNotFoundError:
            return {
                "connected": False,
                "error": "Socket not found",
                "socket": self._broker_socket
            }
        except ConnectionRefusedError:
            return {
                "connected": False,
                "error": "Connection refused",
                "socket": self._broker_socket
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "socket": self._broker_socket
            }

    def _query_server_mounts(self) -> Optional[Dict[str, Any]]:
        """Query the broker for server-side mount state.

        Returns:
            Dict with server mount info, or None if query failed
        """
        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "method": "list_mounts",
            "id": request_id,
            "params": {
                "container": self._container_name
            }
        }

        response = self._send_broker_request(payload, timeout=5.0)

        if response is None:
            return None

        if "error" in response:
            return None

        return response.get("result")
