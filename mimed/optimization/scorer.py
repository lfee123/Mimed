"""
Multi-Objective Scorer for Milestone Ladders.
Calculates explainable preference scores for budget-feasible candidates.
"""
from typing import Dict, Any, Tuple
import numpy as np

from mimed.config import OptimizerConfig
from mimed.optimization.simulator import SimulationOutcome


class MultiObjectiveScorer:
    def __init__(self, config: OptimizerConfig = None):
        self.config = config or OptimizerConfig()

    def score_outcome(
        self, outcome: SimulationOutcome, campaign_budget: float
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculates multi-objective score in [0.0, 1.0] and detailed trace breakdown.
        Score = w_acc * Acc + w_ecpm * Eff + w_fair * Fair + w_util * Util
        """
        # 1. Creator Accessibility (Overall Completion Rate)
        acc_score = min(1.0, outcome.economic_stats.completion_rate / 0.85)

        # 2. Economic Efficiency (Campaign-aware eCPM range)
        ecpm = outcome.economic_stats.effective_cpm
        exp_views = outcome.economic_stats.expected_views
        ecpm_base_min, ecpm_base_max = self.config.target_ecpm_range

        if exp_views > 0:
            e_ref = (campaign_budget / exp_views) * 1000.0
            ecpm_min = max(ecpm_base_min, 0.25 * e_ref)
            ecpm_max = max(ecpm_base_max, 1.15 * e_ref)
        else:
            ecpm_min, ecpm_max = ecpm_base_min, ecpm_base_max

        if ecpm <= 0:
            ecpm_score = 0.0
        elif ecpm < ecpm_min:
            ecpm_score = 0.70  # Low eCPM is cheap but might under-reward creators
        elif ecpm <= ecpm_max:
            # Ideal campaign-aware eCPM band [0.70, 1.00]
            ecpm_score = 1.0 - (ecpm - ecpm_min) / max(1.0, ecpm_max - ecpm_min) * 0.30
        else:
            # Sharply decay score for extreme eCPMs exceeding the campaign envelope
            ecpm_score = max(0.0, 1.0 - (ecpm - ecpm_max) / max(1.0, ecpm_max))

        # 3. Tier Fairness (Low variance of reach rates across creator tiers)
        tier_rates = list(outcome.economic_stats.tier_reach_rates.values())
        if len(tier_rates) > 1:
            mean_r = np.mean(tier_rates)
            std_r = np.std(tier_rates)
            fairness_score = float(max(0.0, 1.0 - (std_r / max(0.01, mean_r))))
        else:
            fairness_score = 1.0

        # 4. Budget Utilization Rate
        utilization = outcome.spend_stats.expected_spend / max(1.0, campaign_budget)
        # Optimal utilization range: 75% to 92%
        if 0.75 <= utilization <= 0.95:
            util_score = 1.0
        elif utilization < 0.75:
            util_score = max(0.0, utilization / 0.75)
        else:
            util_score = max(0.0, 1.0 - (utilization - 0.95) / 0.05)

        # Weighted Composite Score
        total_score = (
            self.config.w_accessibility * acc_score
            + self.config.w_ecpm_efficiency * ecpm_score
            + self.config.w_fairness * fairness_score
            + self.config.w_budget_utilization * util_score
        )

        trace = {
            "total_score": round(total_score, 4),
            "accessibility_score": round(acc_score, 4),
            "ecpm_efficiency_score": round(ecpm_score, 4),
            "fairness_score": round(fairness_score, 4),
            "budget_utilization_score": round(util_score, 4),
            "expected_budget_utilization": round(utilization, 4),
        }

        return total_score, trace
