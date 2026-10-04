"""
Creator Performance & As-Of-Date Historical Feature Extraction.
Guarantees strict temporal anti-leakage: calculates creator features using ONLY posts published prior to as_of_date.
"""
import math
from dataclasses import dataclass
from typing import List, Optional
import numpy as np

from mimed.domain import Post
from mimed.data.repositories import PostRepository, MilestoneLadderRepository


@dataclass
class CreatorHistoricalFeatures:
    creator_id: str
    as_of_date: str
    observation_count: int
    historical_avg_views_per_post: float
    historical_completion_rate: float
    recent_vs_historical_ratio: float
    log_view_slope: float
    historical_volatility: float


class CreatorPerformanceService:
    def __init__(self, post_repo: PostRepository, ladder_repo: Optional[MilestoneLadderRepository] = None):
        self.post_repo = post_repo
        self.ladder_repo = ladder_repo

    def get_creator_historical_features(self, creator_id: str, as_of_date: str) -> CreatorHistoricalFeatures:
        """
        Extract historical creator performance features strictly prior to as_of_date.
        Excludes posts published on or after as_of_date (post_date < as_of_date).
        """
        posts = self.post_repo.get_posts_by_creator_before_date(creator_id, as_of_date)
        clean_posts = [p for p in posts if not p.flagged_suspicious]

        if not clean_posts:
            return CreatorHistoricalFeatures(
                creator_id=creator_id,
                as_of_date=as_of_date,
                observation_count=0,
                historical_avg_views_per_post=0.0,
                historical_completion_rate=0.5,
                recent_vs_historical_ratio=1.0,
                log_view_slope=0.0,
                historical_volatility=0.30,
            )

        n = len(clean_posts)
        views = [p.views_final for p in clean_posts]
        avg_views = float(np.mean(views))

        # Completion rate prior to as_of_date
        completed = 0
        for p in clean_posts:
            if self.ladder_repo:
                ladder = self.ladder_repo.get_by_campaign_id(p.campaign_id)
                if ladder and ladder.milestones:
                    if p.views_final >= ladder.milestones[0].view_threshold:
                        completed += 1
            else:
                # Default completion proxy if no ladder repo passed
                if p.total_payout_earned > 0:
                    completed += 1

        comp_rate = completed / float(n) if n > 0 else 0.5

        # Trend & Volatility
        if n >= 2:
            recent_avg = float(np.mean(views[-min(3, n):]))
            hist_avg = float(np.mean(views[:-min(3, n)])) if n > 3 else avg_views
            ratio = recent_avg / max(1.0, hist_avg)

            log_views = np.log(np.maximum(1, views))
            x = np.arange(n)
            if np.std(x) > 0:
                slope, _ = np.polyfit(x, log_views, 1)
            else:
                slope = 0.0
            volatility = float(np.std(log_views))
        else:
            ratio = 1.0
            slope = 0.0
            volatility = 0.30

        return CreatorHistoricalFeatures(
            creator_id=creator_id,
            as_of_date=as_of_date,
            observation_count=n,
            historical_avg_views_per_post=avg_views,
            historical_completion_rate=comp_rate,
            recent_vs_historical_ratio=ratio,
            log_view_slope=float(slope),
            historical_volatility=max(0.10, volatility),
        )
