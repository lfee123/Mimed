"""
Vectorized Monte Carlo Simulator.
Evaluates candidate milestone ladders against a pre-sampled simulated view matrix.
"""
from dataclasses import dataclass
from typing import List, Dict, Tuple
import numpy as np

from mimed.domain import Campaign, Creator, MilestoneLadder
from mimed.domain.result import SpendStats, EconomicStats


@dataclass
class SimulationOutcome:
    ladder: MilestoneLadder
    spend_stats: SpendStats
    economic_stats: EconomicStats
    per_simulation_spend: np.ndarray  # 1D array of shape (n_simulations,)


class CampaignSimulator:
    def __init__(self, campaign: Campaign, target_creators: List[Creator]):
        self.campaign = campaign
        self.target_creators = target_creators
        self.n_creators = len(target_creators)

    def evaluate_ladder(
        self,
        ladder: MilestoneLadder,
        views_matrix: np.ndarray,  # shape: (n_simulations, n_creators)
    ) -> SimulationOutcome:
        """
        Evaluate a candidate MilestoneLadder against the pre-generated views matrix.
        Fully vectorized using NumPy broadcast operations.
        """
        n_simulations, n_creators = views_matrix.shape
        if n_creators == 0 or not ladder.milestones:
            empty_spend = np.zeros(n_simulations)
            return SimulationOutcome(
                ladder=ladder,
                spend_stats=SpendStats(0, 0, 0, 0, 0, 1.0),
                economic_stats=EconomicStats(0, 0, 0, {}),
                per_simulation_spend=empty_spend,
            )

        # Extract thresholds and payouts
        thresholds = np.array([m.view_threshold for m in ladder.milestones], dtype=np.int64)
        payouts = np.array([m.payout_amount for m in ladder.milestones], dtype=np.float64)

        # Compute payouts for each creator across all simulations
        # views_matrix shape: (n_sim, n_creators, 1) vs thresholds shape: (1, 1, n_milestones)
        # Reached mask shape: (n_sim, n_creators, n_milestones)
        reached_mask = views_matrix[:, :, np.newaxis] >= thresholds[np.newaxis, np.newaxis, :]

        # For cumulative payout, the highest threshold reached gives the payout
        # Mask payouts where not reached
        masked_payouts = np.where(reached_mask, payouts[np.newaxis, np.newaxis, :], 0.0)
        # Max payout across milestones reached per creator
        creator_payouts = np.max(masked_payouts, axis=2)  # shape: (n_sim, n_creators)

        # Total campaign spend per simulation instance
        total_spend_per_sim = np.sum(creator_payouts, axis=1)  # shape: (n_sim,)

        # Total views generated per simulation instance
        total_views_per_sim = np.sum(views_matrix, axis=1)  # shape: (n_sim,)

        # Spend statistics
        expected_spend = float(np.mean(total_spend_per_sim))
        median_spend = float(np.median(total_spend_per_sim))
        p90_spend = float(np.percentile(total_spend_per_sim, 90))
        p95_spend = float(np.percentile(total_spend_per_sim, 95))
        p99_spend = float(np.percentile(total_spend_per_sim, 99))

        # Budget confidence: P(spend <= campaign.total_budget)
        within_budget = total_spend_per_sim <= self.campaign.total_budget
        budget_confidence = float(np.mean(within_budget))

        spend_stats = SpendStats(
            expected_spend=expected_spend,
            median_spend=median_spend,
            p90_spend=p90_spend,
            p95_spend=p95_spend,
            p99_spend=p99_spend,
            budget_confidence=budget_confidence,
        )

        # Economic statistics
        expected_views = float(np.mean(total_views_per_sim))
        effective_cpm = (
            (expected_spend / (expected_views / 1000.0))
            if expected_views > 0
            else 0.0
        )

        # Completion rate: P(reach at least milestone 1)
        first_milestone_reached = reached_mask[:, :, 0]  # shape: (n_sim, n_creators)
        overall_completion_rate = float(np.mean(first_milestone_reached))

        # Tier breakdown of completion rate
        tier_reach_rates: Dict[str, float] = {}
        for idx, creator in enumerate(self.target_creators):
            tier = creator.tier
            c_reached = first_milestone_reached[:, idx]
            tier_reach_rates.setdefault(tier, []).append(float(np.mean(c_reached)))

        tier_summary = {
            t: float(np.mean(rates)) for t, rates in tier_reach_rates.items()
        }

        economic_stats = EconomicStats(
            expected_views=expected_views,
            effective_cpm=effective_cpm,
            completion_rate=overall_completion_rate,
            tier_reach_rates=tier_summary,
        )

        return SimulationOutcome(
            ladder=ladder,
            spend_stats=spend_stats,
            economic_stats=economic_stats,
            per_simulation_spend=total_spend_per_sim,
        )
