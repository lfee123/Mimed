"""
Synthetic data generator for mimed.
Generates realistic, controlled stochastic historical creator, campaign, post, and ladder data.
"""
import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Any

import numpy as np

from mimed.config import (
    CREATOR_TIERS,
    TIER_FOLLOWER_BOUNDS,
    SUPPORTED_PLATFORMS,
    SUPPORTED_CATEGORIES,
    SUPPORTED_FORMATS,
    DEFAULT_SEED,
)
from mimed.domain import Campaign, Creator, Post, Milestone, MilestoneLadder
from mimed.data.database import reset_db, get_connection
from mimed.data.repositories import (
    CampaignRepository,
    CreatorRepository,
    PostRepository,
    MilestoneLadderRepository,
)


class LatentCreatorProfile:
    """Internal latent representation used ONLY during synthetic data generation."""

    def __init__(
        self,
        creator_id: str,
        platform: str,
        follower_count: int,
        tier: str,
        archetype: str,
        baseline_strength: float,
        growth_rate: float,
        volatility: float,
        platform_affinity: float,
        join_date: datetime,
    ):
        self.creator_id = creator_id
        self.platform = platform
        self.follower_count = follower_count
        self.tier = tier
        self.archetype = archetype
        self.baseline_strength = baseline_strength
        self.growth_rate = growth_rate
        self.volatility = volatility
        self.platform_affinity = platform_affinity
        self.join_date = join_date


def generate_synthetic_dataset(seed: int = DEFAULT_SEED, db_path=None) -> Dict[str, int]:
    """
    Generate synthetic data deterministically and persist to SQLite database.
    """
    random.seed(seed)
    np.random.seed(seed)

    reset_db(db_path)

    start_sim_date = datetime(2024, 1, 1)

    # 1. Generate Creators
    creators, latent_profiles = _generate_creators(start_sim_date, count=250)

    # 2. Generate Campaigns
    campaigns = _generate_campaigns(start_sim_date, count=12)

    # 3. Generate Historical Baseline Ladders & Posts Chronologically
    posts: List[Post] = []
    ladders: List[MilestoneLadder] = []

    campaign_repo_posts = []

    for campaign in campaigns:
        # Generate baseline ladder for this campaign
        ladder = _generate_historical_ladder(campaign)
        ladders.append(ladder)

        # Select participating creators matching campaign platform / tier preference
        participating_creators = _select_creators_for_campaign(campaign, latent_profiles)

        camp_start = datetime.strptime(campaign.start_date, "%Y-%m-%d")
        camp_end = datetime.strptime(campaign.end_date, "%Y-%m-%d")

        for idx, profile in enumerate(participating_creators):
            post_id = f"post_{campaign.campaign_id}_{profile.creator_id}"
            
            # Post date within campaign window
            days_offset = random.randint(0, max(1, (camp_end - camp_start).days))
            post_dt = camp_start + timedelta(days=days_offset)

            # Skip if creator joined after campaign
            if post_dt < profile.join_date:
                continue

            # Calculate views via latent formula
            views_final, flagged_suspicious = _simulate_post_views(
                profile, campaign, post_dt, start_sim_date
            )

            # Calculate views growth curve (24h, 7d, 30d, final)
            v_24h, v_7d, v_30d = _simulate_view_timeline(views_final, flagged_suspicious)

            # Calculate payout earned based on historical ladder
            payout_earned = ladder.calculate_payout(views_final)

            post_format = random.choice(SUPPORTED_FORMATS)

            post = Post(
                post_id=post_id,
                campaign_id=campaign.campaign_id,
                creator_id=profile.creator_id,
                post_date=post_dt.strftime("%Y-%m-%d"),
                platform=campaign.platform,
                category=campaign.category,
                format=post_format,
                views_at_24h=v_24h,
                views_at_7d=v_7d,
                views_at_30d=v_30d,
                views_final=views_final,
                total_payout_earned=payout_earned,
                flagged_suspicious=flagged_suspicious,
            )

            posts.append(post)

    # Update creator summary statistics in Creator objects based on generated historical posts
    updated_creators = _update_creator_aggregates(creators, posts, ladders)

    # Persist via Repositories
    conn = get_connection(db_path)
    try:
        camp_repo = CampaignRepository(conn)
        creator_repo = CreatorRepository(conn)
        post_repo = PostRepository(conn)
        ladder_repo = MilestoneLadderRepository(conn)

        camp_repo.save_many(campaigns)
        creator_repo.save_many(updated_creators)
        post_repo.save_many(posts)
        for l in ladders:
            ladder_repo.save(l)

        conn.commit()
    finally:
        conn.close()

    return {
        "creators_count": len(updated_creators),
        "campaigns_count": len(campaigns),
        "posts_count": len(posts),
        "ladders_count": len(ladders),
    }


