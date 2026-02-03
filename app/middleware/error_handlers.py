"""Error handlers for FastAPI application."""

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Any = None,
    ) -> None:
        """Initialize API error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code
            detail: Additional error details
        """
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class ValidationError(APIError):
    """Exception for validation errors."""

    def __init__(self, message: str, detail: Any = None) -> None:
        """Initialize validation error.

        Args:
            message: Human-readable error message
            detail: Additional error details (e.g., field errors)
        """
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, detail)


class ExternalServiceError(APIError):
    """Exception for external service errors."""

    def __init__(self, service: str, message: str) -> None:
        """Initialize external service error.

        Args:
            service: Name of the external service
            message: Error message
        """
        super().__init__(
            f"{service} error: {message}",
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {"service": service},
        )


class CaseNotFoundError(APIError):
    """Exception when a case is not found."""

    def __init__(self, case_id: str) -> None:
        """Initialize case not found error.

        Args:
            case_id: The case ID that was not found
        """
        super().__init__(
            f"Case {case_id} not found",
            status.HTTP_404_NOT_FOUND,
            {"case_id": case_id},
        )


def format_error_response(
    status_code: int,
    message: str,
    detail: Any = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Format a standardized error response.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        detail: Additional error details
        request_id: Request ID for tracing

    Returns:
        Formatted error response dict
    """
    response: dict[str, Any] = {
        "error": {
            "message": message,
            "status": status_code,
        }
    }

    if detail is not None:
        response["error"]["detail"] = detail

    if request_id:
        response["request_id"] = request_id

    return response


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors.

    Args:
        request: Incoming request
        exc: API exception

    Returns:
        JSON error response
    """
    request_id = getattr(request.state, "request_id", None)

    logger.error(
        f"API error: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "request_id": request_id,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            status_code=exc.status_code,
            message=exc.message,
            detail=exc.detail,
            request_id=request_id,
        ),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError | ValidationError
) -> JSONResponse:
    """Handle validation errors.

    Args:
        request: Incoming request
        exc: Validation exception

    Returns:
        JSON error response with field details
    """
    request_id = getattr(request.state, "request_id", None)

    # Format field errors
    field_errors = {}
    if isinstance(exc, RequestValidationError):
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error["loc"])
            field_errors[loc] = error["msg"]

    logger.warning(
        f"Validation error: {len(field_errors)} fields",
        extra={"field_errors": field_errors, "path": request.url.path, "request_id": request_id},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=format_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation failed",
            detail={"fields": field_errors},
            request_id=request_id,
        ),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTP exceptions.

    Args:
        request: Incoming request
        exc: HTTP exception

    Returns:
        JSON error response
    """
    request_id = getattr(request.state, "request_id", None)

    log_level = logging.WARNING if exc.status_code < 500 else logging.ERROR

    logger.log(
        log_level,
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={"path": request.url.path, "request_id": request_id},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            status_code=exc.status_code,
            message=str(exc.detail),
            request_id=request_id,
        ),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions.

    Args:
        request: Incoming request
        exc: Unexpected exception

    Returns:
        JSON error response
    """
    request_id = getattr(request.state, "request_id", None)

    # Log full traceback for debugging
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        extra={"path": request.url.path, "request_id": request_id},
        exc_info=True,
    )

    # Don't expose internal errors in production
    if settings.app_env == "production":
        message = "An internal error occurred. Please try again later."
        detail = None
    else:
        message = f"{type(exc).__name__}: {str(exc)}"
        detail = {"traceback": traceback.format_exc()}

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            detail=detail,
            request_id=request_id,
        ),
    )


def add_error_handlers(app: FastAPI) -> None:
    """Register all error handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    # Custom API errors
    app.add_exception_handler(APIError, api_error_handler)

    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)

    # HTTP exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Catch-all for unexpected errors
    app.add_exception_handler(Exception, general_exception_handler)

    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add unique request ID to each request."""
        import uuid

        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
