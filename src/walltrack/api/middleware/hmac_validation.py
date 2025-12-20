"""HMAC validation middleware for webhook security."""

import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from walltrack.config.settings import get_settings
from walltrack.constants.webhook import HELIUS_SIGNATURE_HEADER
from walltrack.services.helius.models import WebhookValidationResult

logger = structlog.get_logger(__name__)


def validate_hmac_signature(body: bytes, signature: str, secret: str) -> bool:
    """
    Validate HMAC signature for webhook payload.

    Args:
        body: Raw request body bytes
        signature: Signature from request header
        secret: HMAC secret for verification

    Returns:
        True if signature is valid, False otherwise
    """
    expected = hmac.new(
        key=secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


class HMACValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Helius webhook HMAC signatures."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """
        Process request and validate HMAC signature for webhook endpoints.

        Args:
            request: Incoming FastAPI request
            call_next: Next middleware or route handler

        Returns:
            Response from next handler or 401 error
        """
        # Only validate webhook endpoints
        if not request.url.path.startswith("/webhooks"):
            return await call_next(request)

        # Skip validation for health check
        if request.url.path.endswith("/health"):
            return await call_next(request)

        validation_result = await self._validate_signature(request)

        if not validation_result.is_valid:
            logger.warning(
                "webhook_signature_invalid",
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown",
                error=validation_result.error_message,
            )
            return Response(
                content='{"detail": "Invalid webhook signature"}',
                status_code=401,
                media_type="application/json",
            )

        # Store validation result for downstream use
        request.state.webhook_validation = validation_result
        return await call_next(request)

    async def _validate_signature(self, request: Request) -> WebhookValidationResult:
        """
        Validate HMAC signature from Helius.

        Args:
            request: Incoming FastAPI request

        Returns:
            WebhookValidationResult with validation status
        """
        signature = request.headers.get(HELIUS_SIGNATURE_HEADER)

        if not signature:
            return WebhookValidationResult(
                is_valid=False,
                error_message="Missing signature header",
            )

        try:
            body = await request.body()
            settings = get_settings()
            secret = settings.helius_webhook_secret.get_secret_value()

            if not secret:
                logger.error("helius_webhook_secret_not_configured")
                return WebhookValidationResult(
                    is_valid=False,
                    error_message="Webhook secret not configured",
                )

            is_valid = validate_hmac_signature(body, signature, secret)

            return WebhookValidationResult(
                is_valid=is_valid,
                error_message=None if is_valid else "Signature mismatch",
                request_id=request.headers.get("X-Request-ID"),
                timestamp=datetime.now(UTC),
            )
        except Exception as e:
            logger.error("hmac_validation_error", error=str(e))
            return WebhookValidationResult(
                is_valid=False,
                error_message=f"Validation error: {e!s}",
            )
