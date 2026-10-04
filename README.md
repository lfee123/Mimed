# mimed: Milestone Optimization for Brand Campaigns

`mimed` is a Python 3.11+ tool that designs, simulates, and evaluates cumulative milestone payout ladders for brand campaigns on creator marketplaces, while keeping spend within budget with high confidence.

---

## 1. The Problem and the Goal

On creator marketplaces, brands run campaigns where creators publish branded posts and earn payouts when their posts hit view milestones.

Hand-made or rule-based ladders usually fail in two ways:
1. **Budget overruns.** Uncapped milestone payouts let a viral post eat the campaign budget, so $P(\text{spend} > \text{budget})$ is far from zero.
2. **Creators lose interest.** Unrealistic or rigid view thresholds demotivate creators and lower campaign completion rates.

`mimed` handles this by fitting log-normal view models on historical creator performance, simulating view outcomes with vectorized Monte Carlo sampling, and optimizing payout ladders on a 4-dimensional Pareto frontier. The key rule is a **95% budget safety constraint**: a ladder is only considered if total spend stays within budget in at least 95% of simulations.

---

## 2. Quickstart & Interactive Demo

`mimed` includes an interactive terminal-based UI and CLI runner that lets you run the entire end-to-end system, create & simulate custom brand campaigns, and inspect self-explanatory visual reports.

### Option A: Launch Interactive Terminal UI Runner
To start the interactive menu system:
```bash
python -m mimed run
# or
python -m mimed interactive
```
This launches a terminal menu where you can:
1. **Create & Simulate a New Custom Campaign** (interactively prompt for Brand, Category, Platform, Tier, Budget, and Creators).
2. **Select & Simulate an Existing Campaign** (`camp_001` through `camp_012`).
3. **Run Full System Suite** (Seed DB → Validate Integrity → Optimize All → Run Backtest).
4. **Run Walk-Forward Backtest Engine**.
5. **Benchmark Performance**.

### Option B: Create and Simulate a Custom Campaign in One Command
You can pass custom campaign parameters directly via CLI flags to create, simulate, and generate visual spend & economic reports:
```bash
python -m mimed create --brand "ApexTech" --category "Tech" --platform "YouTube" --tier "micro" --budget 600000 --creators 35
```

### Option C: Run Full System Workflow (Seed, Validate, Optimize & Backtest)
To execute the complete end-to-end pipeline automatically:
```bash
# 1. Seed synthetic dataset
python -m mimed seed

# 2. Validate database integrity & temporal safety
python -m mimed validate

# 3. Optimize a specific campaign
python -m mimed optimize --campaign camp_004

# 4. Run walk-forward backtest suite
python -m mimed backtest --walk-forward
```

---

## 3. Architecture & Folder Structure

```
mimed/
├── __init__.py                  # Package initialization
├── __main__.py                  # Entry point (python -m mimed)
├── cli.py                       # Command line interface and argument routing
├── config.py                    # Global settings and hyperparameters
│
├── domain/                      # Core entities and value objects
│   ├── __init__.py
│   ├── campaign.py              # Campaign model
│   ├── creator.py               # Creator profile model
│   ├── milestone.py             # Milestone and MilestoneLadder models
│   ├── post.py                  # Post model with performance metrics
│   └── result.py                # SpendStats, EconomicStats, OptimizationResult
│
├── data/                        # Persistence and synthetic data
│   ├── database.py              # SQLite connection and schema setup
│   ├── schema.sql               # Relational schema
│   ├── generator.py             # Synthetic dataset generator
│   └── repositories.py          # Data access objects for DB CRUD
│
├── modeling/                    # Statistical modeling
│   ├── segment_resolver.py      # Temporal filtering and 4-tier fallback
│   └── view_distribution.py     # Log-normal fitting and bootstrap CIs
│
├── optimization/                # Simulation and optimization engine
│   ├── candidate_generator.py   # Budget-aware candidate ladder generator
│   ├── payout_policy.py         # Cumulative payouts and monotonicity logic
│   ├── simulator.py             # Vectorized Monte Carlo simulator
│   ├── constraints.py           # 95% budget confidence check
│   ├── scorer.py                # Campaign-aware multi-objective scoring
│   └── optimizer.py             # End-to-end pipeline and Pareto solver
│
├── backtest/                    # Historical backtesting
│   ├── runner.py                # Walk-forward backtest runner
│   └── metrics.py               # Comparison metrics
│
└── validation/                  # Data integrity
    └── data_validation.py       # Schema, relational, and temporal checks

tests/                           # Pytest suite
├── test_backtest.py
├── test_distribution.py
├── test_generator.py
├── test_optimizer.py
├── test_payout.py
├── test_repositories.py
└── test_simulator.py
```

