from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class Post:
    post_id: str
    campaign_id: str
    creator_id: str
    post_date: str  # YYYY-MM-DD
    platform: str
    category: str
    format: str
    views_at_24h: int
    views_at_7d: int
    views_at_30d: int
    views_final: int
    total_payout_earned: float
    flagged_suspicious: bool

    def __post_init__(self):
        if self.views_at_24h < 0 or self.views_at_7d < 0 or self.views_at_30d < 0 or self.views_final < 0:
            raise ValueError("View metrics must be non-negative")
        if self.total_payout_earned < 0:
            raise ValueError("Payout earned cannot be negative")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "campaign_id": self.campaign_id,
            "creator_id": self.creator_id,
            "post_date": self.post_date,
            "platform": self.platform,
            "category": self.category,
            "format": self.format,
            "views_at_24h": self.views_at_24h,
            "views_at_7d": self.views_at_7d,
            "views_at_30d": self.views_at_30d,
            "views_final": self.views_final,
            "total_payout_earned": self.total_payout_earned,
            "flagged_suspicious": 1 if self.flagged_suspicious else 0,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Post":
        return cls(
            post_id=data["post_id"],
            campaign_id=data["campaign_id"],
            creator_id=data["creator_id"],
            post_date=data["post_date"],
            platform=data["platform"],
            category=data["category"],
            format=data["format"],
            views_at_24h=int(data["views_at_24h"]),
            views_at_7d=int(data["views_at_7d"]),
            views_at_30d=int(data["views_at_30d"]),
            views_final=int(data["views_final"]),
            total_payout_earned=float(data["total_payout_earned"]),
            flagged_suspicious=bool(data["flagged_suspicious"]),
        )

