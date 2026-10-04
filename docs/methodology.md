# Technical Methodology: Milestone Optimization for Brand Campaigns (`mimed`)

## 1. Problem Formulation
Creator marketplace brand campaigns require milestone payout ladders that incentivize content performance while preventing budget overruns. Unoptimized ladders often cause catastrophic budget breaches (e.g. 200%+ utilization) or set unreachable thresholds that demotivate creators.

`mimed` models campaign payout optimization as a **constrained stochastic optimization problem**:

$$\max_{\mathbf{L} \in \mathcal{L}} \text{Score}(\mathbf{L} \mid B) \quad \text{subject to} \quad P\left(\sum_{i=1}^{N} \text{Payout}(V_i \mid \mathbf{L}) \le B\right) \ge 0.95$$

where:
- $\mathbf{L} = \{(T_k, P_k)\}_{k=1}^K$ is the milestone ladder with view thresholds $T_k$ and cumulative payouts $P_k$.
- $V_i$ is the stochastic view count of creator $i$.
- $B$ is the total campaign budget.

---

## 2. Statistical Modeling & Cold-Start Strategy

### 2.1 View Distribution Model
Because view distributions are heavy-tailed, performance is modeled in log-space over normalized view multipliers:

$$M_i = \frac{\text{views\_final}_i}{\text{follower\_count}_i}$$

A log-normal distribution $\ln(M_i) \sim \mathcal{N}(\mu, \sigma^2)$ is fitted over clean historical post data.

### 2.2 Hierarchical Segment Fallback (Cold Start)
To handle new platforms, categories, or creator tiers with limited history, `mimed` resolves historical data using a 5-level fallback cascade:

1. **Level 1**: `platform + category + format + tier` ($N \ge 25$)
2. **Level 2**: `platform + category` ($N \ge 25$)
3. **Level 3**: `platform` ($N \ge 25$)
4. **Level 4**: `global clean dataset`

Metadata detailing the fallback level, observation count, and confidence score is explicitly returned with every optimization result.

### 2.3 Temporal Anti-Leakage
To prevent data leakage during backtesting and optimization, `mimed` strictly queries historical posts published **prior to the target campaign start date** (`post_date < campaign.start_date`).

---

## 3. Vectorized Monte Carlo Simulation
Rather than re-simulating view outcomes for every candidate ladder, `mimed` pre-samples a reusable view matrix $V \in \mathbb{R}^{N_{\text{sim}} \times N_{\text{creators}}}$.

Using NumPy broadcasting, candidate ladders are evaluated against $V$ in parallel:
- Mask matrix: $M_{s, c, k} = \mathbb{I}(V_{s, c} \ge T_k)$
- Payout matrix: $P_{s, c} = \max_k (M_{s, c, k} \cdot P_k)$
- Campaign spend vector: $S_s = \sum_{c} P_{s, c}$

This vectorized design evaluates 5,000 Monte Carlo simulation instances across dozens of candidate ladders in under 700 milliseconds.

---

## 4. Constraint Enforcement & Multi-Objective Scoring

### Hard Constraint
Candidates failing $P(S_s \le B) \ge 0.95$ are rejected.

### Multi-Objective Objective Function
Feasible ladders are ranked using an explainable weighted composite score:

$$\text{Score} = w_1 \cdot \text{Accessibility} + w_2 \cdot \text{eCPM\_Efficiency} + w_3 \cdot \text{Tier\_Fairness} + w_4 \cdot \text{Budget\_Utilization}$$

- **Accessibility**: First milestone reach rate ($P(V \ge T_1)$).
- **eCPM Efficiency**: Economic alignment with target media value per 1,000 views.
- **Tier Fairness**: Low variance of completion rates across creator tiers.
- **Budget Utilization**: Spend ratio relative to budget ($0.75 \le \text{utilization} \le 0.95$).

---

## 5. Fraud Mitigation
Flagged suspicious posts (`flagged_suspicious == 1`) are filtered out during view distribution fitting to prevent skewed baseline estimations, while suspicious rate statistics are reported as a risk indicator.
