"""Typed application errors with safe client-facing messages."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("authentication_required", message, 401)


class AuthorizationError(AppError):
    def __init__(self, message: str = "You are not permitted to perform this action") -> None:
        super().__init__("permission_denied", message, 403)


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__("not_found", f"{resource} was not found", 404)


class ConflictError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 409)


class ServiceUnavailableError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 503)


class RetryableServiceUnavailableError(ServiceUnavailableError):
    """A demonstrably transient dependency failure safe for bounded replay."""


class UnsafeUploadError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 422)
