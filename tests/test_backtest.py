import tempfile
import gc
from pathlib import Path

from mimed.data.generator import generate_synthetic_dataset
from mimed.data.database import get_connection
from mimed.data.repositories import (
    CampaignRepository,
    CreatorRepository,
    PostRepository,
    MilestoneLadderRepository,
)
from mimed.backtest.runner import BacktestRunner


def test_backtest_runner():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bt_test.db"
        generate_synthetic_dataset(seed=42, db_path=db_path)

        conn = get_connection(db_path)
        try:
            camp_repo = CampaignRepository(conn)
            creator_repo = CreatorRepository(conn)
            post_repo = PostRepository(conn)
            ladder_repo = MilestoneLadderRepository(conn)

            runner = BacktestRunner(camp_repo, creator_repo, post_repo, ladder_repo)
            df_results = runner.run_backtest(min_warmup_campaigns=2)

            assert not df_results.empty
            assert "campaign_id" in df_results.columns
            assert "hist_payout" in df_results.columns
            assert "base_payout" in df_results.columns
            assert "opt_payout" in df_results.columns
            assert "opt_utilization" in df_results.columns

            # Ensure results/backtest_results.csv is generated
            csv_path = Path("results/backtest_results.csv")
            assert csv_path.exists()

        finally:
            conn.close()
            del conn
            gc.collect()