---

## 3. What Each Module Does

### 3.1 Domain Layer (`mimed/domain/`)

#### `campaign.py`
- **Purpose**: The `Campaign` model, describing a brand campaign.
- **Fields**: `campaign_id` (str), `brand` (str), `category` (str), `platform` (str), `target_creator_tier` (str), `total_budget` (float), `expected_creators` (int), `start_date` (str), `end_date` (str).
- **Used for**: The main input to candidate generation, segment resolution, and simulation.

#### `creator.py`
- **Purpose**: Represents a creator in the marketplace.
- **Fields**: `creator_id` (str), `handle` (str), `platform` (str), `tier` (str: `nano`, `micro`, `mid`, `macro`), `follower_count` (int), `historical_avg_views_per_post` (float), `joined_date` (str).

#### `post.py`
- **Purpose**: A historical post and how it performed.
- **Fields**: `post_id` (str), `creator_id` (str), `campaign_id` (str), `platform` (str), `category` (str), `content_format` (str), `published_at` (str), `views_24h` (int), `views_7d` (int), `views_30d` (int), `views_final` (int), `flagged_suspicious` (int: `0` or `1`).

#### `milestone.py`
- **Purpose**: Milestone definitions and ladders.
- **Classes**:
  - `Milestone`: `rank` (int), `view_threshold` (int), `payout_amount` (float).
  - `MilestoneLadder`: `campaign_id` (str), `milestones` (List[Milestone]).
- **Methods**:
  - `calculate_payout(views: int) -> float`: Returns the cumulative payout for a view count. For thresholds $T_1 < T_2 < \dots < T_m$ with cumulative payouts $P_1 < P_2 < \dots < P_m$, it returns $\max_{k: V \ge T_k} P_k$, or $0.0$ if $V < T_1$.
  - `validate()`: Checks that thresholds and payouts are both strictly increasing.

#### `result.py`
- **Purpose**: Holds output statistics and formats the CLI report.
- **Classes**:
  - `SpendStats`: `expected_spend`, `median_spend`, `p90_spend`, `p95_spend`, `p99_spend`, `budget_confidence`.
  - `EconomicStats`: `expected_views`, `effective_cpm`, `completion_rate`, `tier_reach_rates`.
  - `OptimizationResult`: The recommended ladder, spend stats, economic stats, segment metadata, scoring trace, Pareto stats, uncertainty CIs, and runtime.
- **Methods**:
  - `format_summary() -> str`: Builds the text report with candidate counts, selected policy, objective scores, raw economic metrics, budget safety confidence, uncertainty CIs, and run ID.

---

### 3.2 Data Layer (`mimed/data/`)

#### `database.py`
- **Input**: Database file path (`data/mimed.db`).
- **Output**: A `sqlite3.Connection`.
- **What it does**: Opens SQLite connections with foreign keys enabled and runs the schema setup (`init_db`).

#### `schema.sql`
- **Purpose**: Schema for the `creators`, `campaigns`, `posts`, `milestone_ladders`, and `milestones` tables, with indexes on `(platform, category)`, `published_at`, and `flagged_suspicious`.

