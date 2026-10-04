"""
CLI interface for mimed: Milestone Optimization for Brand Campaigns.
"""
import sys
import time
import argparse
from pathlib import Path
import pandas as pd

from mimed.config import DATABASE_PATH, DEFAULT_SEED
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


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="python -m mimed",
        description="Milestone Optimization CLI for Creator Marketplace Brand Campaigns",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 0. run / interactive
    subparsers.add_parser("run", help="Launch the interactive terminal UI runner")
    subparsers.add_parser("interactive", help="Launch the interactive terminal UI runner")

    # 1. create
    create_parser = subparsers.add_parser("create", help="Create and simulate a new campaign")
    create_parser.add_argument("--brand", type=str, default="NovaBrand", help="Brand name")
    create_parser.add_argument("--category", type=str, default="Tech", help="Campaign category")
    create_parser.add_argument("--platform", type=str, default="YouTube", help="Social media platform")
    create_parser.add_argument("--tier", type=str, default="micro", help="Target creator tier (nano, micro, mid, macro)")
    create_parser.add_argument("--budget", type=float, default=500000.0, help="Total campaign budget (₹)")
    create_parser.add_argument("--creators", type=int, default=30, help="Expected creator headcount")

    # 2. seed
    seed_parser = subparsers.add_parser("seed", help="Seed database deterministically")
    seed_parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed (default 42)")

    # 3. validate
    subparsers.add_parser("validate", help="Validate database integrity & temporal safety")

    # 4. inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect database entities")
    inspect_sub = inspect_parser.add_subparsers(dest="target", help="Entity to inspect")
    inspect_sub.add_parser("creators", help="Inspect creator pool statistics")
    inspect_sub.add_parser("campaigns", help="Inspect historical campaigns")

    # 5. optimize
    opt_parser = subparsers.add_parser("optimize", help="Optimize milestone ladder for a campaign")
    opt_parser.add_argument("--campaign", required=True, type=str, help="Campaign ID to optimize")
    opt_parser.add_argument("--pareto", action="store_true", help="Enable Pareto frontier optimization mode")
    opt_parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed (default 42)")

    # 6. backtest
    bt_parser = subparsers.add_parser("backtest", help="Run backtest suite over historical campaigns")
    bt_parser.add_argument("--walk-forward", action="store_true", help="Run walk-forward temporal evaluation mode")

    # 7. benchmark
    subparsers.add_parser("benchmark", help="Benchmark performance of simulator & optimizer")

    # 8. reset
    subparsers.add_parser("reset", help="Reset database and remove generated results")

    args = parser.parse_args()

    if not args.command:
        from mimed.interactive import run_interactive_runner
        run_interactive_runner()
        sys.exit(0)

    try:
        if args.command in ("run", "interactive"):
            from mimed.interactive import run_interactive_runner
            run_interactive_runner()
        elif args.command == "create":
            cmd_create_direct(
                brand=args.brand,
                category=args.category,
                platform=args.platform,
                tier=args.tier,
                budget=args.budget,
                creators=args.creators,
            )
        elif args.command == "seed":
            cmd_seed(args.seed)
        elif args.command == "validate":
            cmd_validate()
        elif args.command == "inspect":
            if args.target == "creators":
                cmd_inspect_creators()
            elif args.target == "campaigns":
                cmd_inspect_campaigns()
            else:
                inspect_parser.print_help()
        elif args.command == "optimize":
            cmd_optimize(args.campaign, seed=args.seed, pareto=args.pareto)
        elif args.command == "backtest":
            cmd_backtest(walk_forward=args.walk_forward)
        elif args.command == "benchmark":
            cmd_benchmark()
        elif args.command == "reset":
            cmd_reset()
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)



def cmd_create_direct(brand: str, category: str, platform: str, tier: str, budget: float, creators: int):
    from datetime import datetime
    from mimed.domain import Campaign
    from mimed.interactive import render_explanation_report, ensure_seeded_database

    ensure_seeded_database()

    conn = get_connection(DATABASE_PATH)
    camp_repo = CampaignRepository(conn)
    creator_repo = CreatorRepository(conn)
    post_repo = PostRepository(conn)

    existing = camp_repo.get_all()
    camp_num = len(existing) + 1
    campaign_id = f"custom_{camp_num:03d}"

    campaign = Campaign(
        campaign_id=campaign_id,
        brand=brand,
        category=category,
        platform=platform,
        total_budget=budget,
        start_date=datetime.now().strftime("%Y-%m-%d"),
        end_date="2026-12-31",
        target_creator_tier=tier,
        expected_creators=creators,
    )
    camp_repo.save(campaign)

    optimizer = MilestoneOptimizer(camp_repo, creator_repo, post_repo)
    result = optimizer.optimize_campaign(campaign_id, seed=DEFAULT_SEED)
    conn.close()

    render_explanation_report(result, campaign)


def cmd_seed(seed: int):
    print(f"Seeding synthetic dataset deterministically with seed={seed}...")
    stats = generate_synthetic_dataset(seed=seed, db_path=DATABASE_PATH)
    print(
        f"Successfully seeded database at {DATABASE_PATH}:\n"
        f"  - Creators:  {stats['creators_count']}\n"
        f"  - Campaigns: {stats['campaigns_count']}\n"
        f"  - Posts:     {stats['posts_count']}\n"
        f"  - Ladders:   {stats['ladders_count']}"
    )


def cmd_validate():
    _check_db_exists()
    print("Running database & temporal validation checks...")
    res = validate_database_integrity(DATABASE_PATH)
    if res["valid"]:
        print("Validation SUCCESSFUL! Database integrity and temporal safety verified.")
        print(f"  - Campaigns: {res['campaigns_count']}")
        print(f"  - Creators:  {res['creators_count']}")
        print(f"  - Posts:     {res['posts_count']}")
    else:
        print("Validation FAILED! Issues found:")
        for issue in res["issues"]:
            print(f"  - {issue}")
        sys.exit(1)


