"""
Payout Policy Module.
Calculates cumulative payouts rooted in effective CPM / media value economics.
"""
import math
from typing import List
from mimed.domain import Milestone, MilestoneLadder


class PayoutPolicy:
    def __init__(self, reward_share: float = 0.35, target_ecpm: float = 40.0):
        """
        :param reward_share: Fraction of estimated media value allocated to creator payouts.
        :param target_ecpm: Effective CPM anchor (INR per 1,000 views).
        """
        self.reward_share = reward_share
        self.target_ecpm = target_ecpm

    def generate_payouts_for_thresholds(
        self,
        campaign_id: str,
        view_thresholds: List[int],
        target_budget_anchor: float = None,
    ) -> MilestoneLadder:
        """
        Convert a list of view thresholds into a cumulative MilestoneLadder.
        Calculates cumulative payouts using media value, target eCPM anchors, and optional target budget anchor.
        """
        sorted_thresh = sorted(view_thresholds)
        n = len(sorted_thresh)
        if n == 0:
            return MilestoneLadder(campaign_id=campaign_id, milestones=[])

        # Media value for each threshold = threshold * (target_ecpm / 1000)
        # Creator cumulative payout pool = media_value * reward_share
        raw_payouts = [
            (th / 1000.0) * self.target_ecpm * self.reward_share
            for th in sorted_thresh
        ]

        if target_budget_anchor is not None and target_budget_anchor > 0 and raw_payouts[-1] > 0:
            max_raw = raw_payouts[-1]
            payouts = [
                max(p, target_budget_anchor * (p / max_raw))
                for p in raw_payouts
            ]
        else:
            payouts = raw_payouts

        # Enforce strict monotonicity and round payouts to clean numbers
        clean_milestones = []
        prev_payout = 0.0

        for idx, (th, p_val) in enumerate(zip(sorted_thresh, payouts)):
            # Round payout to clean currency increment (e.g. round to nearest 100 or 500)
            rounded_p = self._round_to_clean_currency(p_val)

            # Ensure strict monotonic increase over previous rank
            min_required = prev_payout + max(100.0, rounded_p * 0.15)
            final_payout = max(rounded_p, self._round_to_clean_currency(min_required))

            milestone = Milestone(
                rank=idx + 1,
                view_threshold=th,
                payout_amount=float(final_payout),
            )
            clean_milestones.append(milestone)
            prev_payout = final_payout

        return MilestoneLadder(campaign_id=campaign_id, milestones=clean_milestones)

    @staticmethod
    def _round_to_clean_currency(amount: float) -> float:
        """Round currency amount to human-readable clean numbers (e.g., ₹450 -> ₹500, ₹1840 -> ₹1800)."""
        if amount <= 1_000:
            return float(round(amount, -2)) if amount >= 100 else float(round(amount, -1))
        elif amount <= 10_000:
            return float(round(amount, -2))
        elif amount <= 100_000:
            return float(round(amount, -3))
        else:
            return float(round(amount, -4))