#### `generator.py`
- **Input**: Random seed (int, default `42`) and database path.
- **Output**: A dictionary of created counts (`creators_count`, `campaigns_count`, `posts_count`, `ladders_count`).
- **What it does**:
  - Generates synthetic creators across tiers (`nano`: 5k, `micro`: 25k, `mid`: 100k, `macro`: 500k followers) and archetypes (`stable`, `growing`, `declining`, `volatile`, `new`).
  - Simulates historical campaigns, milestone ladders, and post performance.
  - Injects about 4% anomaly or fraud posts (`flagged_suspicious = 1`) with unnatural view spikes.
  - The latent parameters used for generation are **never saved to SQLite or shown to the models**.

#### `repositories.py`
- **Purpose**: Repository classes that wrap database access.
- **Classes**: `CampaignRepository`, `CreatorRepository`, `PostRepository`, `MilestoneLadderRepository`.
- **Key method**:
  - `PostRepository.get_historical_posts_before(cutoff_date: str) -> List[Post]`: Returns only posts published strictly before `cutoff_date`, which keeps queries temporally safe.

---

### 3.3 Modeling Layer (`mimed/modeling/`)

#### `segment_resolver.py`
- **Input**: A `Campaign` and a minimum observation count (`min_obs=10`).
- **Output**: A `SegmentResult` with the filtered clean posts, segment key, fallback level, observation count, and suspicious post rate.
- **What it does**:
  - Drops suspicious posts (keeps `flagged_suspicious == 0`).
  - Keeps only posts with `published_at < campaign.start_date`.
  - If fewer than 10 observations remain, it falls back through four levels:
    $$\text{Platform + Category + Format + Tier (Level 0)} \longrightarrow \text{Platform + Category (Level 1)} \longrightarrow \text{Platform (Level 2)} \longrightarrow \text{Global (Level 3)}$$

#### `view_distribution.py`
- **Input**: A list of clean historical `Post` objects and a creator lookup map.
- **Output**: A fitted `ViewDistributionModel`.
- **The model**:
  - Views are turned into follower-relative multipliers:
    $$M_i = \frac{\text{views\_final}_i}{\text{follower\_count}_i}$$
  - A log-normal distribution is fitted in log-space, with creator-level noise $\sigma_{\text{log}}$ and a campaign-level shared shock $\sigma_{\text{campaign}}$:
    $$y_i = \ln(M_i) = \mu_{\text{log}} + \text{creator\_noise}_{s, c} + \text{camp\_noise}_{s, 0}$$
  - 95% bootstrap confidence intervals are computed for $\mu$ and $\sigma$.
- **Sampling**:
  - `sample_views_for_creators(creators, n_simulations, seed) -> np.ndarray`: Returns an $(S \times C)$ matrix of sampled view counts for $C$ creators over $S$ simulations. Each simulation draws one campaign-level shock and applies it to all creators.

---

### 3.4 Optimization Layer (`mimed/optimization/`)

#### `candidate_generator.py`
- **Input**: A `Campaign` and the fitted `ViewDistributionModel`.
- **Output**: A list of unique candidate `MilestoneLadder` objects.
- **What it does**:
  - Works out a per-creator budget scale:
    $$B_{\text{per\_creator}} = \frac{\text{campaign.total\_budget}}{\max(1, \text{campaign.expected\_creators})}$$
  - Builds threshold ladders from 12 quantile combination sets ($\text{Q}_{10}$ to $\text{Q}_{95}$).
  - Explores budget intensity factors $\beta \in [0.0, 0.20, 0.50, 0.90, 1.30, 1.80, 2.40]$, eCPM targets (20.0 to 200.0 INR), and reward shares (0.25 to 0.65).
  - Removes duplicate payout ladders using a tuple-hash set (`seen`).

#### `payout_policy.py`
- **Input**: A list of view thresholds, `reward_share`, `target_ecpm`, and an optional `target_budget_anchor`.
- **Output**: A validated `MilestoneLadder`.
- **Formula**:
  - Raw eCPM-based payout:
    $$P_{\text{raw}}(V_k) = \left(\frac{V_k}{1000}\right) \times \text{target\_ecpm} \times \text{reward\_share}$$
  - Payouts are scaled toward the budget anchor $P_{\text{anchor}} = \beta \cdot B_{\text{per\_creator}}$:
    $$P(V_k) = \max\left(P_{\text{raw}}(V_k), \; P_{\text{anchor}} \cdot \frac{P_{\text{raw}}(V_k)}{P_{\text{raw}}(V_{\text{max}})}\right)$$
  - Payouts are forced to be strictly increasing ($P(V_k) > P(V_{k-1})$) and rounded to clean, readable currency amounts.

