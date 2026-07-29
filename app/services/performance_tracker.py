import pandas as pd
from datetime import datetime
from pathlib import Path
from app.logger import get_logger
from config import DATABASE_URL

logger = get_logger(__name__)


class PerformanceTracker:

    def save_daily_picks(self, ranking_df):

        top_10 = ranking_df.head(10)
        today = datetime.now().strftime("%Y-%m-%d")

        rows = []
        for _, row in top_10.iterrows():
            rows.append({
                "date": today,
                "symbol": row["symbol"],
                "momentum_score": row["score"],
                "ai_score": row["ai_score"],
                "final_score": row["final_score"],
            })

        df = pd.DataFrame(rows)

        if DATABASE_URL:
            from app.db import upsert_performance_log
            try:
                upsert_performance_log(df)
                logger.info("Performance log upserted to Postgres: %d picks for %s", len(rows), today)
            except Exception as e:
                logger.error("Failed to upsert performance log to Postgres: %s", e)

        file_path = "app/data/performance_log.csv"
        try:
            csv_df = df
            if Path(file_path).exists():
                old_df = pd.read_csv(file_path)
                csv_df = pd.concat([old_df, df], ignore_index=True)

            csv_df = csv_df.drop_duplicates(subset=["date", "symbol"], keep="last")
            csv_df.to_csv(file_path, index=False)
            logger.info("Performance log updated: %d picks saved for %s", len(rows), today)
        except OSError as e:
            logger.warning("Could not write performance_log.csv (ephemeral FS?): %s", e)
