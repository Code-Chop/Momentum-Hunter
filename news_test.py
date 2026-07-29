from app.services.news_service import (
    NewsService
)

news_service = NewsService()

headlines = (
    news_service.get_news(
        "RELIANCE"
    )
)

print("\nHEADLINES\n")

for headline in headlines:

    print("-", headline)