def _generate_creators(
    sim_start: datetime, count: int = 200
) -> Tuple[List[Creator], Dict[str, LatentCreatorProfile]]:
    creators = []
    latent_profiles = {}

    archetypes = ["stable", "growing", "declining", "volatile", "new"]
    archetype_weights = [0.40, 0.25, 0.15, 0.12, 0.08]

    for i in range(1, count + 1):
        creator_id = f"c_{i:04d}"
        platform = random.choice(SUPPORTED_PLATFORMS)
        tier = random.choice(CREATOR_TIERS)
        min_f, max_f = TIER_FOLLOWER_BOUNDS[tier]
        follower_count = int(random.lognormvariate(math.log((min_f + max_f) / 2), 0.5))
        follower_count = max(min_f, min(max_f * 2, follower_count))

        archetype = random.choices(archetypes, weights=archetype_weights)[0]

        account_age_months = random.randint(3, 48) if archetype != "new" else random.randint(1, 3)
        join_date = sim_start - timedelta(days=account_age_months * 30)

        # Latent parameters
        baseline_strength = random.uniform(0.08, 0.45)  # Expected view multiplier
        platform_affinity = random.uniform(0.85, 1.25)

        if archetype == "stable":
            growth_rate = random.uniform(-0.005, 0.005)
            volatility = random.uniform(0.20, 0.40)
        elif archetype == "growing":
            growth_rate = random.uniform(0.02, 0.06)
            volatility = random.uniform(0.25, 0.45)
        elif archetype == "declining":
            growth_rate = random.uniform(-0.05, -0.015)
            volatility = random.uniform(0.25, 0.45)
        elif archetype == "volatile":
            growth_rate = random.uniform(-0.01, 0.01)
            volatility = random.uniform(0.70, 1.10)
        else:  # new
            growth_rate = random.uniform(0.0, 0.03)
            volatility = random.uniform(0.30, 0.60)

        profile = LatentCreatorProfile(
            creator_id=creator_id,
            platform=platform,
            follower_count=follower_count,
            tier=tier,
            archetype=archetype,
            baseline_strength=baseline_strength,
            growth_rate=growth_rate,
            volatility=volatility,
            platform_affinity=platform_affinity,
            join_date=join_date,
        )
        latent_profiles[creator_id] = profile

        # Initial creator object (aggregates updated later)
        creator = Creator(
            creator_id=creator_id,
            platform=platform,
            follower_count=follower_count,
            tier=tier,
            account_age_months=account_age_months,
            historical_avg_views_per_post=follower_count * baseline_strength,
            historical_completion_rate=0.5,
        )
        creators.append(creator)

    return creators, latent_profiles


def _generate_campaigns(sim_start: datetime, count: int = 12) -> List[Campaign]:
    campaigns = []
    brands = [
        "TechNova", "GlowUp", "PixelVerse", "FitLife", "StyleCo",
        "ApexGaming", "PureBotanicals", "CyberByte", "PulseEnergy", "AuraBeauty"
    ]

    base_date = sim_start + timedelta(days=60)

    for i in range(1, count + 1):
        campaign_id = f"camp_{i:03d}"
        brand = random.choice(brands)
        category = random.choice(SUPPORTED_CATEGORIES)
        platform = random.choice(SUPPORTED_PLATFORMS)
        tier = random.choice(CREATOR_TIERS)

        # Campaign dates chronologically progressing
        start_date_dt = base_date + timedelta(days=(i - 1) * 35)
        end_date_dt = start_date_dt + timedelta(days=random.randint(14, 28))

        budget_by_tier = {
            "nano": (50_000, 150_000),
            "micro": (150_000, 400_000),
            "mid": (400_000, 1_000_000),
            "macro": (1_000_000, 2_500_000),
        }
        b_min, b_max = budget_by_tier[tier]
        total_budget = round(random.uniform(b_min, b_max), -3)
        expected_creators = random.randint(15, 60)

        campaign = Campaign(
            campaign_id=campaign_id,
            brand=brand,
            category=category,
            platform=platform,
            total_budget=total_budget,
            start_date=start_date_dt.strftime("%Y-%m-%d"),
            end_date=end_date_dt.strftime("%Y-%m-%d"),
            target_creator_tier=tier,
            expected_creators=expected_creators,
        )
        campaigns.append(campaign)

    return campaigns


