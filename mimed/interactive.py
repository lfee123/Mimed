"""
Interactive Terminal CLI Runner for mimed.
Provides an end-to-end interactive terminal UI for creating, simulating, and evaluating brand campaigns.
"""
import sys
import time
from datetime import datetime
from typing import Optional, List, Dict

from mimed.config import (
    DATABASE_PATH,
    DEFAULT_SEED,
    SUPPORTED_PLATFORMS,
    SUPPORTED_CATEGORIES,
    CREATOR_TIERS,
)
from mimed.domain import Campaign, OptimizationResult
from mimed.data.database import get_connection, reset_db
from mimed.data.generator import generate_synthetic_dataset
from mimed.validation.data_validation import validate_database_integrity
from mimed.data.repositories import (
    CampaignRepository,
    CreatorRepository,
    PostRepository,
    MilestoneLadderRepository,
)
from mimed.optimization.optimizer import MilestoneOptimizer
from mimed.backtest.runner import BacktestRunner


# ANSI Formatting Constants
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_BLUE = "\033[44m\033[97m"
BG_GREEN = "\033[42m\033[30m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}================================================================================
  ███╗   ███╗██╗███╗   ███╗███████╗██████╗ 
  ████╗ ████║██║████╗ ████║██╔════╝██╔══██╗
  ██╔████╔██║██║██╔████╔██║█████╗  ██║  ██║  Milestone Optimization Engine
  ██║╚██╔╝██║██║██║╚██╔╝██║██╔══╝  ██║  ██║  for Brand Campaigns in Creator
  ██║ ╚═╝ ██║██║██║ ╚═╝ ██║███████╗██████╔╝  Marketplaces (v1.0.0)
  ╚═╝     ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═════╝ 
