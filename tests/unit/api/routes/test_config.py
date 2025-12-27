"""Tests for config API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from walltrack.api.routes.config import router


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/api")  # Router already has /config prefix
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


def create_supabase_mock(return_data):
    """Create a properly chained async Supabase mock.

    The Supabase client uses chained method calls like:
        await client.table(...).select(...).eq(...).execute()

    Each method in the chain returns self for chaining,
    except execute() which returns an awaitable result.
    """
    # Create result mock
    result_mock = MagicMock()
    result_mock.data = return_data

    # The chain: table -> select -> eq -> single -> execute
    # All return self except execute which returns result
    chain = MagicMock()
    chain.table.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.single.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.execute = AsyncMock(return_value=result_mock)

    return chain


@pytest.fixture
def sample_config() -> dict:
    """Sample config row for testing."""
    return {
        "id": str(uuid4()),
        "status": "active",
        "version": 1,
        "name": "default",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "wallet_weight": 0.30,
        "cluster_weight": 0.25,
        "token_weight": 0.25,
        "context_weight": 0.20,
    }


class TestGetActiveConfig:
    """Tests for GET /lifecycle/{table}."""

    def test_get_active_config_success(
        self,
        client: TestClient,
        sample_config: dict,
    ) -> None:
        """Test successful retrieval of active config."""
        mock_supabase = create_supabase_mock(sample_config)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/config/lifecycle/scoring")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert "data" in data

    def test_get_active_config_invalid_table(
        self,
        client: TestClient,
    ) -> None:
        """Test error for invalid table name."""
        response = client.get("/api/config/lifecycle/invalid_table")

        assert response.status_code == 400
        assert "Invalid table" in response.json()["detail"]

    def test_get_active_config_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test error when no active config exists."""
        mock_supabase = create_supabase_mock(None)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/config/lifecycle/scoring")

        assert response.status_code == 404


class TestGetAllConfigs:
    """Tests for GET /lifecycle/{table}/all."""

    def test_get_all_configs_success(
        self,
        client: TestClient,
        sample_config: dict,
    ) -> None:
        """Test successful retrieval of all configs."""
        configs = [
            sample_config,
            {**sample_config, "id": str(uuid4()), "status": "draft", "version": 2},
        ]
        mock_supabase = create_supabase_mock(configs)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/config/lifecycle/scoring/all")

        assert response.status_code == 200
        data = response.json()
        assert len(data["configs"]) == 2

    def test_get_all_configs_invalid_table(
        self,
        client: TestClient,
    ) -> None:
        """Test error for invalid table name."""
        response = client.get("/api/config/lifecycle/invalid_table/all")

        assert response.status_code == 400


