"""Unit tests for HMAC validation middleware."""

import hashlib
import hmac

import pytest

from walltrack.api.middleware.hmac_validation import validate_hmac_signature


class TestHMACValidation:
    """Tests for HMAC signature validation."""

    def test_valid_signature_passes(self) -> None:
        """Test that valid signatures pass validation."""
        secret = "test-secret-key"
        body = b'{"test": "data", "timestamp": 1704067200}'

        # Generate valid signature
        signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        result = validate_hmac_signature(body, signature, secret)
        assert result is True

    def test_invalid_signature_fails(self) -> None:
        """Test that invalid signatures fail validation."""
        secret = "test-secret-key"
        body = b'{"test": "data"}'
        wrong_signature = "invalid_signature_that_does_not_match"

        result = validate_hmac_signature(body, wrong_signature, secret)
        assert result is False

    def test_tampered_body_fails(self) -> None:
        """Test that tampered body fails validation."""
        secret = "test-secret-key"
        original_body = b'{"test": "data"}'
        tampered_body = b'{"test": "modified"}'

        # Generate signature for original body
        signature = hmac.new(
            key=secret.encode(),
            msg=original_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Validate with tampered body should fail
        result = validate_hmac_signature(tampered_body, signature, secret)
        assert result is False

    def test_wrong_secret_fails(self) -> None:
        """Test that wrong secret fails validation."""
        correct_secret = "correct-secret"
        wrong_secret = "wrong-secret"
        body = b'{"test": "data"}'

        # Generate signature with correct secret
        signature = hmac.new(
            key=correct_secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Validate with wrong secret should fail
        result = validate_hmac_signature(body, signature, wrong_secret)
        assert result is False

    def test_empty_body_validation(self) -> None:
        """Test validation with empty body."""
        secret = "test-secret"
        body = b""

        signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        result = validate_hmac_signature(body, signature, secret)
        assert result is True

    def test_large_payload_validation(self) -> None:
        """Test validation with large payload."""
        secret = "test-secret"
        # Simulate large webhook payload (100KB)
        body = b'{"data": "' + b"x" * 100000 + b'"}'

        signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        result = validate_hmac_signature(body, signature, secret)
        assert result is True

    def test_timing_safe_comparison(self) -> None:
        """Test that comparison is timing-safe (no early exit)."""
        import time

        secret = "test-secret"
        body = b'{"test": "data"}'

        valid_signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Invalid signatures with different positions of mismatch
        invalid_signatures = [
            "0" + valid_signature[1:],  # First char wrong
            valid_signature[:-1] + "0",  # Last char wrong
            "0" * len(valid_signature),  # All wrong
        ]

        # All invalid signatures should take similar time
        times = []
        for sig in invalid_signatures:
            start = time.perf_counter()
            for _ in range(1000):
                validate_hmac_signature(body, sig, secret)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # Times should be similar (within 50% of each other)
        max_time = max(times)
        min_time = min(times)
        assert max_time < min_time * 2, "Timing variance suggests non-constant-time comparison"


class TestHMACEdgeCases:
    """Edge case tests for HMAC validation."""

    def test_unicode_secret(self) -> None:
        """Test validation with unicode secret."""
        secret = "test-secret-🔐-émojis"
        body = b'{"test": "data"}'

        signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        result = validate_hmac_signature(body, signature, secret)
        assert result is True

    def test_json_body_with_special_chars(self) -> None:
        """Test validation with JSON containing special characters."""
        secret = "test-secret"
        body = b'{"message": "Hello \\n World", "emoji": "\\ud83d\\ude00"}'

        signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        result = validate_hmac_signature(body, signature, secret)
        assert result is True

    def test_binary_body(self) -> None:
        """Test validation with binary body."""
        secret = "test-secret"
        body = bytes([0x00, 0x01, 0x02, 0xFF, 0xFE, 0xFD])

        signature = hmac.new(
            key=secret.encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        result = validate_hmac_signature(body, signature, secret)
        assert result is True
