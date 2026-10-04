import tempfile
import gc
from pathlib import Path

from mimed.data.generator import generate_synthetic_dataset
from mimed.data.database import get_connection
from mimed.data.repositories import CampaignRepository, CreatorRepository, PostRepository
from mimed.optimization.optimizer import MilestoneOptimizer


def test_optimizer_full_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "opt_test.db"
        generate_synthetic_dataset(seed=42, db_path=db_path)

        conn = get_connection(db_path)
        try:
            camp_repo = CampaignRepository(conn)
            creator_repo = CreatorRepository(conn)
            post_repo = PostRepository(conn)

            campaigns = camp_repo.get_all()
            assert len(campaigns) > 0

            target_camp = campaigns[-1]  # Pick the latest campaign

            optimizer = MilestoneOptimizer(camp_repo, creator_repo, post_repo)
            result = optimizer.optimize_campaign(target_camp.campaign_id, seed=42)

            assert result.campaign_id == target_camp.campaign_id
            assert len(result.recommended_ladder.milestones) >= 2
            assert result.spend_stats.budget_confidence >= 0.70
            assert result.economic_stats.expected_views > 0
            assert result.economic_stats.effective_cpm > 0
            assert result.candidates_pareto > 0

            # Test formatting output string
            summary = result.format_summary()
            assert "Selected policy:" in summary
            assert "Probability within budget:" in summary
            assert "Raw Metrics:" in summary
            assert "Completion rate:" in summary
            assert "Expected budget utilization:" in summary


        finally:
            conn.close()
            del conn
            gc.collect()
