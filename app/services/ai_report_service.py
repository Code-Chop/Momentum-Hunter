from app.logger import get_logger
from app.services.gemini_service import GeminiService
from app.services.report_builder import ReportBuilder
from app.services.ai_parser import AIParser
from app.services.news_service import NewsService
from config import GEMINI_API_KEY

logger = get_logger(__name__)


class AIReportService:

    def __init__(self):
        self.gemini = GeminiService(GEMINI_API_KEY)
        self.builder = ReportBuilder()
        self.parser = AIParser()
        self.news_service = NewsService()

    def generate_report(self, ranking_df, regime=None, vix=None):

        top_20 = ranking_df.head(20)
        logger.info("Analyzing %d stocks with Gemini...", len(top_20))

        news_data = {}
        for _, row in top_20.iterrows():
            symbol = row["symbol"]
            news_data[symbol] = self.news_service.get_news(symbol)
            logger.debug("%s: %d headlines", symbol, len(news_data[symbol]))

        prompt = self.builder.build_watchlist_prompt(top_20, news_data, regime=regime, vix=vix)
        logger.info("Prompt size: %d characters", len(prompt))

        response = self.gemini.analyze(prompt)
        logger.debug("Raw Gemini response:\n%s", response)

        parsed = self.parser.parse(response)
        return parsed