def _generate_historical_ladder(campaign: Campaign) -> MilestoneLadder:
    """Generate a realistic baseline ladder for historical campaigns."""
    tier = campaign.target_creator_tier
    base_thresh = {
        "nano": [2_000, 5_000, 10_000, 25_000],
        "micro": [10_000, 25_000, 50_000, 100_000],
        "mid": [50_000, 100_000, 250_000, 500_000],
        "macro": [250_000, 500_000, 1_000_000, 2_500_000],
    }[tier]

    base_payouts = {
        "nano": [500, 1_200, 2_800, 6_000],
        "micro": [2_500, 6_000, 13_000, 28_000],
        "mid": [10_000, 22_000, 55_000, 120_000],
        "macro": [40_000, 90_000, 200_000, 480_000],
    }[tier]

    milestones = [
        Milestone(rank=r + 1, view_threshold=th, payout_amount=float(po))
        for r, (th, po) in enumerate(zip(base_thresh, base_payouts))
    ]
    return MilestoneLadder(campaign_id=campaign.campaign_id, milestones=milestones)


def _select_creators_for_campaign(
    campaign: Campaign, profiles: Dict[str, LatentCreatorProfile]
) -> List[LatentCreatorProfile]:
    # Match platform and tier preferentially, but include some cross-tier
    matched = [
        p for p in profiles.values()
        if p.platform == campaign.platform and p.tier == campaign.target_creator_tier
    ]
    if len(matched) < campaign.expected_creators:
        matched += [
            p for p in profiles.values()
            if p.platform == campaign.platform and p not in matched
        ]

    count = min(len(matched), campaign.expected_creators)
    return random.sample(matched, count) if count > 0 else list(profiles.values())[:campaign.expected_creators]


def _simulate_post_views(
    profile: LatentCreatorProfile,
    campaign: Campaign,
    post_dt: datetime,
    sim_start: datetime,
) -> Tuple[int, bool]:
    months_elapsed = (post_dt - sim_start).days / 30.0

    # Latent factors
    category_factor = 1.15 if random.random() < 0.3 else 0.95
    format_factor = random.uniform(0.9, 1.2)

    base_views = (
        profile.follower_count
        * profile.baseline_strength
        * profile.platform_affinity
        * category_factor
        * format_factor
    )

    time_adjustment = math.exp(profile.growth_rate * months_elapsed)

    # Stochastic noise (log-normal)
    noise = np.random.lognormal(0, profile.volatility)

    # Viral multiplier
    viral_mult = random.uniform(3.5, 8.0) if random.random() < 0.03 else 1.0

    final_views_float = base_views * time_adjustment * noise * viral_mult
    final_views = max(100, int(final_views_float))

    # Flagged suspicious (~4% probability, higher for volatile)
    suspicious_prob = 0.08 if profile.archetype == "volatile" else 0.03
    flagged_suspicious = random.random() < suspicious_prob

    return final_views, flagged_suspicious


def _simulate_view_timeline(views_final: int, flagged_suspicious: bool) -> Tuple[int, int, int]:
    if flagged_suspicious:
        # Fraud/anomaly pattern: massive 24h spike, zero subsequent growth
        p24 = int(views_final * random.uniform(0.92, 0.98))
        p7 = p24
        p30 = views_final
    else:
        # Normal organic growth curve
        r24 = random.uniform(0.35, 0.50)
        r7 = random.uniform(0.70, 0.85)
        r30 = random.uniform(0.92, 0.98)

        p24 = int(views_final * r24)
        p7 = max(p24, int(views_final * r7))
        p30 = max(p7, int(views_final * r30))

    return p24, p7, p30


def _update_creator_aggregates(
    creators: List[Creator], posts: List[Post], ladders: List[MilestoneLadder]
) -> List[Creator]:
    ladder_map = {l.campaign_id: l for l in ladders}
    posts_by_creator: Dict[str, List[Post]] = {}
    for p in posts:
        posts_by_creator.setdefault(p.creator_id, []).append(p)

    updated = []
    for c in creators:
        c_posts = posts_by_creator.get(c.creator_id, [])
        if not c_posts:
            updated.append(c)
            continue

        avg_views = float(np.mean([p.views_final for p in c_posts]))

        completed_count = 0
        for p in c_posts:
            ladder = ladder_map.get(p.campaign_id)
            if ladder and ladder.milestones:
                first_thresh = ladder.milestones[0].view_threshold
                if p.views_final >= first_thresh:
                    completed_count += 1

        comp_rate = completed_count / len(c_posts)

        new_c = Creator(
            creator_id=c.creator_id,
            platform=c.platform,
            follower_count=c.follower_count,
            tier=c.tier,
            account_age_months=c.account_age_months,
            historical_avg_views_per_post=avg_views,
            historical_completion_rate=comp_rate,
        )
        updated.append(new_c)

    return updated
