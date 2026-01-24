"""Custom exceptions for the application.

Provides standardized error handling across the application.
"""
from typing import Optional, Any
from fastapi import HTTPException, status


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }


class GameException(AppException):
    """Game-related exceptions."""
    pass


class GameNotFoundError(GameException):
    """Raised when a game is not found."""

    def __init__(self, game_id: str):
        super().__init__(
            message=f"Game not found: {game_id}",
            code="GAME_NOT_FOUND",
            details={"game_id": game_id}
        )


class InvalidActionError(GameException):
    """Raised when an invalid action is attempted."""

    def __init__(self, message: str, action_type: Optional[str] = None):
        super().__init__(
            message=message,
            code="INVALID_ACTION",
            details={"action_type": action_type} if action_type else {}
        )


class InvalidTargetError(GameException):
    """Raised when an invalid target is selected."""

    def __init__(self, message: str, target_id: Optional[int] = None):
        super().__init__(
            message=message,
            code="INVALID_TARGET",
            details={"target_id": target_id} if target_id else {}
        )


class NotYourTurnError(GameException):
    """Raised when a player acts out of turn."""

    def __init__(self, current_actor: Optional[int] = None):
        super().__init__(
            message="Not your turn to act",
            code="NOT_YOUR_TURN",
            details={"current_actor": current_actor} if current_actor else {}
        )


class PlayerDeadError(GameException):
    """Raised when a dead player tries to act."""

    def __init__(self, seat_id: int):
        super().__init__(
            message="Player is dead and cannot perform this action",
            code="PLAYER_DEAD",
            details={"seat_id": seat_id}
        )


class AuthException(AppException):
    """Authentication-related exceptions."""
    pass


class InvalidCredentialsError(AuthException):
    """Raised when credentials are invalid."""

    def __init__(self):
        super().__init__(
            message="Invalid credentials",
            code="INVALID_CREDENTIALS"
        )


class TokenExpiredError(AuthException):
    """Raised when a token has expired."""

    def __init__(self):
        super().__init__(
            message="Token has expired",
            code="TOKEN_EXPIRED"
        )


class UnauthorizedError(AuthException):
    """Raised when user is not authorized."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED"
        )


class RoomException(AppException):
    """Room-related exceptions."""
    pass


class RoomNotFoundError(RoomException):
    """Raised when a room is not found."""

    def __init__(self, room_id: str):
        super().__init__(
            message=f"Room not found: {room_id}",
            code="ROOM_NOT_FOUND",
            details={"room_id": room_id}
        )


class RoomFullError(RoomException):
    """Raised when a room is full."""

    def __init__(self, room_id: str):
        super().__init__(
            message="Room is full",
            code="ROOM_FULL",
            details={"room_id": room_id}
        )


class RoomInProgressError(RoomException):
    """Raised when trying to join a room with game in progress."""

    def __init__(self, room_id: str):
        super().__init__(
            message="Game already in progress",
            code="GAME_IN_PROGRESS",
            details={"room_id": room_id}
        )


class ConfigException(AppException):
    """Configuration-related exceptions."""
    pass


class InvalidConfigError(ConfigException):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(
            message=message,
            code="INVALID_CONFIG",
            details={"config_key": config_key} if config_key else {}
        )


class ServerCapacityError(AppException):
    """Raised when server is at capacity."""

    def __init__(self, message: str = "Server at capacity"):
        super().__init__(
            message=message,
            code="SERVER_CAPACITY"
        )


# HTTP Exception helpers
def raise_not_found(message: str = "Resource not found"):
    """Raise a 404 Not Found exception."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def raise_bad_request(message: str = "Bad request"):
    """Raise a 400 Bad Request exception."""
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def raise_unauthorized(message: str = "Unauthorized"):
    """Raise a 401 Unauthorized exception."""
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


def raise_forbidden(message: str = "Forbidden"):
    """Raise a 403 Forbidden exception."""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def raise_conflict(message: str = "Conflict"):
    """Raise a 409 Conflict exception."""
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def raise_server_error(message: str = "Internal server error"):
    """Raise a 500 Internal Server Error exception."""
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)