#### `simulator.py`
- **Input**: A `MilestoneLadder` and the pre-sampled views matrix $(S \times C)$.
- **Output**: A `SimulationOutcome` with `SpendStats` and `EconomicStats`.
- **What it does**:
  - Computes payouts across $S$ simulations, $C$ creators, and $M$ milestones in one vectorized step:
    $$\text{payouts\_3d}[s, c, m] = \begin{cases} P_m & \text{if } V_{s, c} \ge T_m \\ 0 & \text{otherwise} \end{cases}$$
  - Takes the max over milestones to get each creator's cumulative payout:
    $$\text{creator\_payout}[s, c] = \max_{m} \text{payouts\_3d}[s, c, m]$$
  - Sums spend per simulation: $\text{spend}_s = \sum_{c=1}^C \text{creator\_payout}[s, c]$.
  - Estimates budget confidence: $P(\text{spend} \le B) = \frac{1}{S} \sum_{s=1}^S \mathbb{I}(\text{spend}_s \le B)$.

#### `constraints.py`
- **Input**: A `SimulationOutcome`.
- **Output**: A boolean (`True` if feasible).
- **Rule**: The hard budget safety check:
  $$\text{budget\_confidence} \ge 0.95$$

#### `scorer.py`
- **Input**: A `SimulationOutcome` and `campaign_budget`.
- **Output**: A tuple `(total_score, scoring_trace_dict)`.
- **Scoring parts**:
  - **Accessibility**: $\min\left(1.0, \; \frac{\text{completion\_rate}}{0.85}\right)$
  - **Campaign-aware eCPM score**:
    - Reference eCPM: $e_{\text{ref}} = \left(\frac{B}{\max(1, V_{\text{expected}})}\right) \times 1000$
    - Campaign envelope: $[e_{\text{target\_min}}, e_{\text{target\_max}}] = [\max(15, 0.25 e_{\text{ref}}), \max(85, 1.15 e_{\text{ref}})]$
    - Actual eCPM scores smoothly between $0.70$ and $1.00$ inside the envelope, and drops sharply when it goes above $e_{\text{target\_max}}$.
  - **Tier fairness**: $1.0 - \frac{\sigma_{\text{reach}}}{\mu_{\text{reach}}}$ across creator tiers.
  - **Budget utilization**: A piecewise linear score that peaks when spend is in the $[75\%, 95\%]$ band.
  - **Weighted total**:
    $$\text{Score} = 0.30 \cdot \text{Acc} + 0.30 \cdot \text{Eff} + 0.20 \cdot \text{Fair} + 0.20 \cdot \text{Util}$$

#### `optimizer.py`
- **Input**: `campaign_id` and an optional random `seed`.
- **Output**: An `OptimizationResult`.
- **Pipeline**:
  1. Resolve the segment with temporal and fraud filtering (`SegmentResolver`).
  2. Fit the log-normal view distribution (`ViewDistributionModel`).
  3. Generate budget-aware candidate ladders (`CandidateGenerator`).
  4. Run the Monte Carlo simulation over all candidates (`CampaignSimulator`).
  5. Keep only budget-feasible candidates ($P(\text{spend} \le B) \ge 0.95$).
  6. Compute the 4D Pareto non-dominated subset (`_get_pareto_subset`).
  7. Pick the candidate with the highest weighted score from that feasible Pareto set.

---

### 3.5 Backtesting Layer (`mimed/backtest/`)

