"""Framework-neutral research datasets and later Portfolio Refinery research services."""

from .dataset import (
    RESEARCH_DAILY_RETURN_POLICY,
    RESEARCH_DATASET_CONTRACT_VERSION,
    RESEARCH_DATASET_HASH_ALGORITHM,
    RESEARCH_WEEKLY_POLICY,
    ResearchDataset,
    ResearchDatasetService,
    build_research_dataset,
)
from .exhaustive_selection import (
    EXHAUSTIVE_RANKING_DIRECTION,
    EXHAUSTIVE_RANKING_FIELD,
    EXHAUSTIVE_RANKING_TIE_BREAK,
    EXHAUSTIVE_SELECTION_RULE,
    WALK_FORWARD_EXHAUSTIVE_ADAPTER_VERSION,
    ExhaustiveAuthorityRunner,
    ExhaustiveSelectionEngine,
    NodeExhaustiveAuthorityRunner,
)
from .factor_data import (
    FRENCH_FACTOR_SOURCE,
    FrenchFactorProvider,
    parse_monthly_factor_text,
)
from .selection import (
    CONFIGURED_EQUAL_WEIGHT_ENGINE_VERSION,
    WALK_FORWARD_SELECTION_CONTRACT_VERSION,
    ConfiguredEqualWeightSelectionEngine,
    SelectionContext,
    SelectionEngine,
    SelectionResult,
    UnavailableCandidate,
    build_selection_context,
    run_selection,
    validate_evaluation_dataset,
)

__all__ = [
    "RESEARCH_DAILY_RETURN_POLICY",
    "RESEARCH_DATASET_CONTRACT_VERSION",
    "RESEARCH_DATASET_HASH_ALGORITHM",
    "RESEARCH_WEEKLY_POLICY",
    "FRENCH_FACTOR_SOURCE",
    "ResearchDataset",
    "ResearchDatasetService",
    "FrenchFactorProvider",
    "build_research_dataset",
    "parse_monthly_factor_text",
    "EXHAUSTIVE_RANKING_DIRECTION",
    "EXHAUSTIVE_RANKING_FIELD",
    "EXHAUSTIVE_RANKING_TIE_BREAK",
    "EXHAUSTIVE_SELECTION_RULE",
    "WALK_FORWARD_EXHAUSTIVE_ADAPTER_VERSION",
    "ExhaustiveAuthorityRunner",
    "ExhaustiveSelectionEngine",
    "NodeExhaustiveAuthorityRunner",
    "CONFIGURED_EQUAL_WEIGHT_ENGINE_VERSION",
    "WALK_FORWARD_SELECTION_CONTRACT_VERSION",
    "ConfiguredEqualWeightSelectionEngine",
    "SelectionContext",
    "SelectionEngine",
    "SelectionResult",
    "UnavailableCandidate",
    "build_selection_context",
    "run_selection",
    "validate_evaluation_dataset",
]
