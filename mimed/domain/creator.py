from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class Creator:
    creator_id: str
    platform: str
    follower_count: int
    tier: str
    account_age_months: int
    historical_avg_views_per_post: float
    historical_completion_rate: float

    def __post_init__(self):
        if self.follower_count < 0:
            raise ValueError(f"Follower count cannot be negative, got {self.follower_count}")
        if self.account_age_months < 0:
            raise ValueError(f"Account age cannot be negative, got {self.account_age_months}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creator_id": self.creator_id,
            "platform": self.platform,
            "follower_count": self.follower_count,
            "tier": self.tier,
            "account_age_months": self.account_age_months,
            "historical_avg_views_per_post": self.historical_avg_views_per_post,
            "historical_completion_rate": self.historical_completion_rate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Creator":
        return cls(
            creator_id=data["creator_id"],
            platform=data["platform"],
            follower_count=int(data["follower_count"]),
            tier=data["tier"],
            account_age_months=int(data["account_age_months"]),
            historical_avg_views_per_post=float(data["historical_avg_views_per_post"]),
            historical_completion_rate=float(data["historical_completion_rate"]),
        )
