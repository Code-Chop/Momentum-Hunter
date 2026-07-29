import yfinance as yf
from app.logger import get_logger
from config import VIX_HIGH, VIX_EXTREME

logger = get_logger(__name__)


class MarketFilter:

    def is_bull_market(self):
        try:
            nifty = yf.Ticker("^NSEI")
            df = nifty.history(period="1y")
            current_price = float(df["Close"].iloc[-1])
            dma_200 = float(df["Close"].rolling(200).mean().iloc[-1])
            bull = current_price > dma_200
            logger.debug("NIFTY %.2f vs 200 DMA %.2f -> %s", current_price, dma_200, "BULL" if bull else "BEAR")
            return bull
        except Exception as e:
            logger.warning("NIFTY fetch failed, defaulting to bull: %s", e)
            return True

    def get_india_vix(self):
        try:
            vix = yf.Ticker("^INDIAVIX")
            df = vix.history(period="5d")
            if df.empty:
                logger.warning("India VIX data empty")
                return None
            value = float(df["Close"].iloc[-1])
            logger.debug("India VIX: %.1f", value)
            return value
        except Exception as e:
            logger.warning("India VIX fetch failed: %s", e)
            return None

    def get_regime(self):
        """
        Returns (regime, top_n, vix_str).

        regime  : 'BEAR' | 'BULL_LOW_VIX' | 'BULL_HIGH_VIX' | 'BULL_EXTREME_VIX'
        top_n   : how many final picks to take (0 = skip scan entirely)
        vix_str : India VIX value as string for display
        """
        bull = self.is_bull_market()
        vix = self.get_india_vix()
        vix_str = f"{vix:.1f}" if vix is not None else "N/A"

        if not bull:
            logger.info("Regime: BEAR (NIFTY below 200 DMA)")
            return "BEAR", 0, vix_str

        if vix is not None and vix > VIX_EXTREME:
            logger.info("Regime: BULL_EXTREME_VIX (VIX=%.1f)", vix)
            return "BULL_EXTREME_VIX", 5, vix_str

        if vix is not None and vix > VIX_HIGH:
            logger.info("Regime: BULL_HIGH_VIX (VIX=%.1f)", vix)
            return "BULL_HIGH_VIX", 7, vix_str

        logger.info("Regime: BULL_LOW_VIX (VIX=%s)", vix_str)
        return "BULL_LOW_VIX", 10, vix_str
