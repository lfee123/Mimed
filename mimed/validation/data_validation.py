"""
Data validation module to verify database integrity, non-negativity constraints,
milestone ladder monotonicity, and campaign/post consistency.
"""
from typing import List, Dict, Any, Optional
from mimed.domain import MilestoneLadder
from mimed.data.database import get_connection
from mimed.data.repositories import CampaignRepository, CreatorRepository, PostRepository, MilestoneLadderRepository


def validate_milestone_ladder_order(ladder: MilestoneLadder) -> List[str]:
    """
    Validates milestone ladder structure.
    Enforces strictly increasing view thresholds (T1 < T2 < T3...)
    and non-decreasing payouts (P1 <= P2 <= P3...).
    Returns a list of error messages describing any violations.
    """
    errors: List[str] = []
    if not ladder.milestones:
        errors.append(f"Campaign {ladder.campaign_id} has an empty milestone ladder.")
        return errors

    ranks_seen = set()
    thresholds_seen = set()

    for i, m in enumerate(ladder.milestones):
        # Rank check
        if m.rank <= 0:
            errors.append(f"Campaign {ladder.campaign_id} milestone at index {i} has invalid rank {m.rank}.")
        if m.rank in ranks_seen:
            errors.append(f"Campaign {ladder.campaign_id} has duplicate milestone rank {m.rank}.")
        ranks_seen.add(m.rank)

        # Threshold check
        if m.view_threshold <= 0:
            errors.append(f"Campaign {ladder.campaign_id} rank {m.rank} has non-positive threshold {m.view_threshold}.")
        if m.view_threshold in thresholds_seen:
            errors.append(f"Campaign {ladder.campaign_id} rank {m.rank} has duplicate threshold {m.view_threshold}.")
        thresholds_seen.add(m.view_threshold)

        # Payout check
        if m.payout_amount < 0:
            errors.append(f"Campaign {ladder.campaign_id} rank {m.rank} has negative payout {m.payout_amount}.")

    # Sequential ordering check
    for i in range(len(ladder.milestones) - 1):
        curr_m = ladder.milestones[i]
        next_m = ladder.milestones[i + 1]

        if next_m.view_threshold <= curr_m.view_threshold:
            errors.append(
                f"Campaign {ladder.campaign_id} rank {next_m.rank} threshold ({next_m.view_threshold}) "
                f"is not strictly greater than rank {curr_m.rank} threshold ({curr_m.view_threshold})."
            )
        if next_m.payout_amount < curr_m.payout_amount:
            errors.append(
                f"Campaign {ladder.campaign_id} rank {next_m.rank} payout ({next_m.payout_amount}) "
                f"is less than rank {curr_m.rank} payout ({curr_m.payout_amount})."
            )

    return errors


def validate_database_integrity(db_path=None) -> Dict[str, Any]:
    """
    Run comprehensive validation checks on database tables.
    Returns dictionary with validation status and findings.
    """
    conn = get_connection(db_path)
    issues: List[str] = []

    try:
        camp_repo = CampaignRepository(conn)
        creator_repo = CreatorRepository(conn)
        post_repo = PostRepository(conn)
        ladder_repo = MilestoneLadderRepository(conn)

        campaigns = camp_repo.get_all()
        creators = creator_repo.get_all()
        posts = post_repo.get_historical_before_date("9999-12-31")

        if not campaigns:
            issues.append("Campaigns table is empty.")
        if not creators:
            issues.append("Creators table is empty.")
        if not posts:
            issues.append("Posts table is empty.")

        camp_map = {c.campaign_id: c for c in campaigns}
        creator_map = {cr.creator_id: cr for cr in creators}

        # 1. Validate Campaigns
        for c in campaigns:
            if c.total_budget <= 0:
                issues.append(f"Campaign {c.campaign_id} has invalid budget: {c.total_budget}")
            if c.expected_creators <= 0:
                issues.append(f"Campaign {c.campaign_id} has non-positive expected creators: {c.expected_creators}")
            if c.start_date >= c.end_date:
                issues.append(f"Campaign {c.campaign_id} start_date >= end_date")

        # 2. Validate Creators
        for cr in creators:
            if cr.follower_count <= 0:
                issues.append(f"Creator {cr.creator_id} has non-positive followers: {cr.follower_count}")
            if cr.account_age_months < 0:
                issues.append(f"Creator {cr.creator_id} has negative account age")

        # 3. Validate Posts & Consistency with Campaign & Creator
        for p in posts:
            camp = camp_map.get(p.campaign_id)
            if not camp:
                issues.append(f"Post {p.post_id} references non-existent campaign_id {p.campaign_id}")
            else:
                if p.platform != camp.platform:
                    issues.append(
                        f"Post {p.post_id} platform '{p.platform}' does not match campaign {camp.campaign_id} platform '{camp.platform}'"
                    )
                if p.category != camp.category:
                    issues.append(
                        f"Post {p.post_id} category '{p.category}' does not match campaign {camp.campaign_id} category '{camp.category}'"
                    )
                if p.post_date < camp.start_date or p.post_date > camp.end_date:
                    issues.append(
                        f"Post {p.post_id} date {p.post_date} outside campaign {camp.campaign_id} window [{camp.start_date}, {camp.end_date}]"
                    )

            if p.creator_id not in creator_map:
                issues.append(f"Post {p.post_id} references non-existent creator_id {p.creator_id}")

            if p.views_at_24h < 0 or p.views_at_7d < 0 or p.views_at_30d < 0 or p.views_final < 0:
                issues.append(f"Post {p.post_id} has negative view metrics")
            if p.total_payout_earned < 0:
                issues.append(f"Post {p.post_id} has negative total_payout_earned: {p.total_payout_earned}")

        # 4. Validate Milestone Ladders
        for c in campaigns:
            ladder = ladder_repo.get_by_campaign_id(c.campaign_id)
            if ladder:
                ladder_errs = validate_milestone_ladder_order(ladder)
                issues.extend(ladder_errs)

    finally:
        conn.close()

    is_valid = len(issues) == 0
    return {
        "valid": is_valid,
        "issues_count": len(issues),
        "issues": issues,
        "campaigns_count": len(campaigns) if 'campaigns' in locals() else 0,
        "creators_count": len(creators) if 'creators' in locals() else 0,
        "posts_count": len(posts) if 'posts' in locals() else 0,
    }
