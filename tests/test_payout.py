import pytest
from mimed.domain import Milestone, MilestoneLadder
from mimed.optimization.payout_policy import PayoutPolicy


def test_milestone_ladder_cumulative_payout():
    ladder = MilestoneLadder(
        campaign_id="c_test",
        milestones=[
            Milestone(rank=1, view_threshold=10000, payout_amount=500.0),
            Milestone(rank=2, view_threshold=50000, payout_amount=2000.0),
            Milestone(rank=3, view_threshold=100000, payout_amount=5000.0),
        ],
    )

    assert ladder.calculate_payout(5000) == 0.0
    assert ladder.calculate_payout(10000) == 500.0
    assert ladder.calculate_payout(75000) == 2000.0
    assert ladder.calculate_payout(120000) == 5000.0


def test_milestone_validation_monotonicity():
    with pytest.raises(ValueError):
        MilestoneLadder(
            campaign_id="c_bad",
            milestones=[
                Milestone(rank=1, view_threshold=50000, payout_amount=2000.0),
                Milestone(rank=2, view_threshold=10000, payout_amount=500.0),
            ],
        )

    with pytest.raises(ValueError):
        MilestoneLadder(
            campaign_id="c_bad2",
            milestones=[
                Milestone(rank=1, view_threshold=10000, payout_amount=2000.0),
                Milestone(rank=2, view_threshold=50000, payout_amount=1000.0),
            ],
        )


def test_payout_policy_generation():
    policy = PayoutPolicy(reward_share=0.35, target_ecpm=40.0)
    ladder = policy.generate_payouts_for_thresholds("c_policy", [10000, 25000, 50000, 100000])

    assert len(ladder.milestones) == 4
    # Check monotonicity
    ladder.validate()
    assert ladder.milestones[0].payout_amount < ladder.milestones[1].payout_amount


def test_scorer_ecpm_cases():
    import numpy as np
    from mimed.optimization.scorer import MultiObjectiveScorer
    from mimed.optimization.simulator import SimulationOutcome
    from mimed.domain import SpendStats, EconomicStats, MilestoneLadder

    scorer = MultiObjectiveScorer()
    budget = 1_000_000.0
    views = 10_000_000.0
    dummy_spend = np.array([10000.0])

    dummy_ladder = MilestoneLadder(campaign_id="test", milestones=[])

    # Low eCPM -> 0.70
    outcome_low = SimulationOutcome(
        ladder=dummy_ladder,
        spend_stats=SpendStats(10000, 10000, 10000, 10000, 10000, 1.0),
        economic_stats=EconomicStats(views, 10.0, 0.85, {"tier1": 0.85}),
        per_simulation_spend=dummy_spend,
    )
    _, trace_low = scorer.score_outcome(outcome_low, budget)
    assert trace_low["ecpm_efficiency_score"] == 0.70

    # Reasonable eCPM -> high score [0.70, 1.00]
    outcome_reasonable = SimulationOutcome(
        ladder=dummy_ladder,
        spend_stats=SpendStats(800000, 800000, 800000, 800000, 800000, 1.0),
        economic_stats=EconomicStats(views, 100.0, 0.85, {"tier1": 0.85}),
        per_simulation_spend=dummy_spend,
    )
    _, trace_reasonable = scorer.score_outcome(outcome_reasonable, budget)
    assert 0.70 <= trace_reasonable["ecpm_efficiency_score"] <= 1.00

    # Extreme eCPM -> decays sharply towards 0.0
    outcome_extreme = SimulationOutcome(
        ladder=dummy_ladder,
        spend_stats=SpendStats(900000, 900000, 900000, 900000, 900000, 1.0),
        economic_stats=EconomicStats(views, 300.0, 0.85, {"tier1": 0.85}),
        per_simulation_spend=dummy_spend,
    )
    _, trace_extreme = scorer.score_outcome(outcome_extreme, budget)
    assert trace_extreme["ecpm_efficiency_score"] < 0.20