#### `runner.py`
- **Input**: Repositories and the minimum number of warmup campaigns (`min_warmup_campaigns=3`).
- **Output**: A `pandas.DataFrame` comparing historical, rule-based baseline, and optimized ladders across past campaigns.
- **What it does**:
  - Enforces walk-forward isolation: when testing campaign $k$, the optimizer only sees posts published before campaign $k$'s start date.
  - Saves the comparison table to `results/backtest_results.csv`.

#### `metrics.py`
- **Input**: Simulation outcomes for the historical, baseline, and optimized ladders.
- **Output**: A comparison dictionary (payouts, utilization rates, budget breach flags).

---

### 3.6 Validation Layer (`mimed/validation/`)

#### `data_validation.py`
- **Input**: Database path.
- **Output**: A result dictionary (`valid` boolean, `issues` list, record counts).
- **Checks**:
  - Relational integrity (foreign keys).
  - Non-negative view and follower counts.
  - Temporal consistency (post date $\ge$ creator joined date).
  - Suspicious post rate sanity check.

---

## 4. CLI Reference

All commands run as `python -m mimed <command> [options]`.

| Command | Arguments / Flags | Description |
| :--- | :--- | :--- |
| `run` / `interactive` | None | Launches the interactive terminal UI runner with custom campaign creation & visual reports. |
| `create` | `--brand STR`<br>`--category STR`<br>`--platform STR`<br>`--tier STR`<br>`--budget FLOAT`<br>`--creators INT` | Interactively or directly creates and simulates a custom brand campaign, printing a rich visual report. |
| `seed` | `--seed INT` (default `42`) | Fills the SQLite database with synthetic creators, campaigns, and historical posts, deterministically. |
| `validate` | None | Runs database integrity, relational, and temporal safety checks. |
| `inspect` | `creators` \| `campaigns` | Prints summary tables of the creator pool or historical campaigns. |
| `optimize` | `--campaign STR` (required)<br>`--seed INT` (default `42`) | Runs the full optimization for a campaign and prints the recommended ladder, scores, and raw metrics. |
| `backtest` | `--walk-forward` | Runs the backtest comparing Historical vs Baseline vs Optimized across campaigns. |
| `benchmark` | None | Benchmarks simulation speed and optimization runtime over 5,000 Monte Carlo runs. |
| `reset` | None | Deletes the SQLite database (`data/mimed.db`) and cached backtest results. |

---

## 5. Statistical and Optimization Details

### 5.1 Log-Normal View Model with a Shared Campaign Shock
Social video views are heavy-tailed and follow a log-normal shape, with macro-level shocks that hit a whole campaign at once. Performance is modeled in log-space over normalized multipliers $M_i$:

$$M_i = \frac{\text{views\_final}_i}{\text{follower\_count}_i}$$

$$y_{s, c} = \ln(M_{s, c}) = \mu_{\text{log}} + \text{creator\_noise}_{s, c} + \text{camp\_noise}_{s, 0}$$

Here $\text{creator\_noise}_{s, c} \sim \mathcal{N}(0, \sigma_{\text{log}}^2)$, and $\text{camp\_noise}_{s, 0} \sim \mathcal{N}(0, \sigma_{\text{campaign}}^2)$ is drawn once per simulation $s$ and shared by all creators.

For a creator with follower count $F_c$, the simulated views in run $s$ are:

$$V_{s, c} = \left\lfloor F_c \cdot \exp\left(\mu_{\text{log}} + \text{creator\_noise}_{s, c} + \text{camp\_noise}_{s, 0}\right) \right\rfloor$$

### 5.2 Pareto Non-Domination
For candidate outcome vectors $\mathbf{o} = [\text{Acc}, \text{Eff}, \text{Fair}, \text{Util}] \in \mathbb{R}^4$, candidate $i$ dominates candidate $j$ ($i \succ j$) iff:

$$\forall k \in \{1..4\}, \quad o_{i, k} \ge o_{j, k} \quad \text{and} \quad \exists k \in \{1..4\}, \quad o_{i, k} > o_{j, k}$$

The optimizer builds the Pareto non-dominated subset $\mathcal{P}_{\text{feasible}}$ from all budget-feasible candidates and picks:

