"""
Constraint Evaluation Engine.
Enforces hard budget safety and validity rules.
"""
from mimed.optimization.simulator import SimulationOutcome


class ConstraintEngine:
    def __init__(self, min_budget_confidence: float = 0.95):
        self.min_budget_confidence = min_budget_confidence

    def is_feasible(self, outcome: SimulationOutcome, campaign_budget: float = None) -> bool:
        """
        Hard constraint check:
        1. P(total campaign spend <= total campaign budget) >= min_budget_confidence
        2. P95 spend <= total campaign budget (if campaign_budget provided)
        """
        if outcome.spend_stats.budget_confidence < self.min_budget_confidence:
            return False
        if campaign_budget is not None and campaign_budget > 0:
            if outcome.spend_stats.p95_spend > campaign_budget:
                return False
        if outcome.spend_stats.expected_spend <= 0:
            return False
        return True
