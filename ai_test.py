"""
Smoke test for the full Gemini AI pipeline.
Run this to verify news fetching, prompt building, and JSON parsing work end-to-end.

Usage:
    python ai_test.py
"""
import pandas as pd
from app.services.news_service import NewsService
from app.services.gemini_service import GeminiService
from app.services.report_builder import ReportBuilder
from app.services.ai_parser import AIParser
from config import GEMINI_API_KEY

STOCK = "ASTRAMICRO"
SCORE = 40.32

news_service = NewsService()
builder = ReportBuilder()
gemini = GeminiService(GEMINI_API_KEY)
parser = AIParser()

print(f"Fetching news for {STOCK}...")
headlines = news_service.get_news(STOCK)
print(f"  {len(headlines)} headlines found")
for h in headlines:
    print(f"  - {h}")

single_df = pd.DataFrame([{"symbol": STOCK, "score": SCORE}])
prompt = builder.build_watchlist_prompt(single_df, {STOCK: headlines}, regime="BULL_LOW_VIX", vix="14.0")
print(f"\nPrompt size: {len(prompt)} characters")

print("\nCalling Gemini...")
response = gemini.analyze(prompt)
print(f"\nRaw response:\n{response}")

result = parser.parse(response)
print(f"\nParsed result:\n{result}")
