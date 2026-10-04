from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    brand: str
    category: str
    platform: str
    total_budget: float
    start_date: str  # Format: YYYY-MM-DD
    end_date: str    # Format: YYYY-MM-DD
    target_creator_tier: str
    expected_creators: int

    def __post_init__(self):
        if self.total_budget <= 0:
            raise ValueError(f"Campaign budget must be positive, got {self.total_budget}")
        if self.expected_creators <= 0:
            raise ValueError(f"Expected creators must be positive, got {self.expected_creators}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "brand": self.brand,
            "category": self.category,
            "platform": self.platform,
            "total_budget": self.total_budget,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "target_creator_tier": self.target_creator_tier,
            "expected_creators": self.expected_creators,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Campaign":
        return cls(
            campaign_id=data["campaign_id"],
            brand=data["brand"],
            category=data["category"],
            platform=data["platform"],
            total_budget=float(data["total_budget"]),
            start_date=data["start_date"],
            end_date=data["end_date"],
            target_creator_tier=data["target_creator_tier"],
            expected_creators=int(data["expected_creators"]),
        )
