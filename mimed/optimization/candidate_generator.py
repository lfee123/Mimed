"""
Candidate Milestone Ladder Generator.
Derives human-interpretable candidate view threshold ladders and pairs them with payout policies.
"""
from typing import List
from mimed.domain import Campaign, MilestoneLadder
from mimed.modeling.view_distribution import ViewDistributionModel
from mimed.optimization.payout_policy import PayoutPolicy


class CandidateGenerator:
    def __init__(self, campaign: Campaign, view_model: ViewDistributionModel):
        self.campaign = campaign
        self.view_model = view_model

    def generate_candidate_ladders(self) -> List[MilestoneLadder]:
        """
        Derives candidate milestone ladders by exploring combinations of:
        1. Quantile-based view threshold structures
        2. Configurable eCPM anchors and reward share fractions
        """
        candidate_ladders = []
        seen = set()

        # Fine-grained quantile combinations for candidate generation
        quantile_sets = [
            [0.10, 0.30, 0.60],
            [0.15, 0.35, 0.65],
            [0.20, 0.40, 0.70],
            [0.25, 0.50, 0.75],
            [0.30, 0.55, 0.80],
            [0.10, 0.25, 0.50, 0.75],
            [0.15, 0.35, 0.55, 0.80],
            [0.20, 0.40, 0.65, 0.85],
            [0.25, 0.45, 0.70, 0.90],
            [0.10, 0.20, 0.40, 0.60, 0.80],
            [0.15, 0.30, 0.50, 0.70, 0.90],
            [0.20, 0.35, 0.55, 0.75, 0.95],
        ]

        ecpm_targets = [20.0, 40.0, 60.0, 80.0, 100.0, 150.0, 200.0]
        reward_shares = [0.25, 0.35, 0.50, 0.65]

        # Derive per-creator budget envelope
        exp_creators = max(1, self.campaign.expected_creators)
        b_per_creator = self.campaign.total_budget / exp_creators

        # Budget target intensity factors spanning low to high spend (considering milestone reach rates)
        budget_scales = [0.0, 0.20, 0.50, 0.90, 1.30, 1.80, 2.40]

        for q_set in quantile_sets:
            raw_thresholds = [
                int(self.view_model.get_quantile_multiplier(q) * self._get_ref_followers())
                for q in q_set
            ]
            clean_thresholds = [self._round_to_clean_threshold(t) for t in raw_thresholds]
            # Ensure unique and strictly increasing thresholds
            unique_thresh = sorted(list(set(clean_thresholds)))
            if len(unique_thresh) < 2:
                continue

            for ecpm in ecpm_targets:
                for share in reward_shares:
                    for b_scale in budget_scales:
                        target_anchor = (b_scale * b_per_creator) if b_scale > 0 else None
                        policy = PayoutPolicy(reward_share=share, target_ecpm=ecpm)
                        ladder = policy.generate_payouts_for_thresholds(
                            campaign_id=self.campaign.campaign_id,
                            view_thresholds=unique_thresh,
                            target_budget_anchor=target_anchor,
                        )
                        try:
                            ladder.validate()

                            key = tuple(
                                (m.view_threshold, m.payout_amount)
                                for m in ladder.milestones
                            )

                            if key not in seen:
                                seen.add(key)
                                candidate_ladders.append(ladder)

                        except ValueError:
                            continue

        return candidate_ladders


    def _get_ref_followers(self) -> int:
        """Reference follower count derived from target tier bounds."""
        tier_ref = {
            "nano": 5_000,
            "micro": 25_000,
            "mid": 100_000,
            "macro": 500_000,
        }
        return tier_ref.get(self.campaign.target_creator_tier, 25_000)

    @staticmethod
    def _round_to_clean_threshold(val: int) -> int:
        """Round threshold to clean human-readable numbers (e.g. 4,821 -> 5,000, 24,100 -> 25,000)."""
        val = max(1_000, val)
        if val <= 10_000:
            return int(round(val, -3))
        elif val <= 50_000:
            return int(round(val / 5000.0) * 5000)
        elif val <= 250_000:
            return int(round(val / 25000.0) * 25000)
        elif val <= 1_000_000:
            return int(round(val / 50000.0) * 50000)
        else:
            return int(round(val / 100000.0) * 100000)
