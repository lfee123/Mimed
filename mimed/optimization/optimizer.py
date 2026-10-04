import time
from datetime import datetime
from typing import List, Optional, Tuple
import numpy as np

from mimed.config import OptimizerConfig
from mimed.domain import Campaign, Creator, OptimizationResult
from mimed.data.repositories import (
    CampaignRepository,
    CreatorRepository,
    PostRepository,
)
from mimed.modeling.segment_resolver import SegmentResolver
from mimed.modeling.view_distribution import ViewDistributionModel
from mimed.optimization.candidate_generator import CandidateGenerator
from mimed.optimization.simulator import CampaignSimulator, SimulationOutcome
from mimed.optimization.constraints import ConstraintEngine
from mimed.optimization.scorer import MultiObjectiveScorer


class MilestoneOptimizer:
    def __init__(
        self,
        camp_repo: CampaignRepository,
        creator_repo: CreatorRepository,
        post_repo: PostRepository,
        config: Optional[OptimizerConfig] = None,
    ):
        self.camp_repo = camp_repo
        self.creator_repo = creator_repo
        self.post_repo = post_repo
        self.config = config or OptimizerConfig()

        self.segment_resolver = SegmentResolver(
            post_repo=post_repo,
            creator_repo=creator_repo,
            min_obs=self.config.min_segment_observations,
        )
        self.constraint_engine = ConstraintEngine(
            min_budget_confidence=self.config.budget_confidence_level
        )
        self.scorer = MultiObjectiveScorer(config=self.config)

    def optimize_campaign(self, campaign_id: str, seed: int = None) -> OptimizationResult:
        """Run milestone optimization pipeline for a target campaign."""
        t_start = time.perf_counter()
        actual_seed = seed if seed is not None else 42

        campaign = self.camp_repo.get_by_id(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign '{campaign_id}' not found in database.")

        # 1. Resolve segment with cold-start fallback (strict temporal filtering)
        segment_res = self.segment_resolver.resolve_segment(campaign)

        # Map all creators for quick lookup
        all_creators_map = {c.creator_id: c for c in self.creator_repo.get_all()}

        # Target creator pool for campaign simulation matched to campaign.expected_creators
        matched_creators = self.creator_repo.get_by_platform_and_tier(
            platform=campaign.platform, tier=campaign.target_creator_tier
        )
        if not matched_creators:
            matched_creators = [c for c in self.creator_repo.get_all() if c.platform == campaign.platform]
        if not matched_creators:
            matched_creators = self.creator_repo.get_all()

        target_count = campaign.expected_creators
        if len(matched_creators) >= target_count:
            target_creators = matched_creators[:target_count]
        else:
            repeats = (target_count // len(matched_creators)) + 1
            target_creators = (matched_creators * repeats)[:target_count]

        # 2. Fit View Distribution Model
        view_model = ViewDistributionModel.fit(
            historical_posts=segment_res.posts, creators_map=all_creators_map
        )

        # 3. Generate Candidate Ladders
        candidate_gen = CandidateGenerator(campaign=campaign, view_model=view_model)
        candidate_ladders = candidate_gen.generate_candidate_ladders()

        if not candidate_ladders:
            raise ValueError(f"No valid candidate ladders could be generated for campaign '{campaign_id}'.")

        # 4. Pre-sample Vectorized Views Matrix across target creators
        simulator = CampaignSimulator(campaign=campaign, target_creators=target_creators)
        views_matrix = view_model.sample_views_for_creators(
            creators=target_creators,
            n_simulations=self.config.simulations_count,
            seed=actual_seed,
        )

        # 5. Simulate & Evaluate candidates
        feasible_outcomes: List[Tuple[SimulationOutcome, float, dict]] = []
        all_evaluated: List[Tuple[SimulationOutcome, float, dict]] = []

        for ladder in candidate_ladders:
            outcome = simulator.evaluate_ladder(ladder=ladder, views_matrix=views_matrix)
            score, trace = self.scorer.score_outcome(outcome, campaign.total_budget)
            all_evaluated.append((outcome, score, trace))

            if self.constraint_engine.is_feasible(outcome, campaign.total_budget):
                feasible_outcomes.append((outcome, score, trace))

        # 6. Compute Pareto Optimal Set across 4 objectives
        target_pool = feasible_outcomes if feasible_outcomes else all_evaluated
        pareto_outcomes = self._get_pareto_subset(target_pool)
        pareto_count = len(pareto_outcomes)

        # 7. Rank candidates: select highest weighted composite score among Pareto feasible candidates
        if feasible_outcomes:
            pareto_outcomes.sort(key=lambda x: x[1], reverse=True)
            best_outcome, best_score, best_trace = pareto_outcomes[0]
        else:
            all_evaluated.sort(key=lambda x: x[0].spend_stats.budget_confidence, reverse=True)
            best_outcome, best_score, best_trace = all_evaluated[0]

        segment_meta = {
            "segment_key": segment_res.segment_key,
            "fallback_level": segment_res.fallback_level,
            "obs_count": segment_res.obs_count,
            "confidence_score": segment_res.confidence_score,
            "suspicious_rate": segment_res.suspicious_rate,
            "suspicious_post_count": segment_res.suspicious_post_count,
        }

        t_end = time.perf_counter()
        runtime_seconds = t_end - t_start
        run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{campaign_id}"

        return OptimizationResult(
            campaign_id=campaign_id,
            recommended_ladder=best_outcome.ladder,
            spend_stats=best_outcome.spend_stats,
            economic_stats=best_outcome.economic_stats,
            segment_metadata=segment_meta,
            scoring_trace=best_trace,
            score=best_score,
            seed=actual_seed,
            candidates_generated=len(candidate_ladders),
            candidates_feasible=len(feasible_outcomes),
            candidates_pareto=pareto_count,
            mu_ci_95=view_model.mu_ci_95,
            sigma_ci_95=view_model.sigma_ci_95,
            runtime_seconds=runtime_seconds,
            run_id=run_id,
        )

    def _get_pareto_subset(
        self, items: List[Tuple[SimulationOutcome, float, dict]]
    ) -> List[Tuple[SimulationOutcome, float, dict]]:
        if not items:
            return []

        # Extract objective vectors: [accessibility, ecpm_efficiency, fairness, budget_utilization]
        objs = [
            [
                trace.get("accessibility_score", 0.0),
                trace.get("ecpm_efficiency_score", 0.0),
                trace.get("fairness_score", 0.0),
                trace.get("budget_utilization_score", 0.0),
            ]
            for _, _, trace in items
        ]

        objs_arr = np.array(objs, dtype=np.float64)
        # Vectorized Pareto dominance check (i dominates j)
        ge = objs_arr[:, np.newaxis, :] >= objs_arr[np.newaxis, :, :]
        gt = objs_arr[:, np.newaxis, :] > objs_arr[np.newaxis, :, :]

        all_ge = np.all(ge, axis=2)
        any_gt = np.any(gt, axis=2)
        dominates = all_ge & any_gt

        is_dominated = np.any(dominates, axis=0)
        return [item for i, item in enumerate(items) if not is_dominated[i]]

    def _compute_pareto_count(
        self, items: List[Tuple[SimulationOutcome, float, dict]]
    ) -> int:
        return len(self._get_pareto_subset(items))


