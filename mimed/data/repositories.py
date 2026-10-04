"""
Repository layer for database operations.
"""
import sqlite3
from typing import List, Optional
from mimed.domain import Campaign, Creator, Post, Milestone, MilestoneLadder


class CampaignRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_id(self, campaign_id: str) -> Optional[Campaign]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return Campaign.from_dict(dict(row))

    def get_all(self) -> List[Campaign]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM campaigns ORDER BY start_date ASC")
        return [Campaign.from_dict(dict(row)) for row in cursor.fetchall()]

    def save(self, campaign: Campaign) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO campaigns 
            (campaign_id, brand, category, platform, total_budget, start_date, end_date, target_creator_tier, expected_creators)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                campaign.campaign_id,
                campaign.brand,
                campaign.category,
                campaign.platform,
                campaign.total_budget,
                campaign.start_date,
                campaign.end_date,
                campaign.target_creator_tier,
                campaign.expected_creators,
            ),
        )

    def save_many(self, campaigns: List[Campaign]) -> None:
        for c in campaigns:
            self.save(c)


class CreatorRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_id(self, creator_id: str) -> Optional[Creator]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM creators WHERE creator_id = ?", (creator_id,))
        row = cursor.fetchone()
        return Creator.from_dict(dict(row)) if row else None

    def get_all(self) -> List[Creator]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM creators")
        return [Creator.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_by_platform_and_tier(self, platform: str, tier: str) -> List[Creator]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM creators WHERE platform = ? AND tier = ?", (platform, tier)
        )
        return [Creator.from_dict(dict(row)) for row in cursor.fetchall()]

    def save(self, creator: Creator) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO creators
            (creator_id, platform, follower_count, tier, account_age_months, historical_avg_views_per_post, historical_completion_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                creator.creator_id,
                creator.platform,
                creator.follower_count,
                creator.tier,
                creator.account_age_months,
                creator.historical_avg_views_per_post,
                creator.historical_completion_rate,
            ),
        )

    def save_many(self, creators: List[Creator]) -> None:
        for c in creators:
            self.save(c)


class PostRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_campaign(self, campaign_id: str) -> List[Post]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE campaign_id = ?", (campaign_id,))
        return [Post.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_historical_before_date(self, max_date: str) -> List[Post]:
        """
        Critical temporal leakage filter:
        Retrieves ONLY posts published BEFORE max_date (YYYY-MM-DD).
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE post_date < ? ORDER BY post_date ASC", (max_date,))
        return [Post.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_posts_by_creator_before_date(self, creator_id: str, as_of_date: str) -> List[Post]:
        """
        Retrieves posts for a specific creator strictly prior to as_of_date.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM posts WHERE creator_id = ? AND post_date < ? ORDER BY post_date ASC",
            (creator_id, as_of_date),
        )
        return [Post.from_dict(dict(row)) for row in cursor.fetchall()]

    def save(self, post: Post) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO posts
            (post_id, campaign_id, creator_id, post_date, platform, category, format, views_at_24h, views_at_7d, views_at_30d, views_final, total_payout_earned, flagged_suspicious)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post.post_id,
                post.campaign_id,
                post.creator_id,
                post.post_date,
                post.platform,
                post.category,
                post.format,
                post.views_at_24h,
                post.views_at_7d,
                post.views_at_30d,
                post.views_final,
                post.total_payout_earned,
                1 if post.flagged_suspicious else 0,
            ),
        )

    def save_many(self, posts: List[Post]) -> None:
        for p in posts:
            self.save(p)



class MilestoneLadderRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_by_campaign_id(self, campaign_id: str) -> Optional[MilestoneLadder]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM milestone_ladders WHERE campaign_id = ? ORDER BY milestone_rank ASC",
            (campaign_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None
        milestones = [
            Milestone(
                rank=int(r["milestone_rank"]),
                view_threshold=int(r["view_threshold"]),
                payout_amount=float(r["payout_amount"]),
            )
            for r in rows
        ]
        return MilestoneLadder(campaign_id=campaign_id, milestones=milestones)

    def save(self, ladder: MilestoneLadder) -> None:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM milestone_ladders WHERE campaign_id = ?", (ladder.campaign_id,))
        for m in ladder.milestones:
            cursor.execute(
                """
                INSERT INTO milestone_ladders (campaign_id, milestone_rank, view_threshold, payout_amount)
                VALUES (?, ?, ?, ?)
                """,
                (ladder.campaign_id, m.rank, m.view_threshold, m.payout_amount),
            )
