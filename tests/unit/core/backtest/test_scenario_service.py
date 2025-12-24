"""Tests for scenario service."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestScenarioService:
    """Tests for ScenarioService class."""

    @pytest.fixture
    def mock_supabase(self) -> MagicMock:
        """Create mock Supabase client."""
        mock = MagicMock()
        mock.select = AsyncMock(return_value=[])
        mock.insert = AsyncMock(return_value=None)
        mock.update = AsyncMock(return_value=None)
        mock.delete = AsyncMock(return_value=None)
        return mock


class TestGetAllScenarios(TestScenarioService):
    """Tests for get_all_scenarios."""

    async def test_returns_presets_by_default(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that presets are included by default."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            scenarios = await service.get_all_scenarios()

            # Should include 5 presets
            assert len(scenarios) >= 5

    async def test_filters_by_category(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test filtering scenarios by category."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario import ScenarioCategory
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            scenarios = await service.get_all_scenarios(
                category=ScenarioCategory.CONSERVATIVE
            )

            # All returned scenarios should be conservative
            for scenario in scenarios:
                assert scenario.category == ScenarioCategory.CONSERVATIVE

    async def test_excludes_presets_when_requested(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test excluding presets from results."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            scenarios = await service.get_all_scenarios(include_presets=False)

            # Should be empty (no custom scenarios in mock)
            assert len(scenarios) == 0


class TestGetScenario(TestScenarioService):
    """Tests for get_scenario."""

    async def test_returns_preset_by_id(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test getting a preset scenario by ID."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario import PRESET_SCENARIOS
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            preset_id = PRESET_SCENARIOS[0].id
            scenario = await service.get_scenario(preset_id)

            assert scenario is not None
            assert scenario.id == preset_id

    async def test_returns_none_for_nonexistent(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test getting nonexistent scenario returns None."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            scenario = await service.get_scenario(uuid4())

            assert scenario is None


class TestCreateScenario(TestScenarioService):
    """Tests for create_scenario."""

    async def test_creates_scenario(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test creating a new scenario."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario import Scenario
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            scenario = Scenario(
                name="New Scenario",
                description="Test",
                score_threshold=Decimal("0.75"),
            )

            result = await service.create_scenario(scenario)

            assert result.name == "New Scenario"
            assert result.is_preset is False
            mock_supabase.insert.assert_called_once()


class TestUpdateScenario(TestScenarioService):
    """Tests for update_scenario."""

    async def test_prevents_preset_update(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that presets cannot be updated."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario import PRESET_SCENARIOS
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            preset_id = PRESET_SCENARIOS[0].id

            with pytest.raises(ValueError, match="Cannot modify preset"):
                await service.update_scenario(preset_id, {"name": "Modified"})


class TestDeleteScenario(TestScenarioService):
    """Tests for delete_scenario."""

    async def test_prevents_preset_deletion(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that presets cannot be deleted."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario import PRESET_SCENARIOS
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            preset_id = PRESET_SCENARIOS[0].id

            with pytest.raises(ValueError, match="Cannot delete preset"):
                await service.delete_scenario(preset_id)


class TestDuplicateScenario(TestScenarioService):
    """Tests for duplicate_scenario."""

    async def test_duplicates_preset(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test duplicating a preset scenario."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario import PRESET_SCENARIOS
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            preset = PRESET_SCENARIOS[0]

            duplicate = await service.duplicate_scenario(preset.id, "My Copy")

            assert duplicate.name == "My Copy"
            assert duplicate.id != preset.id
            assert duplicate.score_threshold == preset.score_threshold
            assert duplicate.is_preset is False


class TestExportImportScenario(TestScenarioService):
    """Tests for export/import."""

    async def test_export_scenario(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test exporting scenario to JSON."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario import PRESET_SCENARIOS
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            json_str = await service.export_scenario(PRESET_SCENARIOS[0].id)

            assert "Conservative" in json_str
            assert "score_threshold" in json_str

    async def test_import_scenario(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test importing scenario from JSON."""
        with patch(
            "walltrack.core.backtest.scenario_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.scenario import Scenario
            from walltrack.core.backtest.scenario_service import ScenarioService

            service = ScenarioService()
            original = Scenario(name="Import Test", score_threshold=Decimal("0.85"))
            json_str = original.to_json()

            imported = await service.import_scenario(json_str)

            assert imported.name == "Import Test"
            assert imported.score_threshold == Decimal("0.85")
            assert imported.id != original.id  # New ID generated


class TestCompareToLive(TestScenarioService):
    """Tests for compare_to_live."""

    def test_finds_differences(self) -> None:
        """Test comparing scenario to live config."""
        from walltrack.core.backtest.scenario import Scenario
        from walltrack.core.backtest.scenario_service import ScenarioService

        scenario = Scenario(
            name="Test",
            score_threshold=Decimal("0.80"),
            base_position_sol=Decimal("0.2"),
        )

        live_config = {
            "score_threshold": 0.70,
            "base_position_sol": 0.1,
        }

        service = ScenarioService()
        differences = service.compare_to_live(scenario, live_config)

        assert "score_threshold" in differences
        assert differences["score_threshold"]["scenario"] == 0.80
        assert differences["score_threshold"]["live"] == 0.70


class TestGetScenarioService:
    """Tests for singleton accessor."""

    async def test_returns_singleton(self) -> None:
        """Test get_scenario_service returns singleton."""
        from walltrack.core.backtest.scenario_service import get_scenario_service

        service1 = await get_scenario_service()
        service2 = await get_scenario_service()

        assert service1 is service2
