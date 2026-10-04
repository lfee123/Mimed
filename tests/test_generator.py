import os
import tempfile
from pathlib import Path

from mimed.data.generator import generate_synthetic_dataset
from mimed.validation.data_validation import validate_database_integrity
from mimed.data.database import get_connection
from mimed.data.repositories import CreatorRepository, CampaignRepository, PostRepository


def test_deterministic_generator():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path1 = Path(tmpdir) / "test1.db"
        db_path2 = Path(tmpdir) / "test2.db"

        # Generate twice with same seed
        res1 = generate_synthetic_dataset(seed=42, db_path=db_path1)
        res2 = generate_synthetic_dataset(seed=42, db_path=db_path2)

        assert res1 == res2
        assert res1["creators_count"] > 0
        assert res1["campaigns_count"] > 0
        assert res1["posts_count"] > 0

        # Validate database integrity
        val_res = validate_database_integrity(db_path=db_path1)
        assert val_res["valid"], f"Validation failed with issues: {val_res['issues']}"


def test_creator_archetypes_and_tiers():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_tiers.db"
        generate_synthetic_dataset(seed=42, db_path=db_path)

        conn = get_connection(db_path)
        try:
            creator_repo = CreatorRepository(conn)
            creators = creator_repo.get_all()

            tiers = {c.tier for c in creators}
            assert "nano" in tiers
            assert "micro" in tiers
            assert "mid" in tiers
            assert "macro" in tiers

            for c in creators:
                assert c.follower_count > 0
                assert c.historical_avg_views_per_post > 0
        finally:
            conn.close()


def test_candidate_generator_budget_spans():
    from mimed.modeling.segment_resolver import SegmentResolver
    from mimed.modeling.view_distribution import ViewDistributionModel
    from mimed.optimization.candidate_generator import CandidateGenerator
    from mimed.optimization.simulator import CampaignSimulator

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cand.db"
        generate_synthetic_dataset(seed=42, db_path=db_path)

        conn = get_connection(db_path)
        try:
            camp_repo = CampaignRepository(conn)
            creator_repo = CreatorRepository(conn)
            post_repo = PostRepository(conn)

            campaigns = camp_repo.get_all()
            target_camp = campaigns[0]

            resolver = SegmentResolver(post_repo=post_repo, creator_repo=creator_repo, min_obs=10)
            res = resolver.resolve_segment(target_camp)
            creators_map = {c.creator_id: c for c in creator_repo.get_all()}
            view_model = ViewDistributionModel.fit(res.posts, creators_map)

            cand_gen = CandidateGenerator(target_camp, view_model)
            ladders = cand_gen.generate_candidate_ladders()

            assert len(ladders) > 10

            target_creators = creator_repo.get_by_platform_and_tier(
                platform=target_camp.platform, tier=target_camp.target_creator_tier
            )
            if not target_creators:
                target_creators = creator_repo.get_all()[: target_camp.expected_creators]

            simulator = CampaignSimulator(target_camp, target_creators)
            views_matrix = view_model.sample_views_for_creators(target_creators, n_simulations=500, seed=42)

            utils = []
            for l in ladders:
                outcome = simulator.evaluate_ladder(l, views_matrix)
                utils.append(outcome.spend_stats.expected_spend / target_camp.total_budget)

            assert min(utils) < 0.20
            assert max(utils) > 0.60
        finally:
            conn.close()
