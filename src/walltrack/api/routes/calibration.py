"""API routes for scoring model calibration."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from walltrack.core.feedback import (
    ApplyWeightsRequest,
    AutoCalibrationConfig,
    CalibrationAnalysis,
    CalibrationSuggestion,
    WeightArchive,
    WeightSet,
    get_model_calibrator,
)

router = APIRouter(prefix="/calibration", tags=["calibration"])


class AnalysisResponse(BaseModel):
    """Response for calibration analysis."""

    analysis: CalibrationAnalysis
    is_valid: bool = Field(..., description="Whether analysis has sufficient data")


class SuggestionResponse(BaseModel):
    """Response with calibration suggestion."""

    suggestion: CalibrationSuggestion
    requires_action: bool = Field(
        default=True, description="Whether operator review is required"
    )


class WeightHistoryResponse(BaseModel):
    """Response for weight history."""

    archives: list[WeightArchive]
    total_count: int


class CurrentWeightsResponse(BaseModel):
    """Response for current weights."""

    weights: WeightSet
    last_updated: str | None = None


class AutoCalibrationResponse(BaseModel):
    """Response for auto-calibration config update."""

    config: AutoCalibrationConfig
    message: str


@router.post("/analyze", response_model=AnalysisResponse)
async def run_analysis(min_trades: int = 100) -> AnalysisResponse:
    """Run calibration analysis on recent trades.

    Args:
        min_trades: Minimum trades required for valid analysis

    Returns:
        Analysis results with suggestions
    """
    calibrator = get_model_calibrator()
    analysis = await calibrator.run_analysis(min_trades=min_trades)

    return AnalysisResponse(
        analysis=analysis,
        is_valid=analysis.is_valid,
    )


@router.post("/suggest", response_model=SuggestionResponse)
async def create_suggestion(analysis_id: UUID) -> SuggestionResponse:
    """Create calibration suggestion from analysis.

    Args:
        analysis_id: ID of analysis to create suggestion from

    Returns:
        Suggestion for operator review
    """
    calibrator = get_model_calibrator()

    try:
        suggestion = await calibrator.create_suggestion(analysis_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return SuggestionResponse(suggestion=suggestion)


@router.get("/suggestions/{suggestion_id}", response_model=CalibrationSuggestion)
async def get_suggestion(suggestion_id: UUID) -> CalibrationSuggestion:
    """Get a calibration suggestion by ID.

    Args:
        suggestion_id: Suggestion ID

    Returns:
        Suggestion details
    """
    calibrator = get_model_calibrator()
    suggestion = await calibrator.get_suggestion(suggestion_id)

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    return suggestion


@router.get("/suggestions", response_model=list[CalibrationSuggestion])
async def list_pending_suggestions(
    limit: int = 10,
) -> list[CalibrationSuggestion]:
    """List pending calibration suggestions.

    Args:
        limit: Maximum number of suggestions to return

    Returns:
        List of pending suggestions
    """
    calibrator = get_model_calibrator()
    return await calibrator.list_pending_suggestions(limit=limit)


@router.post("/apply", response_model=CalibrationSuggestion)
async def apply_weights(request: ApplyWeightsRequest) -> CalibrationSuggestion:
    """Apply calibration suggestion to update weights.

    Args:
        request: Apply weights request with optional modifications

    Returns:
        Updated suggestion with applied status
    """
    calibrator = get_model_calibrator()

    try:
        return await calibrator.apply_weights(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/reject/{suggestion_id}", response_model=CalibrationSuggestion)
async def reject_suggestion(
    suggestion_id: UUID, reason: str = "No reason provided"
) -> CalibrationSuggestion:
    """Reject a calibration suggestion.

    Args:
        suggestion_id: Suggestion to reject
        reason: Rejection reason

    Returns:
        Updated suggestion with rejected status
    """
    calibrator = get_model_calibrator()

    try:
        return await calibrator.reject_suggestion(suggestion_id, reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/weights/current", response_model=CurrentWeightsResponse)
async def get_current_weights() -> CurrentWeightsResponse:
    """Get current scoring weights.

    Returns:
        Current weight configuration
    """
    calibrator = get_model_calibrator()
    weights = await calibrator.get_current_weights()

    return CurrentWeightsResponse(weights=weights)


@router.get("/weights/history", response_model=WeightHistoryResponse)
async def get_weight_history(
    limit: int = 20, offset: int = 0
) -> WeightHistoryResponse:
    """Get weight change history.

    Args:
        limit: Maximum records to return
        offset: Pagination offset

    Returns:
        Historical weight configurations
    """
    calibrator = get_model_calibrator()
    archives = await calibrator.get_weight_history(limit=limit, offset=offset)

    return WeightHistoryResponse(
        archives=archives,
        total_count=len(archives),
    )


@router.put("/weights/manual", response_model=CalibrationSuggestion)
async def manual_weight_update(
    weights: WeightSet, reason: str = "Manual adjustment"
) -> CalibrationSuggestion:
    """Manually update scoring weights.

    Args:
        weights: New weight configuration
        reason: Reason for manual update

    Returns:
        Applied suggestion record
    """
    calibrator = get_model_calibrator()

    # Validate weights are normalized
    if not weights.is_normalized:
        raise HTTPException(
            status_code=400,
            detail=f"Weights must sum to 1.0, got {weights.total_weight}",
        )

    return await calibrator.apply_manual_weights(weights, reason)


@router.get("/auto-config", response_model=AutoCalibrationConfig)
async def get_auto_calibration_config() -> AutoCalibrationConfig:
    """Get auto-calibration configuration.

    Returns:
        Current auto-calibration settings
    """
    calibrator = get_model_calibrator()
    return await calibrator.get_auto_config()


@router.put("/auto-config", response_model=AutoCalibrationResponse)
async def update_auto_calibration_config(
    config: AutoCalibrationConfig,
) -> AutoCalibrationResponse:
    """Update auto-calibration configuration.

    Args:
        config: New auto-calibration settings

    Returns:
        Updated configuration with confirmation
    """
    calibrator = get_model_calibrator()
    await calibrator.update_auto_config(config)

    message = "Auto-calibration enabled" if config.enabled else "Auto-calibration disabled"
    return AutoCalibrationResponse(config=config, message=message)


@router.get("/performance")
async def get_weight_performance(
    lookback_days: int = 30,
) -> dict:
    """Get performance metrics for current weights.

    Args:
        lookback_days: Number of days to analyze

    Returns:
        Performance metrics including win rate and PnL
    """
    calibrator = get_model_calibrator()
    return await calibrator.get_weight_performance(lookback_days)
