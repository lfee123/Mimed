"""
Backtest Runner Engine.
Executes temporal backtesting over historical campaigns, comparing historical vs baseline vs optimized ladders.
"""
from typing import List
import pandas as pd

from mimed.config import RESULTS_DIR
from mimed.domain import Campaign, Post, Milestone, MilestoneLadder
from mimed.data.repositories import (
    CampaignRepository,
    CreatorRepository,
    PostRepository,
    MilestoneLadderRepository,
)
from mimed.optimization.optimizer import MilestoneOptimizer
from mimed.optimization.payout_policy import PayoutPolicy
from mimed.backtest.metrics import LadderEvaluation, CampaignBacktestResult


class BacktestRunner:
    def __init__(
        self,
        camp_repo: CampaignRepository,
        creator_repo: CreatorRepository,
        post_repo: PostRepository,
        ladder_repo: MilestoneLadderRepository,
    ):
        self.camp_repo = camp_repo
        self.creator_repo = creator_repo
        self.post_repo = post_repo
        self.ladder_repo = ladder_repo
        self.optimizer = MilestoneOptimizer(camp_repo, creator_repo, post_repo)

    def run_backtest(self, min_warmup_campaigns: int = 3) -> pd.DataFrame:
        """
        Run backtest on campaigns that have sufficient historical data preceding them.
        """
        all_campaigns = self.camp_repo.get_all()
        if len(all_campaigns) <= min_warmup_campaigns:
            # If few campaigns, backtest all except the very first
            eval_campaigns = all_campaigns[1:]
        else:
            eval_campaigns = all_campaigns[min_warmup_campaigns:]

        results: List[CampaignBacktestResult] = []

        for camp in eval_campaigns:
            res = self._backtest_single_campaign(camp)
            if res:
                results.append(res)

        # Build pandas summary DataFrame
        summary_rows = [r.to_summary_dict() for r in results]
        df = pd.DataFrame(summary_rows)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = RESULTS_DIR / "backtest_results.csv"
        df.to_csv(csv_path, index=False)

        return df

    def _backtest_single_campaign(self, campaign: Campaign) -> CampaignBacktestResult:
        # Actual posts recorded for this campaign
        actual_posts = self.post_repo.get_by_campaign(campaign.campaign_id)
        if not actual_posts:
            return None

        # 1. Historical Actual Ladder
        hist_ladder = self.ladder_repo.get_by_campaign_id(campaign.campaign_id)
        hist_eval = self._evaluate_ladder_on_posts(campaign, hist_ladder, actual_posts, "historical")

        # 2. Baseline Ladder (Fixed quantile rule: P40 & P80, fixed 30% payout share)
        baseline_ladder = self._generate_baseline_ladder(campaign, actual_posts)
        base_eval = self._evaluate_ladder_on_posts(campaign, baseline_ladder, actual_posts, "baseline")

        # 3. Optimized Ladder (Temporal horizon strictly < campaign.start_date)
        opt_res = self.optimizer.optimize_campaign(campaign.campaign_id, seed=42)
        opt_ladder = opt_res.recommended_ladder
        opt_eval = self._evaluate_ladder_on_posts(campaign, opt_ladder, actual_posts, "optimized")

        return CampaignBacktestResult(
            campaign_id=campaign.campaign_id,
            brand=campaign.brand,
            category=campaign.category,
            platform=campaign.platform,
            target_tier=campaign.target_creator_tier,
            total_budget=campaign.total_budget,
            historical_eval=hist_eval,
            baseline_eval=base_eval,
            optimized_eval=opt_eval,
        )

    def _generate_baseline_ladder(self, campaign: Campaign, actual_posts: List[Post]) -> MilestoneLadder:
        """Simple rule-based baseline ladder generated from historical posts prior to campaign.start_date."""
        hist_posts = self.post_repo.get_historical_before_date(campaign.start_date)
        views_list = [p.views_final for p in hist_posts if not p.flagged_suspicious]
        if not views_list:
            views_list = [10000, 50000]

        import numpy as np
        p40 = int(np.percentile(views_list, 40))
        p80 = int(np.percentile(views_list, 80))

        policy = PayoutPolicy(reward_share=0.30, target_ecpm=35.0)
        return policy.generate_payouts_for_thresholds(campaign.campaign_id, [p40, p80])


    def _evaluate_ladder_on_posts(
        self,
        campaign: Campaign,
        ladder: MilestoneLadder,
        posts: List[Post],
        ladder_type: str,
    ) -> LadderEvaluation:
        if not ladder or not ladder.milestones:
            return LadderEvaluation(
                ladder_type=ladder_type,
                actual_payout=0.0,
                total_budget=campaign.total_budget,
                budget_utilization=0.0,
                exceeded_budget=False,
                expected_views=0.0,
                actual_views=0.0,
                effective_cpm=0.0,
                completion_rate=0.0,
                first_milestone_reach_rate=0.0,
            )

        total_payout = 0.0
        total_views = 0
        reached_first_count = 0

        first_thresh = ladder.milestones[0].view_threshold

        for p in posts:
            payout = ladder.calculate_payout(p.views_final)
            total_payout += payout
            total_views += p.views_final
            if p.views_final >= first_thresh:
                reached_first_count += 1

        n_posts = len(posts)
        completion_rate = reached_first_count / n_posts if n_posts > 0 else 0.0
        budget_utilization = total_payout / max(1.0, campaign.total_budget)
        exceeded = total_payout > campaign.total_budget
        ecpm = (total_payout / (total_views / 1000.0)) if total_views > 0 else 0.0

        return LadderEvaluation(
            ladder_type=ladder_type,
            actual_payout=round(total_payout, 2),
            total_budget=campaign.total_budget,
            budget_utilization=round(budget_utilization, 4),
            exceeded_budget=exceeded,
            expected_views=float(total_views),
            actual_views=float(total_views),
            effective_cpm=round(ecpm, 2),
            completion_rate=round(completion_rate, 4),
            first_milestone_reach_rate=round(completion_rate, 4),
        )
