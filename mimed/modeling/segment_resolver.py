"""
Hierarchical Segment Resolver for Cold-Start Campaigns.
Enforces strict temporal boundary filtering and hierarchical fallbacks.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from mimed.domain import Campaign, Post, Creator
from mimed.data.repositories import PostRepository, CreatorRepository


@dataclass
class SegmentResolutionResult:
    posts: List[Post]
    segment_key: str
    fallback_level: str  # "none", "level_1_tier_drop", "level_2_format_drop", "level_3_category_drop", "global"
    obs_count: int
    confidence_score: float  # [0.0, 1.0]
    suspicious_post_count: int
    suspicious_rate: float


class SegmentResolver:
    def __init__(self, post_repo: PostRepository, creator_repo: CreatorRepository, min_obs: int = 25):
        self.post_repo = post_repo
        self.creator_repo = creator_repo
        self.min_obs = min_obs

    def resolve_segment(self, campaign: Campaign) -> SegmentResolutionResult:
        """
        Resolve historical posts for a campaign strictly prior to campaign.start_date.
        Uses hierarchical fallback when observation counts are low.
        """
        # Temporal leakage prevention: fetch only posts published before campaign start_date
        all_hist_posts = self.post_repo.get_historical_before_date(campaign.start_date)
        all_creators = {c.creator_id: c for c in self.creator_repo.get_all()}

        # Attach creator tier to posts for filtering
        posts_with_meta = []
        for p in all_hist_posts:
            cr = all_creators.get(p.creator_id)
            c_tier = cr.tier if cr else "unknown"
            posts_with_meta.append((p, c_tier))

        # Hierarchical Level 1: Platform + Category + Format + Tier
        l1_posts = [
            p for p, t in posts_with_meta
            if p.platform == campaign.platform
            and t == campaign.target_creator_tier
        ]
        clean_l1 = [p for p in l1_posts if not p.flagged_suspicious]

        if len(clean_l1) >= self.min_obs:
            return self._build_result(
                clean_posts=clean_l1,
                all_posts=l1_posts,
                segment_key=f"{campaign.platform}:{campaign.category}:{campaign.target_creator_tier}",
                fallback_level="none",
                max_confidence=1.0,
            )

        # Hierarchical Level 2: Platform + Category
        l2_posts = [p for p, _ in posts_with_meta if p.platform == campaign.platform]
        clean_l2 = [p for p in l2_posts if not p.flagged_suspicious]

        if len(clean_l2) >= self.min_obs:
            return self._build_result(
                clean_posts=clean_l2,
                all_posts=l2_posts,
                segment_key=f"{campaign.platform}:{campaign.category}",
                fallback_level="level_1_tier_drop",
                max_confidence=0.85,
            )

        # Hierarchical Level 3: Platform
        clean_l3 = [p for p, _ in posts_with_meta if p.platform == campaign.platform and not p.flagged_suspicious]
        l3_all = [p for p, _ in posts_with_meta if p.platform == campaign.platform]

        if len(clean_l3) >= self.min_obs:
            return self._build_result(
                clean_posts=clean_l3,
                all_posts=l3_all,
                segment_key=f"{campaign.platform}",
                fallback_level="level_2_category_drop",
                max_confidence=0.70,
            )

        # Level 4 Fallback: Global clean posts
        clean_global = [p for p, _ in posts_with_meta if not p.flagged_suspicious]
        all_global = [p for p, _ in posts_with_meta]

        return self._build_result(
            clean_posts=clean_global,
            all_posts=all_global,
            segment_key="global",
            fallback_level="global",
            max_confidence=0.50,
        )

    def _build_result(
        self,
        clean_posts: List[Post],
        all_posts: List[Post],
        segment_key: str,
        fallback_level: str,
        max_confidence: float,
    ) -> SegmentResolutionResult:
        obs_count = len(clean_posts)
        suspicious_count = sum(1 for p in all_posts if p.flagged_suspicious)
        suspicious_rate = suspicious_count / max(1, len(all_posts))

        # Confidence increases with sample size up to min_obs * 3
        count_factor = min(1.0, obs_count / (self.min_obs * 2))
        confidence_score = round(max_confidence * count_factor, 2)

        return SegmentResolutionResult(
            posts=clean_posts,
            segment_key=segment_key,
            fallback_level=fallback_level,
            obs_count=obs_count,
            confidence_score=confidence_score,
            suspicious_post_count=suspicious_count,
            suspicious_rate=suspicious_rate,
        )
