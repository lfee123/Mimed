"""
Backtest Metrics & Comparison Data Structures.
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class LadderEvaluation:
    ladder_type: str  # "historical", "baseline", "optimized"
    actual_payout: float
    total_budget: float
    budget_utilization: float
    exceeded_budget: bool
    expected_views: float
    actual_views: float
    effective_cpm: float
    completion_rate: float
    first_milestone_reach_rate: float


@dataclass
class CampaignBacktestResult:
    campaign_id: str
    brand: str
    category: str
    platform: str
    target_tier: str
    total_budget: float
    historical_eval: LadderEvaluation
    baseline_eval: LadderEvaluation
    optimized_eval: LadderEvaluation

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "brand": self.brand,
            "category": self.category,
            "platform": self.platform,
            "target_tier": self.target_tier,
            "total_budget": self.total_budget,
            "hist_payout": self.historical_eval.actual_payout,
            "hist_utilization": self.historical_eval.budget_utilization,
            "hist_ecpm": self.historical_eval.effective_cpm,
            "base_payout": self.baseline_eval.actual_payout,
            "base_utilization": self.baseline_eval.budget_utilization,
            "base_ecpm": self.baseline_eval.effective_cpm,
            "opt_payout": self.optimized_eval.actual_payout,
            "opt_utilization": self.optimized_eval.budget_utilization,
            "opt_ecpm": self.optimized_eval.effective_cpm,
            "opt_exceeded_budget": self.optimized_eval.exceeded_budget,
            "opt_completion_rate": self.optimized_eval.completion_rate,
        }