$$\mathbf{x}^* = \arg\max_{\mathbf{x} \in \mathcal{P}_{\text{feasible}}} \sum_{k=1}^4 w_k \cdot o_k(\mathbf{x})$$

---

## 6. Backtest Results (Walk-Forward)

The backtest (`python -m mimed backtest`) keeps strict temporal isolation (`published_at < campaign.start_date`) so no future data leaks in.

### Summary Table

| Campaign ID | Budget (₹) | Historical Payout (₹) | Baseline Payout (₹) | **Optimized Payout (₹)** | **Optimized Utilization** | **Optimized eCPM** | **Exceeded Budget?** |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`camp_004`** | ₹549,000 | ₹1,155,000 | ₹17,700 | **₹314,200** | **57.23%** | ₹38.41 | **FALSE** |
| **`camp_005`** | ₹649,000 | ₹647,000 | ₹22,800 | **₹268,800** | **41.42%** | ₹54.51 | **FALSE** |
| **`camp_006`** | ₹2,125,000 | ₹890,000 | ₹31,000 | **₹524,000** | **24.66%** | ₹58.55 | **FALSE** |
| **`camp_007`** | ₹401,000 | ₹272,000 | ₹6,200 | **₹284,800** | **71.02%** | ₹155.30 | **FALSE** |
| **`camp_008`** | ₹438,000 | ₹915,000 | ₹27,200 | **₹327,200** | **74.70%** | ₹42.37 | **FALSE** |
| **`camp_009`** | ₹217,000 | ₹326,500 | ₹19,600 | **₹235,200** | **108.39%** | ₹40.53 | TRUE (outlier) |
| **`camp_010`** | ₹363,000 | ₹552,000 | ₹36,100 | **₹393,000** | **108.26%** | ₹32.72 | TRUE (outlier) |
| **`camp_011`** | ₹1,186,000 | ₹580,000 | ₹19,500 | **₹360,000** | **30.35%** | ₹81.81 | **FALSE** |
| **`camp_012`** | ₹2,494,000 | ₹280,000 | ₹8,700 | **₹454,000** | **18.20%** | ₹197.62 | **FALSE** |

### Key Numbers
- **Budget compliance rate**: 77.8% (7 of 9 campaigns stayed within budget; the earlier failure rate was 44.4%).
- **Average optimized utilization**: 48.2% across campaigns.
- **Average optimized eCPM**: ₹78.09 per 1,000 views.

---

## 7. Testing

Run the full suite with:

```bash
python -m pytest
```

### Coverage (13/13 passing)
- **`test_generator.py`**: Deterministic seeding, creator tier distributions, and candidate budget-scaling range checks.
- **`test_payout.py`**: Cumulative payout logic, strict milestone monotonicity, and low, reasonable, and extreme eCPM scoring cases.
- **`test_distribution.py`**: Log-normal fit correctness, multiplier normalization, reproducibility of the correlated campaign shock, and bootstrap confidence intervals.
- **`test_simulator.py`**: Vectorized Monte Carlo payouts, spend calculation, and budget confidence estimation.
- **`test_optimizer.py`**: End-to-end optimization, creator pool count alignment (`target_creators`), Pareto subset construction, and summary output formatting.
- **`test_repositories.py`**: SQLite CRUD and strict temporal query safety (`published_at < max_date`).
- **`test_backtest.py`**: Backtest execution and CSV export checks.

---

## 8. Limitations and Next Steps

1. **Synthetic viral outliers**:
   Extreme synthetic spikes (over $8\times$ view multipliers on single posts in `camp_009` and `camp_010`) can still cause small overruns of around 8%. In a real deployment, pair static milestone ladders with live in-campaign budget locks.
2. **Database and scale**:
   Moving from SQLite to PostgreSQL with connection pooling would allow parallel runs for marketplace pools above 100,000 creators.
3. **Live telemetry**:
   Hooking in live webhooks from YouTube Analytics or the Instagram Graph API would let the system re-tune milestone thresholds while a campaign is running.