import numpy as np
from mimed.domain import Post, Creator
from mimed.modeling.view_distribution import ViewDistributionModel


def test_view_distribution_fit_and_sampling():
    creator = Creator(
        creator_id="cr_1",
        platform="instagram",
        follower_count=50000,
        tier="micro",
        account_age_months=12,
        historical_avg_views_per_post=10000.0,
        historical_completion_rate=0.7,
    )
    creators_map = {"cr_1": creator}

    posts = [
        Post(
            post_id=f"p_{i}",
            campaign_id="c_1",
            creator_id="cr_1",
            post_date="2025-01-01",
            platform="instagram",
            category="tech",
            format="reel",
            views_at_24h=5000,

            views_at_7d=9000,
            views_at_30d=10000,
            views_final=views,
            total_payout_earned=500.0,
            flagged_suspicious=False,
        )
        for i, views in enumerate([8000, 10000, 12000, 15000, 9000, 11000])
    ]

    model = ViewDistributionModel.fit(posts, creators_map)
    assert model.sigma_log > 0

    # Test sampling matrix shape
    views_matrix = model.sample_views_for_creators([creator], n_simulations=1000, seed=42)
    assert views_matrix.shape == (1000, 1)
    assert np.all(views_matrix >= 100)
