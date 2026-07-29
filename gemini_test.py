import pandas as pd

from config import (
    GEMINI_API_KEY
)

from app.services.gemini_service import (
    GeminiService
)

from app.services.report_builder import (
    ReportBuilder
)


gemini = GeminiService(
    GEMINI_API_KEY
)

builder = ReportBuilder()

ranking_df = pd.read_csv(
    "app/data/watchlist.csv"
)

top_10 = ranking_df.head(10)

prompt = (
    builder.build_watchlist_prompt(
        top_10
    )
)

response = (
    gemini.analyze(
        prompt
    )
)

print(response)