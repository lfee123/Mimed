from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple

@dataclass(frozen=True)
class Milestone:
    rank: int
    view_threshold: int
    payout_amount: float  # Cumulative payout amount for reaching this milestone

    def __post_init__(self):
        if self.rank < 1:
            raise ValueError(f"Milestone rank must be >= 1, got {self.rank}")
        if self.view_threshold <= 0:
            raise ValueError(f"View threshold must be positive, got {self.view_threshold}")
        if self.payout_amount <= 0:
            raise ValueError(f"Payout amount must be positive, got {self.payout_amount}")


@dataclass
class MilestoneLadder:
    campaign_id: str
    milestones: List[Milestone] = field(default_factory=list)

    def __post_init__(self):
        # Sort milestones by rank
        self.milestones.sort(key=lambda m: m.rank)
        self.validate()

    def validate(self) -> None:
        """Enforce strict monotonic increasing thresholds and cumulative payouts."""
        for i in range(len(self.milestones) - 1):
            curr_m = self.milestones[i]
            next_m = self.milestones[i + 1]

            if next_m.view_threshold <= curr_m.view_threshold:
                raise ValueError(
                    f"Milestone thresholds must be strictly increasing: "
                    f"rank {curr_m.rank} ({curr_m.view_threshold}) >= rank {next_m.rank} ({next_m.view_threshold})"
                )
            if next_m.payout_amount <= curr_m.payout_amount:
                raise ValueError(
                    f"Cumulative payouts must be strictly increasing: "
                    f"rank {curr_m.rank} ({curr_m.payout_amount}) >= rank {next_m.rank} ({next_m.payout_amount})"
                )

    def calculate_payout(self, views: int) -> float:
        """
        Calculate total cumulative payout earned for a given view count.
        Payouts are cumulative, so hitting threshold X unlocks payout_amount X.
        """
        earned = 0.0
        for m in self.milestones:
            if views >= m.view_threshold:
                earned = m.payout_amount
            else:
                break
        return earned

    def get_highest_milestone_rank(self, views: int) -> int:
        """Returns the highest rank achieved for a given view count (0 if none reached)."""
        rank = 0
        for m in self.milestones:
            if views >= m.view_threshold:
                rank = m.rank
            else:
                break
        return rank

    def to_list_of_dicts(self) -> List[Dict[str, Any]]:
        return [
            {
                "campaign_id": self.campaign_id,
                "milestone_rank": m.rank,
                "view_threshold": m.view_threshold,
                "payout_amount": m.payout_amount,
            }
            for m in self.milestones
        ]
