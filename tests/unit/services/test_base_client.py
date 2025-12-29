"""Tests for BaseAPIClient implementation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestBaseAPIClientInit:
    """Tests for BaseAPIClient initialization."""

    def test_base_api_client_init_with_base_url(self) -> None:
        """
        Given: BaseAPIClient class
        When: Created with base_url
        Then: Stores base_url correctly
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")
        assert client.base_url == "https://api.example.com"

    def test_base_api_client_default_timeout(self) -> None:
        """
        Given: BaseAPIClient without explicit timeout
        When: Created
        Then: Uses default timeout of 30 seconds
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")
        assert client.timeout == 30.0

    def test_base_api_client_custom_timeout(self) -> None:
        """
        Given: BaseAPIClient with custom timeout
        When: Created
        Then: Uses custom timeout
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com", timeout=60.0)
        assert client.timeout == 60.0

    def test_base_api_client_custom_headers(self) -> None:
        """
        Given: BaseAPIClient with custom headers
        When: Created
        Then: Stores headers correctly
        """
        from walltrack.services.base import BaseAPIClient

        headers = {"Authorization": "Bearer token123"}
        client = BaseAPIClient(base_url="https://api.example.com", headers=headers)
        assert client.headers == headers

    def test_base_api_client_lazy_initialization(self) -> None:
        """
        Given: BaseAPIClient created
        When: Before first request
        Then: Internal httpx client is None (lazy)
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")
        assert client._client is None


class TestBaseAPIClientClose:
    """Tests for BaseAPIClient close method."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self) -> None:
        """
        Given: BaseAPIClient with active httpx client
        When: close() is called
        Then: Client is closed and set to None
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")
        # Simulate client creation
        mock_httpx_client = AsyncMock()
        client._client = mock_httpx_client

        await client.close()

        mock_httpx_client.aclose.assert_called_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_does_nothing_if_no_client(self) -> None:
        """
        Given: BaseAPIClient without active client
        When: close() is called
        Then: No error occurs
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")
        assert client._client is None

        # Should not raise
        await client.close()


class TestBaseAPIClientRetry:
    """Tests for BaseAPIClient retry logic."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        """
        Given: BaseAPIClient
        When: Request succeeds on first attempt
        Then: Returns response without retry
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        response = await client.get("/endpoint")

        assert response.status_code == 200
        assert mock_httpx_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_timeout_then_success(self) -> None:
        """
        Given: BaseAPIClient
        When: First request times out, second succeeds
        Then: Returns response after retry
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(
            side_effect=[httpx.TimeoutException("timeout"), mock_response]
        )
        client._client = mock_httpx_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client.get("/endpoint")

        assert response.status_code == 200
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_400_error(self) -> None:
        """
        Given: BaseAPIClient
        When: Request returns 400 Bad Request
        Then: Fails immediately without retry
        """
        from walltrack.core.exceptions import ExternalServiceError
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Bad Request", request=MagicMock(), response=mock_response
            )
        )

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await client.get("/endpoint")

        assert exc_info.value.status_code == 400
        assert mock_httpx_client.request.call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_no_retry_on_401_error(self) -> None:
        """
        Given: BaseAPIClient
        When: Request returns 401 Unauthorized
        Then: Fails immediately without retry
        """
        from walltrack.core.exceptions import ExternalServiceError
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )
        )

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await client.get("/endpoint")

        assert exc_info.value.status_code == 401
        assert mock_httpx_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_403_error(self) -> None:
        """
        Given: BaseAPIClient
        When: Request returns 403 Forbidden
        Then: Fails immediately without retry
        """
        from walltrack.core.exceptions import ExternalServiceError
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Forbidden", request=MagicMock(), response=mock_response
            )
        )

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await client.get("/endpoint")

        assert exc_info.value.status_code == 403
        assert mock_httpx_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_404_error(self) -> None:
        """
        Given: BaseAPIClient
        When: Request returns 404 Not Found
        Then: Fails immediately without retry
        """
        from walltrack.core.exceptions import ExternalServiceError
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )
        )

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        with pytest.raises(ExternalServiceError) as exc_info:
            await client.get("/endpoint")

        assert exc_info.value.status_code == 404
        assert mock_httpx_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_429_rate_limit(self) -> None:
        """
        Given: BaseAPIClient
        When: First request returns 429, second succeeds
        Then: Retries and returns success
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_429_response = MagicMock()
        mock_429_response.status_code = 429
        mock_429_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Rate Limit", request=MagicMock(), response=mock_429_response
            )
        )

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(
            side_effect=[mock_429_response, mock_success_response]
        )
        client._client = mock_httpx_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client.get("/endpoint")

        assert response.status_code == 200
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_500_server_error(self) -> None:
        """
        Given: BaseAPIClient
        When: First request returns 500, second succeeds
        Then: Retries and returns success
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_500_response = MagicMock()
        mock_500_response.status_code = 500
        mock_500_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_500_response
            )
        )

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(
            side_effect=[mock_500_response, mock_success_response]
        )
        client._client = mock_httpx_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client.get("/endpoint")

        assert response.status_code == 200
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_502_error(self) -> None:
        """
        Given: BaseAPIClient
        When: First request returns 502, second succeeds
        Then: Retries and returns success
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_502_response = MagicMock()
        mock_502_response.status_code = 502
        mock_502_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Bad Gateway", request=MagicMock(), response=mock_502_response
            )
        )

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(
            side_effect=[mock_502_response, mock_success_response]
        )
        client._client = mock_httpx_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client.get("/endpoint")

        assert response.status_code == 200
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_503_error(self) -> None:
        """
        Given: BaseAPIClient
        When: First request returns 503, second succeeds
        Then: Retries and returns success
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_503_response = MagicMock()
        mock_503_response.status_code = 503
        mock_503_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Service Unavailable", request=MagicMock(), response=mock_503_response
            )
        )

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(
            side_effect=[mock_503_response, mock_success_response]
        )
        client._client = mock_httpx_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client.get("/endpoint")

        assert response.status_code == 200
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_raises_external_service_error(self) -> None:
        """
        Given: BaseAPIClient
        When: All retry attempts fail with 500 errors
        Then: Raises ExternalServiceError with "Max retries exceeded" message
        """
        from walltrack.core.exceptions import ExternalServiceError
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
        )

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ExternalServiceError) as exc_info:
                await client.get("/endpoint")

        assert "Max retries" in str(exc_info.value)
        assert mock_httpx_client.request.call_count == 3  # All 3 retries attempted

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self) -> None:
        """
        Given: BaseAPIClient
        When: First request has connection error, second succeeds
        Then: Retries and returns success
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(
            side_effect=[
                httpx.RequestError("Connection refused", request=MagicMock()),
                mock_success_response,
            ]
        )
        client._client = mock_httpx_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client.get("/endpoint")

        assert response.status_code == 200
        assert mock_httpx_client.request.call_count == 2


