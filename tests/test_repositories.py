import tempfile
import gc
from pathlib import Path

from mimed.data.database import init_db, get_connection
from mimed.data.repositories import CampaignRepository, CreatorRepository, PostRepository, MilestoneLadderRepository
from mimed.domain import Campaign, Creator, Post, Milestone, MilestoneLadder


def test_repository_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "repo_test.db"
        init_db(db_path)

        conn = get_connection(db_path)
        try:
            camp_repo = CampaignRepository(conn)
            creator_repo = CreatorRepository(conn)
            post_repo = PostRepository(conn)
            ladder_repo = MilestoneLadderRepository(conn)

            # Campaign
            camp = Campaign(
                campaign_id="c_test",
                brand="TestBrand",
                category="tech",
                platform="instagram",
                total_budget=100000.0,
                start_date="2025-01-01",
                end_date="2025-01-31",
                target_creator_tier="micro",
                expected_creators=10,
            )
            camp_repo.save(camp)
            fetched_camp = camp_repo.get_by_id("c_test")
            assert fetched_camp == camp

            # Creator
            creator = Creator(
                creator_id="cr_test",
                platform="instagram",
                follower_count=25000,
                tier="micro",
                account_age_months=12,
                historical_avg_views_per_post=5000.0,
                historical_completion_rate=0.8,
            )
            creator_repo.save(creator)
            fetched_cr = creator_repo.get_by_id("cr_test")
            assert fetched_cr == creator

            # Post
            post = Post(
                post_id="p_test",
                campaign_id="c_test",
                creator_id="cr_test",
                post_date="2025-01-10",
                platform="instagram",
                category="tech",
                format="reel",
                views_at_24h=2000,

                views_at_7d=4500,
                views_at_30d=5000,
                views_final=5200,
                total_payout_earned=1000.0,
                flagged_suspicious=False,
            )
            post_repo.save(post)

            # Temporal Cutoff Check
            hist_before_15 = post_repo.get_historical_before_date("2025-01-15")
            assert len(hist_before_15) == 1
            hist_before_05 = post_repo.get_historical_before_date("2025-01-05")
            assert len(hist_before_05) == 0

            # Ladder
            ladder = MilestoneLadder(
                campaign_id="c_test",
                milestones=[
                    Milestone(rank=1, view_threshold=2000, payout_amount=500.0),
                    Milestone(rank=2, view_threshold=5000, payout_amount=1200.0),
                ],
            )
            ladder_repo.save(ladder)
            fetched_ladder = ladder_repo.get_by_campaign_id("c_test")
            assert fetched_ladder is not None
            assert len(fetched_ladder.milestones) == 2
            assert fetched_ladder.calculate_payout(1000) == 0.0
            assert fetched_ladder.calculate_payout(3000) == 500.0
            assert fetched_ladder.calculate_payout(6000) == 1200.0

        finally:
            conn.close()
            del conn
            gc.collect()
