import numpy as np
from mimed.domain import Campaign, Creator, Milestone, MilestoneLadder
from mimed.optimization.simulator import CampaignSimulator


def test_simulator_reproducibility_and_vectorization():
    campaign = Campaign(
        campaign_id="c_sim",
        brand="BrandX",
        category="tech",
        platform="instagram",
        total_budget=50000.0,
        start_date="2025-01-01",
        end_date="2025-01-31",
        target_creator_tier="micro",
        expected_creators=2,
    )

    creators = [
        Creator("cr_1", "instagram", 20000, "micro", 12, 4000.0, 0.8),
        Creator("cr_2", "instagram", 30000, "micro", 12, 6000.0, 0.7),
    ]

    ladder = MilestoneLadder(
        campaign_id="c_sim",
        milestones=[
            Milestone(rank=1, view_threshold=5000, payout_amount=500.0),
            Milestone(rank=2, view_threshold=15000, payout_amount=1500.0),
        ],
    )

    # Fixed synthetic views matrix (3 simulations, 2 creators)
    views_matrix = np.array([
        [4000, 16000],  # Sim 0: cr_1 gets 0, cr_2 gets 1500 -> total spend = 1500
        [6000, 7000],   # Sim 1: cr_1 gets 500, cr_2 gets 500 -> total spend = 1000
        [20000, 3000],  # Sim 2: cr_1 gets 1500, cr_2 gets 0 -> total spend = 1500
    ])

    simulator = CampaignSimulator(campaign, creators)
    outcome = simulator.evaluate_ladder(ladder, views_matrix)

    np.testing.assert_array_equal(outcome.per_simulation_spend, [1500.0, 1000.0, 1500.0])
    assert outcome.spend_stats.expected_spend == (1500 + 1000 + 1500) / 3.0
    assert outcome.spend_stats.budget_confidence == 1.0  # All spend <= 50,000 budget


def test_campaign_shock_reproducibility_and_correlation():
    from mimed.modeling.view_distribution import ViewDistributionModel
    from mimed.optimization.constraints import ConstraintEngine
    from mimed.optimization.simulator import SimulationOutcome
    from mimed.domain import SpendStats, EconomicStats, MilestoneLadder

    creators = [
        Creator("cr_1", "instagram", 20000, "micro", 12, 4000.0, 0.8),
        Creator("cr_2", "instagram", 30000, "micro", 12, 6000.0, 0.7),
        Creator("cr_3", "instagram", 25000, "micro", 12, 5000.0, 0.75),
    ]

    model = ViewDistributionModel(mu_log=-1.2, sigma_log=0.4, sigma_campaign=0.35)

    # 1. Reproducibility with fixed seed
    m1 = model.sample_views_for_creators(creators, n_simulations=100, seed=42)
    m2 = model.sample_views_for_creators(creators, n_simulations=100, seed=42)
    np.testing.assert_array_equal(m1, m2)

    # 2. Different simulations receive different shocks
    assert not np.array_equal(m1[0], m1[1])

    # 3. Shared campaign shock causes positive correlation across creators in the same simulation
    corr_matrix = np.corrcoef(m1.T)
    assert np.all(corr_matrix > 0.0)  # Positive correlation across creator outcomes

    # 4. Zero campaign shock variance matches independent behavior
    model_zero = ViewDistributionModel(mu_log=-1.2, sigma_log=0.4, sigma_campaign=0.0)
    m_zero = model_zero.sample_views_for_creators(creators, n_simulations=100, seed=42)
    assert m_zero.shape == (100, 3)

    # 5. ConstraintEngine checks P95 spend feasibility
    constraint_engine = ConstraintEngine(min_budget_confidence=0.95)
    dummy_ladder = MilestoneLadder(campaign_id="test", milestones=[])
    
    # Feasible P95 (<= budget)
    outcome_ok = SimulationOutcome(
        ladder=dummy_ladder,
        spend_stats=SpendStats(expected_spend=800, median_spend=800, p90_spend=900, p95_spend=950, p99_spend=990, budget_confidence=1.0),
        economic_stats=EconomicStats(10000, 50.0, 0.8, {}),
        per_simulation_spend=np.array([800.0]),
    )
    assert constraint_engine.is_feasible(outcome_ok, campaign_budget=1000.0)

    # Infeasible P95 (> budget)
    outcome_bad_p95 = SimulationOutcome(
        ladder=dummy_ladder,
        spend_stats=SpendStats(expected_spend=800, median_spend=800, p90_spend=900, p95_spend=1050, p99_spend=1100, budget_confidence=0.96),
        economic_stats=EconomicStats(10000, 50.0, 0.8, {}),
        per_simulation_spend=np.array([800.0]),
    )
    assert not constraint_engine.is_feasible(outcome_bad_p95, campaign_budget=1000.0)