class TestCreateDraft:
    """Tests for POST /lifecycle/{table}/draft."""

    def test_create_draft_success(
        self,
        client: TestClient,
        sample_config: dict,
    ) -> None:
        """Test successful draft creation from active config."""
        active_config = sample_config.copy()
        draft_config = {**sample_config, "id": str(uuid4()), "status": "draft", "version": 1}

        # Create mock that returns different values on successive calls
        # Call sequence:
        # 1. Get active config (single)
        # 2. Check existing draft (returns empty list = no draft)
        # 3. Insert new draft (returns list with new record)
        # 4. Audit log insert
        mock_supabase = MagicMock()
        result_mocks = [
            MagicMock(data=active_config),  # 1. Get active
            MagicMock(data=[]),  # 2. Check existing draft (empty = no draft)
            MagicMock(data=[draft_config]),  # 3. Insert new draft (returns list)
            MagicMock(data=None),  # 4. Audit log
        ]
        call_count = [0]

        def get_execute_result():
            result = result_mocks[call_count[0]] if call_count[0] < len(result_mocks) else MagicMock(data=None)
            call_count[0] += 1
            return result

        mock_supabase.table.return_value = mock_supabase
        mock_supabase.select.return_value = mock_supabase
        mock_supabase.eq.return_value = mock_supabase
        mock_supabase.neq.return_value = mock_supabase
        mock_supabase.single.return_value = mock_supabase
        mock_supabase.delete.return_value = mock_supabase
        mock_supabase.insert.return_value = mock_supabase
        mock_supabase.execute = AsyncMock(side_effect=get_execute_result)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.post(
                "/api/config/lifecycle/scoring/draft",
                json={"name": "test-draft"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"

    def test_create_draft_invalid_table(
        self,
        client: TestClient,
    ) -> None:
        """Test error for invalid table name."""
        response = client.post(
            "/api/config/lifecycle/invalid_table/draft",
            json={"name": "test"},
        )

        assert response.status_code == 400


class TestUpdateDraft:
    """Tests for PATCH /lifecycle/{table}/draft."""

    def test_update_draft_success(
        self,
        client: TestClient,
        sample_config: dict,
    ) -> None:
        """Test successful draft update."""
        draft_config = {**sample_config, "status": "draft"}
        updated_config = {**draft_config, "wallet_weight": 0.35}

        mock_supabase = MagicMock()
        result_mocks = [
            MagicMock(data=draft_config),  # Get draft
            MagicMock(data=[updated_config]),  # Update draft (returns list)
            MagicMock(data=None),  # Audit log
        ]
        call_count = [0]

        def get_execute_result():
            result = result_mocks[call_count[0]] if call_count[0] < len(result_mocks) else MagicMock(data=None)
            call_count[0] += 1
            return result

        # All chain methods return self to enable method chaining
        mock_supabase.table.return_value = mock_supabase
        mock_supabase.select.return_value = mock_supabase
        mock_supabase.eq.return_value = mock_supabase
        mock_supabase.single.return_value = mock_supabase
        mock_supabase.update.return_value = mock_supabase
        mock_supabase.insert.return_value = mock_supabase  # For audit log
        mock_supabase.execute = AsyncMock(side_effect=get_execute_result)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.patch(
                "/api/config/lifecycle/scoring/draft",
                json={"data": {"wallet_weight": 0.35}},  # field is "data", not "changes"
            )

        assert response.status_code == 200

    def test_update_draft_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test error when no draft exists."""
        mock_supabase = create_supabase_mock(None)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.patch(
                "/api/config/lifecycle/scoring/draft",
                json={"data": {"wallet_weight": 0.35}},  # field is "data", not "changes"
            )

        assert response.status_code == 404


class TestActivateDraft:
    """Tests for POST /lifecycle/{table}/activate."""

    def test_activate_draft_success(
        self,
        client: TestClient,
        sample_config: dict,
    ) -> None:
        """Test successful draft activation."""
        draft_config = {**sample_config, "id": str(uuid4()), "status": "draft", "version": 2}
        active_config = sample_config.copy()

        mock_supabase = MagicMock()
        result_mocks = [
            MagicMock(data=draft_config),  # Get draft
            MagicMock(data=active_config),  # Get active
            MagicMock(data=[{**active_config, "status": "archived"}]),  # Archive active (returns list)
            MagicMock(data=[{**draft_config, "status": "active"}]),  # Activate draft (returns list)
            MagicMock(data=None),  # Audit log
        ]
        call_count = [0]

        def get_execute_result():
            result = result_mocks[call_count[0]] if call_count[0] < len(result_mocks) else MagicMock(data=None)
            call_count[0] += 1
            return result

        mock_supabase.table.return_value = mock_supabase
        mock_supabase.select.return_value = mock_supabase
        mock_supabase.eq.return_value = mock_supabase
        mock_supabase.single.return_value = mock_supabase
        mock_supabase.update.return_value = mock_supabase
        mock_supabase.insert.return_value = mock_supabase
        mock_supabase.execute = AsyncMock(side_effect=get_execute_result)

        mock_config_service = MagicMock()
        mock_config_service.refresh = AsyncMock()  # refresh(table) is called, not refresh_cache

        with (
            patch(
                "walltrack.api.routes.config.get_supabase_client",
                new=AsyncMock(return_value=mock_supabase),
            ),
            patch(
                "walltrack.api.routes.config.get_config_service",
                new=AsyncMock(return_value=mock_config_service),
            ),
        ):
            response = client.post(
                "/api/config/lifecycle/scoring/activate",
                json={"reason": "test activation"},  # Only reason is optional
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"  # ActivateResponse uses "status", not "success"
        mock_config_service.refresh.assert_called_once()

    def test_activate_draft_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test error when no draft exists."""
        mock_supabase = create_supabase_mock(None)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.post(
                "/api/config/lifecycle/scoring/activate",
                json={},  # Empty body is valid since all fields optional
            )

        assert response.status_code == 404


class TestRestoreArchived:
    """Tests for POST /lifecycle/{table}/{config_id}/restore."""

    def test_restore_archived_success(
        self,
        client: TestClient,
        sample_config: dict,
    ) -> None:
        """Test successful restoration of archived config as draft."""
        config_id = sample_config["id"]
        archived_config = {**sample_config, "status": "archived"}
        new_draft = {**sample_config, "id": str(uuid4()), "status": "draft"}

        mock_supabase = MagicMock()
        result_mocks = [
            MagicMock(data=archived_config),  # Get archived
            MagicMock(data=None),  # Delete existing draft
            MagicMock(data=[new_draft]),  # Insert as draft (returns list)
            MagicMock(data=None),  # Audit log
        ]
        call_count = [0]

        def get_execute_result():
            result = result_mocks[call_count[0]] if call_count[0] < len(result_mocks) else MagicMock(data=None)
            call_count[0] += 1
            return result

        mock_supabase.table.return_value = mock_supabase
        mock_supabase.select.return_value = mock_supabase
        mock_supabase.eq.return_value = mock_supabase
        mock_supabase.single.return_value = mock_supabase
        mock_supabase.delete.return_value = mock_supabase
        mock_supabase.insert.return_value = mock_supabase
        mock_supabase.execute = AsyncMock(side_effect=get_execute_result)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.post(
                f"/api/config/lifecycle/scoring/{config_id}/restore"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"

    def test_restore_archived_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test error when config not found."""
        mock_supabase = create_supabase_mock(None)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.post(
                f"/api/config/lifecycle/scoring/{uuid4()}/restore"
            )

        assert response.status_code == 404


class TestDeleteDraft:
    """Tests for DELETE /lifecycle/{table}/draft."""

    def test_delete_draft_success(
        self,
        client: TestClient,
        sample_config: dict,
    ) -> None:
        """Test successful draft deletion."""
        draft_config = {**sample_config, "status": "draft"}

        mock_supabase = MagicMock()
        result_mocks = [
            MagicMock(data=draft_config),  # Get draft
            MagicMock(data=None),  # Delete draft
            MagicMock(data=None),  # Audit log
        ]
        call_count = [0]

        def get_execute_result():
            result = result_mocks[call_count[0]] if call_count[0] < len(result_mocks) else MagicMock(data=None)
            call_count[0] += 1
            return result

        mock_supabase.table.return_value = mock_supabase
        mock_supabase.select.return_value = mock_supabase
        mock_supabase.eq.return_value = mock_supabase
        mock_supabase.single.return_value = mock_supabase
        mock_supabase.delete.return_value = mock_supabase
        mock_supabase.insert.return_value = mock_supabase
        mock_supabase.execute = AsyncMock(side_effect=get_execute_result)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.delete("/api/config/lifecycle/scoring/draft")

        assert response.status_code == 200


class TestGetAuditLog:
    """Tests for GET /audit."""

    def test_get_audit_log_success(
        self,
        client: TestClient,
    ) -> None:
        """Test successful retrieval of audit log."""
        audit_entries = [
            {
                "id": 1,  # id is an integer, not UUID
                "config_table": "scoring",
                "config_key": "activate",
                "old_value": None,
                "new_value": "v2",
                "changed_by": "test-user",
                "changed_at": datetime.now(UTC).isoformat(),
                "reason": "Activating new config",
            }
        ]
        mock_supabase = create_supabase_mock(audit_entries)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/config/audit")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 1

    def test_get_audit_log_with_table_filter(
        self,
        client: TestClient,
    ) -> None:
        """Test audit log filtering by table."""
        mock_supabase = create_supabase_mock([])

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/config/audit?table=scoring")

        assert response.status_code == 200


class TestRiskConfigEndpoints:
    """Tests for legacy risk config endpoints."""

    def test_get_risk_config(
        self,
        client: TestClient,
    ) -> None:
        """Test GET /risk endpoint."""
        config_data = {
            "id": str(uuid4()),
            "max_position_pct": 0.02,
            "stop_loss_pct": 0.10,
            "take_profit_pct": 0.25,
        }
        mock_supabase = create_supabase_mock(config_data)

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/config/risk")

        assert response.status_code == 200

    def test_update_risk_config(
        self,
        client: TestClient,
    ) -> None:
        """Test PUT /risk endpoint."""
        mock_supabase = create_supabase_mock({"max_position_pct": 0.03})

        with patch(
            "walltrack.api.routes.config.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.put(
                "/api/config/risk",
                json={"max_position_pct": 0.03},
            )

        assert response.status_code == 200
