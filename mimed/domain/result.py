from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from .milestone import MilestoneLadder


@dataclass
class SpendStats:
    expected_spend: float
    median_spend: float
    p90_spend: float
    p95_spend: float
    p99_spend: float
    budget_confidence: float  # P(spend <= budget)

@dataclass
class EconomicStats:
    expected_views: float
    effective_cpm: float
    completion_rate: float  # P(reach at least milestone 1)
    tier_reach_rates: Dict[str, float] = field(default_factory=dict)

@dataclass
class OptimizationResult:
    campaign_id: str
    recommended_ladder: MilestoneLadder
    spend_stats: SpendStats
    economic_stats: EconomicStats
    segment_metadata: Dict[str, Any]
    scoring_trace: Dict[str, Any]
    score: float = 0.0
    seed: int = 42
    candidates_generated: int = 0
    candidates_feasible: int = 0
    candidates_pareto: int = 0
    mu_ci_95: Tuple[float, float] = (0.0, 0.0)
    sigma_ci_95: Tuple[float, float] = (0.0, 0.0)
    runtime_seconds: float = 0.0
    run_id: str = ""

    def format_summary(self) -> str:
        ladder_lines = []
        for m in self.recommended_ladder.milestones:
            ladder_lines.append(
                f"  T{m.rank}: {m.view_threshold:,d} views → ₹{m.payout_amount:,.0f}"
            )
        ladder_str = "\n".join(ladder_lines)

        acc = self.scoring_trace.get("accessibility_score", 0.0)
        eff = self.scoring_trace.get("ecpm_efficiency_score", 0.0)
        fair = self.scoring_trace.get("fairness_score", 0.0)
        util = self.scoring_trace.get("budget_utilization_score", 0.0)

        total_obs = self.segment_metadata.get("obs_count", 0) + self.segment_metadata.get("suspicious_post_count", 0)
        clean_obs = self.segment_metadata.get("obs_count", 0)

        mu_lower, mu_upper = self.mu_ci_95
        sig_lower, sig_upper = self.sigma_ci_95

        raw_util = self.scoring_trace.get("expected_budget_utilization", 0.0)
        tier_reach = self.economic_stats.tier_reach_rates
        tier_reach_str = ", ".join(f"{k}: {v * 100:.1f}%" for k, v in tier_reach.items()) if tier_reach else "N/A"

        return (
            f"MIMED Optimization\n"
            f"────────────────────────────────\n\n"
            f"Campaign: {self.campaign_id}\n"
            f"Seed: {self.seed}\n\n"
            f"Historical observations: {total_obs:,d}\n"
            f"Clean observations: {clean_obs:,d}\n\n"
            f"Candidates:\n"
            f"  Generated: {self.candidates_generated:,d}\n"
            f"  Feasible: {self.candidates_feasible:,d}\n"
            f"  Pareto optimal: {self.candidates_pareto:,d}\n\n"
            f"Selected policy:\n"
            f"{ladder_str}\n\n"
            f"Objectives:\n"
            f"  Accessibility:       {acc:.2f}\n"
            f"  eCPM efficiency:     {eff:.2f}\n"
            f"  Tier fairness:       {fair:.2f}\n"
            f"  Budget utilization:  {util:.2f}\n\n"
            f"Raw Metrics:\n"
            f"  Completion rate:            {self.economic_stats.completion_rate * 100:.1f}%\n"
            f"  Effective CPM:              ₹{self.economic_stats.effective_cpm:,.2f}\n"
            f"  Expected spend:             ₹{self.spend_stats.expected_spend:,.0f}\n"
            f"  Expected budget utilization: {raw_util * 100:.1f}%\n"
            f"  Tier reach rates:           {tier_reach_str}\n\n"
            f"Budget:\n"
            f"  Probability within budget: {self.spend_stats.budget_confidence * 100:.1f}%\n\n"
            f"Uncertainty:\n"
            f"  μ 95% CI: [{mu_lower:.2f}, {mu_upper:.2f}]\n"
            f"  σ 95% CI: [{sig_lower:.2f}, {sig_upper:.2f}]\n\n"
            f"Runtime: {self.runtime_seconds:.2f}s\n\n"
            f"Run:\n"
            f"  {self.run_id}"
        )

