"""Behavioral profiling module.

This module provides functions for wallet behavioral analysis including:
- Position sizing classification
- Hold duration analysis
- Trading style profiling
"""

from walltrack.core.behavioral.hold_duration import (
    calculate_hold_duration_avg,
    classify_hold_duration,
    format_duration_human,
)
from walltrack.core.behavioral.position_sizing import (
    calculate_position_size_avg,
    classify_position_size,
)
from walltrack.core.behavioral.profiler import BehavioralProfile, BehavioralProfiler

__all__ = [
    "calculate_position_size_avg",
    "classify_position_size",
    "calculate_hold_duration_avg",
    "classify_hold_duration",
    "format_duration_human",
    "BehavioralProfile",
    "BehavioralProfiler",
]