================================================================================{RESET}
"""
    print(banner)


def draw_box(title: str, lines: List[str], color: str = CYAN) -> str:
    max_len = max(len(strip_ansi(l)) for l in [title] + lines) if lines else len(title)
    width = max(max_len + 4, 72)

    top = f"{color}╔═ {BOLD}{title}{RESET}{color} " + "═" * (width - len(title) - 4) + f"╗{RESET}"
    bottom = f"{color}╚" + "═" * (width - 2) + f"╝{RESET}"

    content = []
    for line in lines:
        padding = width - len(strip_ansi(line)) - 4
        content.append(f"{color}║{RESET}  {line}" + " " * max(0, padding) + f" {color}║{RESET}")

    return "\n".join([top] + content + [bottom])


def strip_ansi(text: str) -> str:
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def draw_gauge(label: str, val: float, max_val: float, width: int = 25) -> str:
    ratio = min(1.0, max(0.0, val / max_val if max_val > 0 else 0))
    filled = int(round(ratio * width))
    unfilled = width - filled

    if ratio <= 0.75:
        bar_color = GREEN
    elif ratio <= 0.95:
        bar_color = YELLOW
    else:
        bar_color = RED

    bar = f"{bar_color}" + "█" * filled + f"{DIM}" + "░" * unfilled + f"{RESET}"
    pct = f"{ratio * 100:5.1f}%"
    return f"{label:<22} [{bar}] {pct} (₹{val:,.0f} / ₹{max_val:,.0f})"


def render_explanation_report(result: OptimizationResult, campaign: Campaign):
    res = result
    ladder = res.recommended_ladder
    spend = res.spend_stats
    econ = res.economic_stats

    # Header Card
    header_lines = [
        f"{BOLD}Campaign ID:{RESET} {campaign.campaign_id:<14} {BOLD}Brand:{RESET} {campaign.brand}",
        f"{BOLD}Platform:{RESET}    {campaign.platform:<14} {BOLD}Category:{RESET} {campaign.category}",
        f"{BOLD}Target Tier:{RESET} {campaign.target_creator_tier:<14} {BOLD}Creators:{RESET} {campaign.expected_creators}",
        f"{BOLD}Total Budget:{RESET} ₹{campaign.total_budget:,.0f}",
    ]
    print("\n" + draw_box("CAMPAIGN SPECIFICATIONS", header_lines, CYAN))

    # Recommended Milestone Ladder
    ladder_lines = [
        f"{BOLD}{'Rank':<6} {'Threshold (Views)':<20} {'Payout (₹)':<16} {'Marginal eCPM':<15}{RESET}",
        "-" * 64,
    ]
    prev_thresh = 0
    prev_payout = 0.0
    for m in ladder.milestones:
        d_v = m.view_threshold - prev_thresh
        d_p = m.payout_amount - prev_payout
        m_ecpm = (d_p / (d_v / 1000.0)) if d_v > 0 else 0.0
        ladder_lines.append(
            f"T{m.rank:<5} {m.view_threshold:<20,d} ₹{m.payout_amount:<15,.0f} ₹{m_ecpm:<14.2f}"
        )
        prev_thresh = m.view_threshold
        prev_payout = m.payout_amount

    print("\n" + draw_box("OPTIMIZED MILESTONE PAYOUT LADDER", ladder_lines, GREEN))

    # Budget Safety & Spend Distribution
    safety_color = GREEN if spend.budget_confidence >= 0.95 else RED
    safety_status = "SAFE (>= 95% Confidence)" if spend.budget_confidence >= 0.95 else "HIGH RISK (< 95% Confidence)"

    gauge_exp = draw_gauge("Expected Spend:", spend.expected_spend, campaign.total_budget)
    gauge_p95 = draw_gauge("P95 Max Spend:", spend.p95_spend, campaign.total_budget)

    spend_lines = [
        f"{BOLD}Budget Safety Status:{RESET} {safety_color}{safety_status}{RESET}",
        f"{BOLD}Budget Confidence:{RESET}   {spend.budget_confidence * 100:.1f}% simulations within budget",
        "",
        gauge_exp,
        gauge_p95,
        "",
        f"{BOLD}Spend Percentiles:{RESET}",
        f"  - Median Spend (P50): ₹{spend.median_spend:,.0f} ({spend.median_spend/campaign.total_budget*100:.1f}% budget)",
        f"  - High Spend (P90):   ₹{spend.p90_spend:,.0f} ({spend.p90_spend/campaign.total_budget*100:.1f}% budget)",
        f"  - Risk Ceiling (P95): ₹{spend.p95_spend:,.0f} ({spend.p95_spend/campaign.total_budget*100:.1f}% budget)",
        f"  - Extreme Tail (P99): ₹{spend.p99_spend:,.0f} ({spend.p99_spend/campaign.total_budget*100:.1f}% budget)",
    ]
    print("\n" + draw_box("BUDGET SAFETY & STOCHASTIC SPEND ANALYSIS", spend_lines, YELLOW))

    # Economic Efficiency & Performance
    econ_lines = [
        f"{BOLD}Expected Campaign Views:{RESET} {econ.expected_views:,.0f} total views",
        f"{BOLD}Effective CPM (eCPM):{RESET}   ₹{econ.effective_cpm:.2f} per 1,000 views",
        f"{BOLD}Creator Completion Rate:{RESET} {econ.completion_rate * 100:.1f}% expected to cross Milestone 1",
    ]
    if econ.tier_reach_rates:
        econ_lines.append(f"{BOLD}Tier Completion Rates:{RESET}")
        for t, rate in econ.tier_reach_rates.items():
            econ_lines.append(f"  - Tier {t:<6}: {rate * 100:.1f}%")

    print("\n" + draw_box("ECONOMIC EFFICIENCY & CREATOR REACH", econ_lines, MAGENTA))

    # Optimization Diagnostic & Pareto Score
    trace = res.scoring_trace
    diag_lines = [
        f"{BOLD}Composite Score:{RESET}    {res.score:.4f} / 1.0000",
        f"  - Accessibility (Completion): {trace.get('accessibility_score', 0.0):.4f} (Weight 30%)",
        f"  - eCPM Efficiency:            {trace.get('ecpm_efficiency_score', 0.0):.4f} (Weight 30%)",
        f"  - Tier Reach Fairness:        {trace.get('fairness_score', 0.0):.4f} (Weight 20%)",
        f"  - Budget Utilization:         {trace.get('budget_utilization_score', 0.0):.4f} (Weight 20%)",
        "",
        f"{BOLD}Pareto Search Space Diagnostics:{RESET}",
        f"  - Total Candidates Evaluated: {res.candidates_generated}",
        f"  - Budget-Feasible Candidates: {res.candidates_feasible}",
        f"  - Pareto Frontier Size:       {res.candidates_pareto}",
        f"  - Simulation Runtime:         {res.runtime_seconds * 1000:.1f} ms (5,000 Monte Carlo runs)",
    ]
    print("\n" + draw_box("SCORING TRACE & PARETO DIAGNOSTICS", diag_lines, BLUE))
    print("\n" + "=" * 80 + "\n")


def create_custom_campaign_interactive(camp_repo: CampaignRepository) -> Campaign:
    print(f"\n{CYAN}{BOLD}--- CREATE A NEW BRAND CAMPAIGN ---{RESET}\n")

    # Brand
    brand_input = input(f"{BOLD}Enter Brand Name{RESET} [default: 'NovaBrand']: ").strip()
    brand = brand_input if brand_input else "NovaBrand"

    # Category
    print(f"\n{BOLD}Select Category:{RESET}")
    for idx, cat in enumerate(SUPPORTED_CATEGORIES, 1):
        print(f"  {idx}. {cat}")
    cat_choice = input(f"Choice (1-{len(SUPPORTED_CATEGORIES)}) [default: 1]: ").strip()
    try:
        category = SUPPORTED_CATEGORIES[int(cat_choice) - 1]
    except (ValueError, IndexError):
        category = SUPPORTED_CATEGORIES[0]

    # Platform
    print(f"\n{BOLD}Select Platform:{RESET}")
    for idx, plat in enumerate(SUPPORTED_PLATFORMS, 1):
        print(f"  {idx}. {plat}")
    plat_choice = input(f"Choice (1-{len(SUPPORTED_PLATFORMS)}) [default: 1]: ").strip()
    try:
        platform = SUPPORTED_PLATFORMS[int(plat_choice) - 1]
    except (ValueError, IndexError):
        platform = SUPPORTED_PLATFORMS[0]

    # Tier
    print(f"\n{BOLD}Select Target Creator Tier:{RESET}")
    for idx, t in enumerate(CREATOR_TIERS, 1):
        print(f"  {idx}. {t}")
    tier_choice = input(f"Choice (1-{len(CREATOR_TIERS)}) [default: 2]: ").strip()
    try:
        target_tier = CREATOR_TIERS[int(tier_choice) - 1]
    except (ValueError, IndexError):
        target_tier = "micro"

    # Budget
    budget_input = input(f"\n{BOLD}Enter Total Campaign Budget in ₹{RESET} [default: 500000]: ").strip()
    try:
        total_budget = float(budget_input)
        if total_budget <= 0:
            total_budget = 500000.0
    except ValueError:
        total_budget = 500000.0

    # Creators
    creators_input = input(f"{BOLD}Enter Expected Creator Count{RESET} [default: 30]: ").strip()
    try:
        expected_creators = int(creators_input)
        if expected_creators <= 0:
            expected_creators = 30
    except ValueError:
        expected_creators = 30

    existing = camp_repo.get_all()
    camp_num = len(existing) + 1
    campaign_id = f"custom_{camp_num:03d}"

    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date = "2026-12-31"

    campaign = Campaign(
        campaign_id=campaign_id,
        brand=brand,
        category=category,
        platform=platform,
        total_budget=total_budget,
        start_date=start_date,
        end_date=end_date,
        target_creator_tier=target_tier,
        expected_creators=expected_creators,
    )

    camp_repo.save(campaign)
    print(f"\n{GREEN}{BOLD}Successfully created campaign '{campaign_id}'!{RESET}\n")
    return campaign


def ensure_seeded_database() -> bool:
    if not DATABASE_PATH.exists():
        print(f"{YELLOW}Database not found. Seeding initial synthetic dataset...{RESET}")
        generate_synthetic_dataset(seed=DEFAULT_SEED, db_path=DATABASE_PATH)
        print(f"{GREEN}Database seeded successfully.{RESET}\n")
        return True
    return False


def run_interactive_runner():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    print_banner()
    ensure_seeded_database()

    conn = get_connection(DATABASE_PATH)
    camp_repo = CampaignRepository(conn)
    creator_repo = CreatorRepository(conn)
    post_repo = PostRepository(conn)
    ladder_repo = MilestoneLadderRepository(conn)
    optimizer = MilestoneOptimizer(camp_repo, creator_repo, post_repo)

    while True:
        print(f"\n{CYAN}{BOLD}--- MAIN MENU ---{RESET}")
        print("1. Create & Simulate a New Custom Campaign")
        print("2. Select & Simulate an Existing Historical Campaign")
        print("3. Run Full System Suite (Seed -> Validate -> Optimize -> Backtest)")
        print("4. Run Walk-Forward Backtest Engine")
        print("5. Benchmark Engine Performance")
        print("6. Exit")

        choice = input(f"\n{BOLD}Select an option (1-6):{RESET} ").strip()

        if choice == "1":
            camp = create_custom_campaign_interactive(camp_repo)
            print(f"{CYAN}Running 5,000-simulation Monte Carlo optimization for '{camp.campaign_id}'...{RESET}")
            t0 = time.perf_counter()
            result = optimizer.optimize_campaign(camp.campaign_id, seed=DEFAULT_SEED)
            t1 = time.perf_counter()
            render_explanation_report(result, camp)

        elif choice == "2":
            campaigns = camp_repo.get_all()
            if not campaigns:
                print(f"{RED}No campaigns found in database.{RESET}")
                continue

            print(f"\n{BOLD}Available Campaigns:{RESET}\n")
            print(f"{'#':<4} {'ID':<10} {'Brand':<15} {'Platform':<12} {'Tier':<8} {'Budget (₹)':<14} {'Creators':<8}")
            print("-" * 75)
            for idx, c in enumerate(campaigns, 1):
                print(f"{idx:<4} {c.campaign_id:<10} {c.brand:<15} {c.platform:<12} {c.target_creator_tier:<8} {c.total_budget:<14,.0f} {c.expected_creators:<8}")

            c_choice = input(f"\n{BOLD}Select Campaign # (1-{len(campaigns)}):{RESET} ").strip()
            try:
                sel_camp = campaigns[int(c_choice) - 1]
            except (ValueError, IndexError):
                print(f"{RED}Invalid selection.{RESET}")
                continue

            print(f"\n{CYAN}Optimizing ladder for '{sel_camp.campaign_id}' ({sel_camp.brand})...{RESET}")
            result = optimizer.optimize_campaign(sel_camp.campaign_id, seed=DEFAULT_SEED)
            render_explanation_report(result, sel_camp)

        elif choice == "3":
            print(f"\n{CYAN}{BOLD}--- RUNNING FULL SYSTEM WORKFLOW ---{RESET}\n")
            print("Step 1/4: Seeding Synthetic Dataset...")
            generate_synthetic_dataset(seed=DEFAULT_SEED, db_path=DATABASE_PATH)
            print("Step 2/4: Validating Database Integrity...")
            val_res = validate_database_integrity(DATABASE_PATH)
            print(f"  -> Validation: {'PASSED' if val_res['valid'] else 'FAILED'}")
            print("Step 3/4: Optimizing All Campaigns...")
            all_camps = camp_repo.get_all()
            for c in all_camps:
                res = optimizer.optimize_campaign(c.campaign_id, seed=DEFAULT_SEED)
                print(f"  -> {c.campaign_id}: Composite Score {res.score:.4f}, Budget Conf {res.spend_stats.budget_confidence * 100:.1f}%")
            print("Step 4/4: Running Walk-Forward Backtest...")
            runner = BacktestRunner(camp_repo, creator_repo, post_repo, ladder_repo)
            df = runner.run_backtest(min_warmup_campaigns=3)
            print(f"\n{GREEN}{BOLD}System Workflow Complete! Summary Results exported to results/backtest_results.csv.{RESET}\n")

        elif choice == "4":
            print(f"\n{CYAN}Running Walk-Forward Temporal Backtest...{RESET}\n")
            runner = BacktestRunner(camp_repo, creator_repo, post_repo, ladder_repo)
            df = runner.run_backtest(min_warmup_campaigns=3)
            summary_cols = [
                "campaign_id", "total_budget",
                "hist_payout", "hist_utilization",
                "opt_payout", "opt_utilization", "opt_ecpm", "opt_exceeded_budget"
            ]
            import pandas as pd
            pd.set_option("display.max_columns", None)
            pd.set_option("display.width", 1000)
            print(df[summary_cols].to_string(index=False))

        elif choice == "5":
            camps = camp_repo.get_all()
            if camps:
                target = camps[-1]
                print(f"\n{CYAN}Benchmarking Campaign Optimizer on '{target.campaign_id}'...{RESET}")
                t0 = time.perf_counter()
                res = optimizer.optimize_campaign(target.campaign_id, seed=DEFAULT_SEED)
                t1 = time.perf_counter()
                print(f"  - Runtime for 5,000 Monte Carlo Sims: {(t1 - t0) * 1000:.2f} ms")
                print(f"  - Candidates Evaluated: {res.candidates_generated}")
                print(f"  - Feasible Candidates: {res.candidates_feasible}")
                print(f"  - Pareto Set Count: {res.candidates_pareto}")

        elif choice == "6":
            print(f"\n{GREEN}Exiting mimed Interactive Runner. Goodbye!{RESET}\n")
            break
        else:
            print(f"{RED}Invalid option. Please enter 1-6.{RESET}")

    conn.close()


if __name__ == "__main__":
    run_interactive_runner()
