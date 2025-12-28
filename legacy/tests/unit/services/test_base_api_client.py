"""Unit tests for BaseAPIClient implementation.

Test ID: 1.3-UNIT-002
"""

import contextlib
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from walltrack.core.exceptions import CircuitBreakerOpenError
from walltrack.services.base import BaseAPIClient, CircuitState


def create_mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    method: str = "GET",
    url: str = "https://api.example.com/test",
) -> httpx.Response:
    """Create a mock httpx.Response with proper request instance."""
    request = httpx.Request(method, url)
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=request,
    )
    return response


class TestBaseAPIClient:
    """Tests for BaseAPIClient class."""

    @pytest.fixture
    def client(self) -> BaseAPIClient:
        """Create a BaseAPIClient instance."""
        return BaseAPIClient(base_url="https://api.example.com", timeout=5.0)

    async def test_get_client_creates_http_client(self, client: BaseAPIClient) -> None:
        """Test that _get_client creates an httpx.AsyncClient."""
        http_client = await client._get_client()
        assert isinstance(http_client, httpx.AsyncClient)
        assert http_client.base_url == httpx.URL("https://api.example.com")
        await client.close()

    async def test_close_closes_http_client(self, client: BaseAPIClient) -> None:
        """Test that close properly closes the HTTP client."""
        await client._get_client()
        assert client._client is not None
        await client.close()
        assert client._client is None

    async def test_request_with_successful_response(self, client: BaseAPIClient) -> None:
        """Test successful request."""
        mock_response = create_mock_response(200, {"data": "test"})

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            response = await client.get("/test")
            assert response.status_code == 200

        await client.close()

    async def test_request_retries_on_failure(self, client: BaseAPIClient) -> None:
        """Test that request retries on transient failure."""
        success_response = create_mock_response(200, {"data": "success"})

        call_count = 0

        async def side_effect(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")
            return success_response

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = side_effect
            response = await client.get("/test")
            assert response.status_code == 200
            assert call_count == 3  # Two failures + one success

        await client.close()

    async def test_request_raises_after_max_retries(self, client: BaseAPIClient) -> None:
        """Test that request raises exception after max retries."""
        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(httpx.ConnectError):
                await client.get("/test", max_retries=3)

        await client.close()

    async def test_circuit_breaker_opens_after_failures(self, client: BaseAPIClient) -> None:
        """Test that circuit breaker opens after consecutive failures."""
        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection failed")

            # Make enough requests to open the circuit breaker
            # Each request tries 3 times, we need 5 failures to open circuit
            for _ in range(2):
                with contextlib.suppress(httpx.ConnectError):
                    await client.get("/test", max_retries=3)

            # Circuit should now be open (5+ failures recorded)
            assert client._circuit_breaker.state == CircuitState.OPEN

            # Next request should raise CircuitBreakerOpenError immediately
            with pytest.raises(CircuitBreakerOpenError):
                await client.get("/test")

        await client.close()

    async def test_circuit_breaker_resets_on_success(self, client: BaseAPIClient) -> None:
        """Test that circuit breaker resets after successful request."""
        # First, simulate some failures
        client._circuit_breaker.failure_count = 3

        success_response = create_mock_response(200, {"data": "success"})

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = success_response
            await client.get("/test")

            assert client._circuit_breaker.failure_count == 0
            assert client._circuit_breaker.state == CircuitState.CLOSED

        await client.close()

    async def test_request_does_not_retry_on_http_status_error(
        self, client: BaseAPIClient
    ) -> None:
        """Test that HTTP 4xx errors trigger retry logic through raise_for_status."""
        error_response = create_mock_response(404, {"error": "Not found"})

        call_count = 0

        async def side_effect(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return error_response

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = side_effect

            with pytest.raises(httpx.HTTPStatusError):
                await client.get("/test", max_retries=3)

            # Should retry since raise_for_status raises HTTPError
            assert call_count == 3

        await client.close()

    async def test_headers_are_passed_to_client(self) -> None:
        """Test that custom headers are passed to HTTP client."""
        client = BaseAPIClient(
            base_url="https://api.example.com",
            headers={"Authorization": "Bearer token123"},
        )

        http_client = await client._get_client()
        assert "Authorization" in http_client.headers
        assert http_client.headers["Authorization"] == "Bearer token123"

        await client.close()

    async def test_timeout_is_configured(self) -> None:
        """Test that timeout is properly configured."""
        client = BaseAPIClient(
            base_url="https://api.example.com",
            timeout=10.0,
        )

        http_client = await client._get_client()
        assert http_client.timeout.connect == 10.0

        await client.close()

    async def test_base_url_trailing_slash_removed(self) -> None:
        """Test that trailing slash is removed from base URL."""
        client = BaseAPIClient(base_url="https://api.example.com/")
        assert client.base_url == "https://api.example.com"
        await client.close()

    async def test_post_request(self, client: BaseAPIClient) -> None:
        """Test POST request method."""
        success_response = create_mock_response(
            201, {"id": 1}, method="POST", url="https://api.example.com/items"
        )

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = success_response
            response = await client.post("/items", json={"name": "test"})
            assert response.status_code == 201
            mock_request.assert_called_once_with("POST", "/items", json={"name": "test"})

        await client.close()

    async def test_put_request(self, client: BaseAPIClient) -> None:
        """Test PUT request method."""
        success_response = create_mock_response(
            200, {"id": 1, "updated": True}, method="PUT", url="https://api.example.com/items/1"
        )

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = success_response
            response = await client.put("/items/1", json={"name": "updated"})
            assert response.status_code == 200

        await client.close()

    async def test_delete_request(self, client: BaseAPIClient) -> None:
        """Test DELETE request method."""
        success_response = create_mock_response(
            204, method="DELETE", url="https://api.example.com/items/1"
        )

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = success_response
            response = await client.delete("/items/1")
            assert response.status_code == 204

        await client.close()
