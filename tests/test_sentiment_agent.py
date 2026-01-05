from unittest.mock import MagicMock, patch

import pytest

from alpacalyzer.agents.sentiment_agent import calculate_sentiment_signals, sentiment_agent
from alpacalyzer.data.models import SentimentAnalysis, SentimentAnalysisResponse


@pytest.fixture
def mock_state():
    return {
        "data": {"tickers": ["AAPL", "TSLA"], "analyst_signals": {}},
        "metadata": {"show_reasoning": False},
        "messages": [],
    }


@patch("alpacalyzer.agents.sentiment_agent.FinvizScanner")
@patch("alpacalyzer.agents.sentiment_agent.YFinanceClient")
@patch("alpacalyzer.agents.sentiment_agent.calculate_sentiment_signals")
def test_sentiment_agent_success(mock_calculate_sentiment_signals, mock_yfinance_client, mock_finviz_scanner, mock_state):
    # Mock FinvizScanner
    mock_finviz_scanner.return_value.get_ownership_stocks.return_value = MagicMock(loc=MagicMock(return_value=MagicMock(empty=False, __getitem__=MagicMock(return_value=["-0.26%"]))))

    # Mock YFinanceClient
    mock_yfinance_client.return_value.get_news.return_value = [
        {
            "content": {
                "title": "News Title",
                "summary": "Summary",
                "description": "Description",
                "pubDate": "2023-01-01",
            }
        }
    ]

    # Mock calculate_sentiment_signals with proper Pydantic model objects
    mock_calculate_sentiment_signals.return_value = SentimentAnalysisResponse(
        sentiment_analysis=[SentimentAnalysis(sentiment="Bullish", score=0.8, highlights=["Positive highlight"], rationale="This is bullish")]
    )

    result = sentiment_agent(mock_state)

    assert "messages" in result
    assert "data" in result
    assert "sentiment_agent" in result["data"]["analyst_signals"]
    assert "AAPL" in result["data"]["analyst_signals"]["sentiment_agent"]
    assert result["data"]["analyst_signals"]["sentiment_agent"]["AAPL"]["signal"] == "bullish"


@patch("alpacalyzer.agents.sentiment_agent.FinvizScanner")
@patch("alpacalyzer.agents.sentiment_agent.YFinanceClient")
def test_sentiment_agent_no_news(mock_yfinance_client, mock_finviz_scanner, mock_state):
    # Mock FinvizScanner
    mock_finviz_scanner.return_value.get_ownership_stocks.return_value = MagicMock(loc=MagicMock(return_value=MagicMock(empty=False, __getitem__=MagicMock(return_value=["-0.26%"]))))

    # Mock YFinanceClient
    mock_yfinance_client.return_value.get_news.return_value = None

    result = sentiment_agent(mock_state)

    assert "messages" in result
    assert "data" in result
    assert "sentiment_agent" in result["data"]["analyst_signals"]
    # Check that the function ran but doesn't check for specific ticker results
    # as they might not be present due to the no news condition
    assert isinstance(result["data"]["analyst_signals"]["sentiment_agent"], dict)


@patch("alpacalyzer.agents.sentiment_agent.call_gpt_structured")
def test_calculate_sentiment_signals(mock_call_gpt_structured):
    # Use proper Pydantic model objects
    mock_call_gpt_structured.return_value = SentimentAnalysisResponse(
        sentiment_analysis=[
            SentimentAnalysis(
                sentiment="Bullish",
                score=0.7,
                highlights=["Positive news", "Good outlook"],
                rationale="Company shows strong growth potential",
            )
        ]
    )

    news_items = [{"title": "News Title", "summary": "Summary", "description": "Description", "pubDate": "2023-01-01"}]

    result = calculate_sentiment_signals(news_items)

    assert result is not None
    assert len(result.sentiment_analysis) > 0
    assert result.sentiment_analysis[0].sentiment == "Bullish"
