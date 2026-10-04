"""
Global configuration settings for mimed.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
DATABASE_PATH = DATA_DIR / "mimed.db"
SCHEMA_PATH = BASE_DIR / "mimed" / "data" / "schema.sql"

DEFAULT_SEED = 42

# Creator Tiers
CREATOR_TIERS: List[str] = ["nano", "micro", "mid", "macro"]

TIER_FOLLOWER_BOUNDS: Dict[str, tuple[int, int]] = {
    "nano": (1_000, 10_000),
    "micro": (10_000, 50_000),
    "mid": (50_000, 250_000),
    "macro": (250_000, 2_000_000),
}

SUPPORTED_PLATFORMS: List[str] = ["instagram", "youtube", "tiktok"]
SUPPORTED_CATEGORIES: List[str] = ["gaming", "beauty", "tech", "fashion", "fitness", "lifestyle"]
SUPPORTED_FORMATS: List[str] = ["reel", "video", "short", "story"]

# Default Optimization & Simulation Config
@dataclass
class OptimizerConfig:
    budget_confidence_level: float = 0.95  # P(spend <= budget) >= 0.95
    simulations_count: int = 5_000
    candidate_quantiles: List[float] = field(
        default_factory=lambda: [0.20, 0.35, 0.50, 0.65, 0.80, 0.92]
    )
    # Objective weights for ladder scoring
    w_accessibility: float = 0.30
    w_ecpm_efficiency: float = 0.30
    w_fairness: float = 0.20
    w_budget_utilization: float = 0.20

    # Economic parameters
    target_ecpm_range: tuple[float, float] = (15.0, 100.0)  # INR per 1000 views
    reward_share_of_media_value: float = 0.35  # Payout pool as fraction of media value

    # Hierarchical fallback minimum observations
    min_segment_observations: int = 25