class TestBaseAPIClientCircuitBreaker:
    """Tests for BaseAPIClient circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold_failures(self) -> None:
        """
        Given: BaseAPIClient
        When: 5 consecutive failures occur
        Then: Circuit opens and blocks requests
        """
        from walltrack.core.exceptions import CircuitBreakerOpenError
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=mock_response
            )
        )

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        # Trigger 5 failures (threshold default) with max retries each
        # Each failed request with 3 retries = 3 circuit breaker failures
        # We need 5 total failures to open the circuit
        # With retry loop, we should hit the threshold
        with patch("asyncio.sleep", new_callable=AsyncMock):
            for _ in range(2):  # 2 requests * 3 retries = 6 failures
                try:
                    await client.get("/endpoint")
                except Exception:
                    pass

        # Now circuit should be open
        with pytest.raises(CircuitBreakerOpenError):
            await client.get("/endpoint")

    @pytest.mark.asyncio
    async def test_request_fails_fast_when_circuit_open(self) -> None:
        """
        Given: BaseAPIClient with open circuit
        When: Request is made
        Then: Fails immediately with CircuitBreakerOpenError
        """
        from walltrack.core.exceptions import CircuitBreakerOpenError
        from walltrack.services.base import BaseAPIClient, CircuitState

        client = BaseAPIClient(base_url="https://api.example.com")

        # Manually open the circuit
        from datetime import datetime, timezone

        client._circuit_breaker.state = CircuitState.OPEN
        client._circuit_breaker.last_failure_time = datetime.now(timezone.utc)

        with pytest.raises(CircuitBreakerOpenError):
            await client.get("/endpoint")


class TestBaseAPIClientMethods:
    """Tests for BaseAPIClient HTTP methods."""

    @pytest.mark.asyncio
    async def test_get_method(self) -> None:
        """
        Given: BaseAPIClient
        When: get() is called
        Then: Makes GET request
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        await client.get("/endpoint")

        mock_httpx_client.request.assert_called_once()
        call_args = mock_httpx_client.request.call_args
        assert call_args[0][0] == "GET"

    @pytest.mark.asyncio
    async def test_post_method(self) -> None:
        """
        Given: BaseAPIClient
        When: post() is called with json data
        Then: Makes POST request with body
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        await client.post("/endpoint", json={"key": "value"})

        mock_httpx_client.request.assert_called_once()
        call_args = mock_httpx_client.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[1]["json"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_put_method(self) -> None:
        """
        Given: BaseAPIClient
        When: put() is called
        Then: Makes PUT request
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        await client.put("/endpoint", json={"key": "value"})

        mock_httpx_client.request.assert_called_once()
        call_args = mock_httpx_client.request.call_args
        assert call_args[0][0] == "PUT"

    @pytest.mark.asyncio
    async def test_delete_method(self) -> None:
        """
        Given: BaseAPIClient
        When: delete() is called
        Then: Makes DELETE request
        """
        from walltrack.services.base import BaseAPIClient

        client = BaseAPIClient(base_url="https://api.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_httpx_client

        await client.delete("/endpoint")

        mock_httpx_client.request.assert_called_once()
        call_args = mock_httpx_client.request.call_args
        assert call_args[0][0] == "DELETE"
