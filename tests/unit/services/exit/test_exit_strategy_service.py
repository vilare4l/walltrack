"""Tests for ExitStrategyService."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategyCreate,
    ExitStrategyRule,
    ExitStrategyService,
    ExitStrategyUpdate,
    reset_exit_strategy_service,
)
from walltrack.services.exit.strategy_templates import (
    get_aggressive_template,
    get_conservative_template,
    get_standard_template,
    get_template,
    list_templates,
)


@pytest.fixture
def sample_rule() -> ExitStrategyRule:
    """Create a sample exit rule."""
    return ExitStrategyRule(
        rule_type="stop_loss",
        trigger_pct=Decimal("-10"),
        exit_pct=Decimal("100"),
        priority=0,
        enabled=True,
    )


@pytest.fixture
def sample_create_data(sample_rule: ExitStrategyRule) -> ExitStrategyCreate:
    """Create sample strategy create data."""
    return ExitStrategyCreate(
        name="Test Strategy",
        description="Test description",
        rules=[sample_rule],
        max_hold_hours=24,
        stagnation_hours=6,
        stagnation_threshold_pct=Decimal("2.0"),
    )


@pytest.fixture
def sample_db_row() -> dict:
    """Create a sample database row."""
    return {
        "id": "test-id-123",
        "name": "Test Strategy",
        "description": "Test description",
        "version": 1,
        "status": "draft",
        "rules": [
            {
                "rule_type": "stop_loss",
                "trigger_pct": "-10",
                "exit_pct": "100",
                "priority": 0,
                "enabled": True,
                "params": {},
            }
        ],
        "max_hold_hours": 24,
        "stagnation_hours": 6,
        "stagnation_threshold_pct": "2.0",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "activated_at": None,
        "archived_at": None,
    }


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def service(mock_client: MagicMock) -> ExitStrategyService:
    """Create service with mock client."""
    svc = ExitStrategyService()
    svc._client = mock_client
    return svc


class TestExitStrategyRule:
    """Tests for ExitStrategyRule model."""

    def test_create_rule(self) -> None:
        """Test creating a basic rule."""
        rule = ExitStrategyRule(
            rule_type="take_profit",
            trigger_pct=Decimal("15"),
            exit_pct=Decimal("50"),
            priority=1,
        )

        assert rule.rule_type == "take_profit"
        assert rule.trigger_pct == Decimal("15")
        assert rule.exit_pct == Decimal("50")
        assert rule.priority == 1
        assert rule.enabled is True
        assert rule.params == {}

    def test_rule_with_params(self) -> None:
        """Test rule with custom parameters."""
        rule = ExitStrategyRule(
            rule_type="trailing_stop",
            trigger_pct=Decimal("-5"),
            priority=3,
            params={"activation_pct": 10},
        )

        assert rule.params == {"activation_pct": 10}


class TestExitStrategyCreate:
    """Tests for ExitStrategyCreate model."""

    def test_create_with_defaults(self, sample_rule: ExitStrategyRule) -> None:
        """Test creating with default values."""
        data = ExitStrategyCreate(
            name="Test",
            rules=[sample_rule],
        )

        assert data.name == "Test"
        assert data.description is None
        assert data.max_hold_hours == 24
        assert data.stagnation_hours == 6
        assert data.stagnation_threshold_pct == Decimal("2.0")

    def test_create_with_all_fields(self, sample_rule: ExitStrategyRule) -> None:
        """Test creating with all fields."""
        data = ExitStrategyCreate(
            name="Full Strategy",
            description="Full description",
            rules=[sample_rule],
            max_hold_hours=48,
            stagnation_hours=12,
            stagnation_threshold_pct=Decimal("3.0"),
        )

        assert data.max_hold_hours == 48
        assert data.stagnation_hours == 12
        assert data.stagnation_threshold_pct == Decimal("3.0")


class TestExitStrategyService:
    """Tests for ExitStrategyService."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_exit_strategy_service()

    def test_parse_strategy(
        self, service: ExitStrategyService, sample_db_row: dict
    ) -> None:
        """Test parsing database row to model."""
        strategy = service._parse_strategy(sample_db_row)

        assert strategy.id == "test-id-123"
        assert strategy.name == "Test Strategy"
        assert strategy.version == 1
        assert strategy.status == "draft"
        assert len(strategy.rules) == 1
        assert strategy.rules[0].rule_type == "stop_loss"
        assert strategy.max_hold_hours == 24

    def test_parse_strategy_with_active_status(
        self, service: ExitStrategyService, sample_db_row: dict
    ) -> None:
        """Test parsing active strategy with activated_at."""
        sample_db_row["status"] = "active"
        sample_db_row["activated_at"] = "2024-01-02T00:00:00Z"

        strategy = service._parse_strategy(sample_db_row)

        assert strategy.status == "active"
        assert strategy.activated_at is not None

    @pytest.mark.asyncio
    async def test_create_strategy(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_create_data: ExitStrategyCreate,
        sample_db_row: dict,
    ) -> None:
        """Test creating a new strategy."""
        mock_execute = AsyncMock(return_value=MagicMock(data=[sample_db_row]))
        mock_client.table.return_value.insert.return_value.execute = mock_execute

        result = await service.create(sample_create_data)

        assert result.name == "Test Strategy"
        assert result.status == "draft"
        assert result.version == 1
        mock_client.table.assert_called_with("exit_strategies")

    @pytest.mark.asyncio
    async def test_get_strategy(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test getting a strategy by ID."""
        mock_execute = AsyncMock(return_value=MagicMock(data=sample_db_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_execute
        )

        result = await service.get("test-id-123")

        assert result is not None
        assert result.id == "test-id-123"

    @pytest.mark.asyncio
    async def test_get_nonexistent_strategy(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
    ) -> None:
        """Test getting a nonexistent strategy."""
        mock_execute = AsyncMock(return_value=MagicMock(data=None))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_execute
        )

        result = await service.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test listing all strategies."""
        mock_execute = AsyncMock(return_value=MagicMock(data=[sample_db_row]))
        mock_query = MagicMock()
        mock_query.neq.return_value.order.return_value.order.return_value.execute = (
            mock_execute
        )
        mock_client.table.return_value.select.return_value = mock_query

        result = await service.list_all()

        assert len(result) == 1
        assert result[0].name == "Test Strategy"

    @pytest.mark.asyncio
    async def test_update_draft_in_place(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test updating a draft strategy in place."""
        # Setup get mock
        mock_get = AsyncMock(return_value=MagicMock(data=sample_db_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_get
        )

        # Setup update mock
        updated_row = {**sample_db_row, "name": "Updated Name"}
        mock_update = AsyncMock(return_value=MagicMock(data=[updated_row]))
        mock_client.table.return_value.update.return_value.eq.return_value.execute = (
            mock_update
        )

        update_data = ExitStrategyUpdate(name="Updated Name")
        result = await service.update("test-id-123", update_data)

        assert result.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_active_creates_new_version(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test updating an active strategy creates a new version."""
        # Make it active
        active_row = {**sample_db_row, "status": "active"}

        # Setup get mock
        mock_get = AsyncMock(return_value=MagicMock(data=active_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_get
        )

        # Setup list_by_name mock
        mock_list = AsyncMock(return_value=MagicMock(data=[active_row]))
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute = (
            mock_list
        )

        # Setup insert mock for new version
        new_row = {**sample_db_row, "id": "new-id", "version": 2, "status": "draft"}
        mock_insert = AsyncMock(return_value=MagicMock(data=[new_row]))
        mock_client.table.return_value.insert.return_value.execute = mock_insert

        update_data = ExitStrategyUpdate(description="Updated description")
        result = await service.update("test-id-123", update_data)

        assert result.version == 2
        assert result.status == "draft"

    @pytest.mark.asyncio
    async def test_activate_strategy(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test activating a draft strategy."""
        # Setup get mock
        mock_get = AsyncMock(return_value=MagicMock(data=sample_db_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_get
        )

        # Setup archive previous active mock
        mock_archive = AsyncMock(return_value=MagicMock(data=[]))
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute = (
            mock_archive
        )

        # Setup activate mock
        activated_row = {**sample_db_row, "status": "active", "activated_at": "2024-01-02T00:00:00Z"}
        mock_activate = AsyncMock(return_value=MagicMock(data=[activated_row]))
        mock_client.table.return_value.update.return_value.eq.return_value.execute = (
            mock_activate
        )

        result = await service.activate("test-id-123")

        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_activate_non_draft_fails(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test activating a non-draft strategy fails."""
        active_row = {**sample_db_row, "status": "active"}
        mock_get = AsyncMock(return_value=MagicMock(data=active_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_get
        )

        with pytest.raises(ValueError, match="Can only activate draft strategies"):
            await service.activate("test-id-123")

    @pytest.mark.asyncio
    async def test_clone_strategy(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test cloning a strategy."""
        # Setup get mock
        mock_get = AsyncMock(return_value=MagicMock(data=sample_db_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_get
        )

        # Setup create mock
        cloned_row = {
            **sample_db_row,
            "id": "cloned-id",
            "name": "Test Strategy (copy)",
        }
        mock_insert = AsyncMock(return_value=MagicMock(data=[cloned_row]))
        mock_client.table.return_value.insert.return_value.execute = mock_insert

        result = await service.clone("test-id-123")

        assert result.name == "Test Strategy (copy)"
        assert result.id == "cloned-id"

    @pytest.mark.asyncio
    async def test_clone_with_custom_name(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test cloning with custom name."""
        # Setup get mock
        mock_get = AsyncMock(return_value=MagicMock(data=sample_db_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_get
        )

        # Setup create mock
        cloned_row = {**sample_db_row, "id": "cloned-id", "name": "Custom Clone"}
        mock_insert = AsyncMock(return_value=MagicMock(data=[cloned_row]))
        mock_client.table.return_value.insert.return_value.execute = mock_insert

        result = await service.clone("test-id-123", "Custom Clone")

        assert result.name == "Custom Clone"

    @pytest.mark.asyncio
    async def test_delete_draft(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test deleting a draft strategy."""
        # Setup get mock
        mock_get = AsyncMock(return_value=MagicMock(data=sample_db_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_get
        )

        # Setup delete mock
        mock_delete = AsyncMock(return_value=MagicMock(data=[]))
        mock_client.table.return_value.delete.return_value.eq.return_value.execute = (
            mock_delete
        )

        result = await service.delete_draft("test-id-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_active_fails(
        self,
        service: ExitStrategyService,
        mock_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test deleting an active strategy fails."""
        active_row = {**sample_db_row, "status": "active"}
        mock_get = AsyncMock(return_value=MagicMock(data=active_row))
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
            mock_get
        )

        with pytest.raises(ValueError, match="Can only delete draft strategies"):
            await service.delete_draft("test-id-123")


class TestStrategyTemplates:
    """Tests for strategy templates."""

    def test_get_standard_template(self) -> None:
        """Test standard template."""
        template = get_standard_template()

        assert template.name == "Standard"
        assert len(template.rules) == 4
        assert template.max_hold_hours == 24

        # Check for expected rule types
        rule_types = [r.rule_type for r in template.rules]
        assert "stop_loss" in rule_types
        assert "take_profit" in rule_types
        assert "trailing_stop" in rule_types

    def test_get_aggressive_template(self) -> None:
        """Test aggressive template."""
        template = get_aggressive_template()

        assert template.name == "High Conviction"
        assert len(template.rules) == 5
        assert template.max_hold_hours == 48

    def test_get_conservative_template(self) -> None:
        """Test conservative template."""
        template = get_conservative_template()

        assert template.name == "Conservative"
        assert len(template.rules) == 4
        assert template.max_hold_hours == 12

        # Should have time_based rule
        rule_types = [r.rule_type for r in template.rules]
        assert "time_based" in rule_types

    def test_get_template_by_name(self) -> None:
        """Test getting template by name."""
        template = get_template("standard")
        assert template.name == "Standard"

        template = get_template("AGGRESSIVE")  # Case insensitive
        assert template.name == "High Conviction"

    def test_get_unknown_template_fails(self) -> None:
        """Test getting unknown template fails."""
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("nonexistent")

    def test_list_templates(self) -> None:
        """Test listing available templates."""
        templates = list_templates()

        assert "standard" in templates
        assert "aggressive" in templates
        assert "conservative" in templates
        assert len(templates) == 3
