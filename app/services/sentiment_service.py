from sqlalchemy import case
from app.models import NewsItem


def signed_sentiment_expression():
    """Map label and confidence to a heuristic [-1, 1] score, not a probability."""
    return case(
        (NewsItem.sentiment_score.between(0, 1), case(
            (NewsItem.sentiment_label == "positive", NewsItem.sentiment_score),
            (NewsItem.sentiment_label == "negative", -NewsItem.sentiment_score),
            (NewsItem.sentiment_label == "neutral", 0.0),
            else_=None,
        )),
        else_=None,
    )