def cmd_inspect_creators():
    _check_db_exists()
    conn = get_connection(DATABASE_PATH)
    repo = CreatorRepository(conn)
    creators = repo.get_all()
    conn.close()

    print(f"Creator Pool Summary (Total: {len(creators)} creators):\n")
    print(f"{'Tier':<10} {'Platform':<12} {'Count':<8} {'Avg Followers':<15} {'Avg Views/Post':<15}")
    print("-" * 65)

    tier_stats = {}
    for c in creators:
        key = (c.tier, c.platform)
        if key not in tier_stats:
            tier_stats[key] = {"count": 0, "followers": 0, "views": 0.0}
        tier_stats[key]["count"] += 1
        tier_stats[key]["followers"] += c.follower_count
        tier_stats[key]["views"] += c.historical_avg_views_per_post

    for (tier, platform), data in sorted(tier_stats.items()):
        cnt = data["count"]
        avg_f = data["followers"] // cnt
        avg_v = data["views"] / cnt
        print(f"{tier:<10} {platform:<12} {cnt:<8} {avg_f:<15,d} {avg_v:<15,.0f}")


def cmd_inspect_campaigns():
    _check_db_exists()
    conn = get_connection(DATABASE_PATH)
    repo = CampaignRepository(conn)
    campaigns = repo.get_all()
    conn.close()

    print(f"Campaigns Summary (Total: {len(campaigns)} campaigns):\n")
    print(f"{'ID':<10} {'Brand':<15} {'Category':<12} {'Platform':<12} {'Tier':<8} {'Budget (₹)':<14} {'Start Date':<12}")
    print("-" * 88)
    for c in campaigns:
        print(f"{c.campaign_id:<10} {c.brand:<15} {c.category:<12} {c.platform:<12} {c.target_creator_tier:<8} {c.total_budget:<14,.0f} {c.start_date:<12}")


def cmd_optimize(campaign_id: str, seed: int = DEFAULT_SEED, pareto: bool = False):
    _check_db_exists()
    conn = get_connection(DATABASE_PATH)
    camp_repo = CampaignRepository(conn)
    creator_repo = CreatorRepository(conn)
    post_repo = PostRepository(conn)

    campaign = camp_repo.get_by_id(campaign_id)
    if not campaign:
        conn.close()
        raise ValueError(f"Campaign ID '{campaign_id}' not found. Run 'python -m mimed inspect campaigns' to list IDs.")

    optimizer = MilestoneOptimizer(camp_repo, creator_repo, post_repo)
    result = optimizer.optimize_campaign(campaign_id, seed=seed)
    conn.close()

    print(result.format_summary())


def cmd_backtest(walk_forward: bool = False):
    _check_db_exists()
    conn = get_connection(DATABASE_PATH)
    camp_repo = CampaignRepository(conn)
    creator_repo = CreatorRepository(conn)
    post_repo = PostRepository(conn)
    ladder_repo = MilestoneLadderRepository(conn)

    mode_str = " (Walk-Forward Temporal Mode)" if walk_forward else ""
    print(f"Running backtest suite over historical campaigns{mode_str}...")
    runner = BacktestRunner(camp_repo, creator_repo, post_repo, ladder_repo)
    df = runner.run_backtest(min_warmup_campaigns=3)
    conn.close()


    print("\nBacktest Summary Results:\n")
    summary_cols = [
        "campaign_id", "total_budget",
        "hist_payout", "hist_utilization",
        "base_payout", "base_utilization",
        "opt_payout", "opt_utilization", "opt_ecpm", "opt_exceeded_budget"
    ]
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)
    print(df[summary_cols].to_string(index=False))
    print(f"\nDetailed CSV results exported to: results/backtest_results.csv")


def cmd_benchmark():
    _check_db_exists()
    print("Benchmarking mimed simulation & optimization performance...")
    conn = get_connection(DATABASE_PATH)
    camp_repo = CampaignRepository(conn)
    creator_repo = CreatorRepository(conn)
    post_repo = PostRepository(conn)

    campaigns = camp_repo.get_all()
    if not campaigns:
        conn.close()
        raise ValueError("No campaigns found to benchmark.")

    target_camp = campaigns[-1]

    t0 = time.perf_counter()
    optimizer = MilestoneOptimizer(camp_repo, creator_repo, post_repo)
    t1 = time.perf_counter()

    t2 = time.perf_counter()
    result = optimizer.optimize_campaign(target_camp.campaign_id, seed=DEFAULT_SEED)
    t3 = time.perf_counter()
    conn.close()

    init_time = (t1 - t0) * 1000.0
    opt_time = (t3 - t2) * 1000.0

    print(f"\nBenchmark Results for Campaign '{target_camp.campaign_id}':")
    print(f"  - Optimizer Init Time: {init_time:.2f} ms")
    print(f"  - Full Optimization Runtime (5,000 Monte Carlo Sims): {opt_time:.2f} ms")
    print(f"  - Recommended Ladder Length: {len(result.recommended_ladder.milestones)} milestones")
    print(f"  - Budget Safety Confidence: {result.spend_stats.budget_confidence * 100:.1f}%")


def cmd_reset():
    print("Resetting mimed database...")
    reset_db(DATABASE_PATH)
    print(f"Database reset complete at {DATABASE_PATH}.")


def _check_db_exists():
    if not DATABASE_PATH.exists():
        print(f"Error: Database not found at {DATABASE_PATH}.", file=sys.stderr)
        print("Please run 'python -m mimed seed' first.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
