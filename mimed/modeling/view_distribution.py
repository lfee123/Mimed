"""
View distribution fitting and stochastic view multiplier sampling.
Uses log-normal statistics over historical view multipliers (views / follower_count).
"""
import math
from typing import List, Dict, Tuple
import numpy as np

from mimed.domain import Post, Creator


class ViewDistributionModel:
    def __init__(
        self,
        mu_log: float,
        sigma_log: float,
        sigma_campaign: float = 0.35,
        mu_ci_95: Tuple[float, float] = (0.0, 0.0),
        sigma_ci_95: Tuple[float, float] = (0.0, 0.0),
        min_multiplier: float = 0.02,
    ):
        self.mu_log = mu_log
        self.sigma_log = sigma_log
        self.sigma_campaign = sigma_campaign
        self.mu_ci_95 = mu_ci_95
        self.sigma_ci_95 = sigma_ci_95
        self.min_multiplier = min_multiplier

    @classmethod
    def fit(cls, historical_posts: List[Post], creators_map: Dict[str, Creator]) -> "ViewDistributionModel":
        """
        Fit log-normal distribution over clean historical post view multipliers.
        Estimates creator-level variance sigma_log and campaign-level correlated shock variance sigma_campaign.
        """
        multipliers = []
        campaign_posts: Dict[str, List[float]] = {}

        for p in historical_posts:
            if p.flagged_suspicious:
                continue
            creator = creators_map.get(p.creator_id)
            if creator and creator.follower_count > 0:
                mult = p.views_final / creator.follower_count
                if mult > 0:
                    multipliers.append(mult)
                    campaign_posts.setdefault(p.campaign_id, []).append(math.log(mult))

        if not multipliers:
            # Fallback default log-normal parameters if no clean posts available
            return cls(
                mu_log=-1.2,
                sigma_log=0.5,
                sigma_campaign=0.35,
                mu_ci_95=(-1.30, -1.10),
                sigma_ci_95=(0.42, 0.58),
            )

        log_mults = np.log(multipliers)
        n = len(log_mults)
        mu_log = float(np.mean(log_mults))
        sigma_log = float(np.std(log_mults))
        sigma_log = max(0.15, sigma_log)  # Floor variance for numerical stability

        # Estimate campaign-level residual variance across historical campaigns
        camp_means = [np.mean(logs) for cid, logs in campaign_posts.items() if len(logs) >= 2]
        if len(camp_means) >= 2:
            camp_residuals = [m - mu_log for m in camp_means]
            sigma_campaign = float(np.std(camp_residuals))
            sigma_campaign = float(np.clip(sigma_campaign, 0.20, 0.60))
        else:
            sigma_campaign = 0.35  # Principled fallback if < 2 historical campaigns

        # 95% Confidence Intervals
        se_mu = sigma_log / math.sqrt(n)
        mu_ci = (float(mu_log - 1.96 * se_mu), float(mu_log + 1.96 * se_mu))

        se_sigma = sigma_log / math.sqrt(2 * n)
        sigma_ci = (max(0.05, float(sigma_log - 1.96 * se_sigma)), float(sigma_log + 1.96 * se_sigma))

        return cls(
            mu_log=mu_log,
            sigma_log=sigma_log,
            sigma_campaign=sigma_campaign,
            mu_ci_95=mu_ci,
            sigma_ci_95=sigma_ci,
        )


    def sample_multipliers(self, n_samples: int, seed: int = None) -> np.ndarray:
        """
        Sample stochastic view multipliers from log-normal distribution.
        Returns 1D numpy array of shape (n_samples,).
        """
        if seed is not None:
            rng = np.random.default_rng(seed)
            raw_samples = rng.lognormal(mean=self.mu_log, sigma=self.sigma_log, size=n_samples)
        else:
            raw_samples = np.random.lognormal(mean=self.mu_log, sigma=self.sigma_log, size=n_samples)

        return np.maximum(self.min_multiplier, raw_samples)

    def sample_views_for_creators(
        self, creators: List[Creator], n_simulations: int, seed: int = None
    ) -> np.ndarray:
        """
        Generates a 2D matrix of shape (n_simulations, n_creators) containing simulated view counts.
        Includes campaign-level correlated noise sampled ONCE PER SIMULATION and broadcast across creators.
        """
        n_creators = len(creators)
        if n_creators == 0:
            return np.zeros((n_simulations, 0), dtype=np.int64)

        if seed is not None:
            rng = np.random.default_rng(seed)
            creator_noise = rng.normal(loc=0.0, scale=self.sigma_log, size=(n_simulations, n_creators))
            camp_noise = rng.normal(loc=0.0, scale=self.sigma_campaign, size=(n_simulations, 1)) if self.sigma_campaign > 0 else 0.0
        else:
            creator_noise = np.random.normal(loc=0.0, scale=self.sigma_log, size=(n_simulations, n_creators))
            camp_noise = np.random.normal(loc=0.0, scale=self.sigma_campaign, size=(n_simulations, 1)) if self.sigma_campaign > 0 else 0.0

        # Combine: mu_log + creator_noise (S x C) + camp_noise (S x 1)
        log_noise = self.mu_log + creator_noise + camp_noise
        mult_matrix = np.exp(log_noise)
        follower_vector = np.array([c.follower_count for c in creators], dtype=np.float64)

        # Matrix multiplication / broadcasting: shape (n_simulations, n_creators)
        views_matrix = mult_matrix * follower_vector

        return np.maximum(100, views_matrix.astype(np.int64))

    def get_quantile_multiplier(self, q: float) -> float:
        """Calculate quantile multiplier for a given probability q (e.g. 0.50 for median)."""
        from scipy.stats import lognorm
        scale = math.exp(self.mu_log)
        return float(lognorm.ppf(q, s=self.sigma_log, scale=scale))
