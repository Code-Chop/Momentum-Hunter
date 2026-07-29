import os
import pandas as pd

from app.services.downloader import StockDownloader


downloader = StockDownloader()

stocks_df = pd.read_csv(
    "app/data/stocks.csv"
)

stocks = stocks_df["symbol"].tolist()

os.makedirs(
    "app/data/history",
    exist_ok=True
)

for stock in stocks:

    try:

        print(
            f"Downloading {stock}"
        )

        df = downloader.get_stock_data(
            stock,
            period="5y"
        )

        df.to_csv(
            f"app/data/history/{stock}.csv"
        )

    except Exception as e:

        print(
            stock,
            e
        )

print(
    "\nHistory download complete!"
)