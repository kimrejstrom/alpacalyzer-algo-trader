import os
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

from alpacalyzer.data.cache import get_cache
from alpacalyzer.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)
from alpacalyzer.utils.logger import logger

# Global cache instance
_cache = get_cache()


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch price data with multi-source fallback strategy."""
    # Check cache first
    cache_key = ticker
    if cached_data := _cache.get_prices(cache_key):
        filtered_data = [Price(**price) for price in cached_data if start_date <= price["time"] <= end_date]
        if filtered_data:
            return filtered_data

    # Try primary source: Yahoo Finance
    try:
        # Get the data from Yahoo Finance
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(start=start_date, end=end_date)

        if not df.empty:
            prices = []
            for index, row in df.iterrows():
                date_str = index.strftime("%Y-%m-%d")
                price = Price(
                    open=float(row["Open"]),
                    close=float(row["Close"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    volume=int(row["Volume"]),
                    time=date_str,
                )
                prices.append(price)

            # Cache the results
            _cache.set_prices(cache_key, [p.model_dump() for p in prices])
            return prices
    except Exception as e:
        logger.debug(f"Yahoo Finance error for {ticker}: {str(e)}")

    # Return empty list if all sources fail
    return []


def get_financial_metrics(ticker: str, end_date: str, period: str = "ttm", limit: int = 10) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or APIs."""

    # Check cache first
    if cached_data := _cache.get_financial_metrics(ticker):
        # Filter cached data by date and limit
        filtered_data = [FinancialMetrics(**metric) for metric in cached_data if metric["report_period"] <= end_date]
        filtered_data.sort(key=lambda x: x.report_period, reverse=True)
        if filtered_data:
            return filtered_data[:limit]

    # If not in cache or insufficient data, fetch from Yahoo Finance
    try:
        yf_ticker = yf.Ticker(ticker)

        # Get various metrics
        info = yf_ticker.info
        financial_data = yf_ticker.financials
        balance_sheet = yf_ticker.balance_sheet
        cash_flow = yf_ticker.cashflow

        # Get quarterly data too for more data points if needed
        quarterly_financials = yf_ticker.quarterly_financials
        quarterly_balance_sheet = yf_ticker.quarterly_balance_sheet
        quarterly_cashflow = yf_ticker.quarterly_cashflow

        # Combine data sources based on available dates
        all_dates = set()
        for df in [
            financial_data,
            balance_sheet,
            cash_flow,
            quarterly_financials,
            quarterly_balance_sheet,
            quarterly_cashflow,
        ]:
            if not df.empty:
                all_dates.update(df.columns)

        # Sort dates in descending order
        sorted_dates = sorted(all_dates, reverse=True)

        # Create financial metrics for each date
        financial_metrics = []
        for i, date in enumerate(sorted_dates):
            if i >= limit:
                break

            report_date = date.strftime("%Y-%m-%d")
            if report_date > end_date:
                continue

            # Gather metrics that we can calculate
            try:
                # Basic metrics from info
                market_cap = info.get("marketCap")
                enterprise_value = info.get("enterpriseValue")

                # Price ratios
                pe_ratio = info.get("trailingPE")
                pb_ratio = info.get("priceToBook")
                ps_ratio = info.get("priceToSalesTrailing12Months")

                # Get financial data for this period if available
                net_income = get_value_from_df(financial_data, "Net Income", date)
                total_revenue = get_value_from_df(financial_data, "Total Revenue", date)

                # Balance sheet items
                total_assets = get_value_from_df(balance_sheet, "Total Assets", date)
                total_liabilities = get_value_from_df(balance_sheet, "Total Liabilities Net Minority Interest", date)
                total_equity = total_assets - total_liabilities if total_assets and total_liabilities else None

                # Cash flow items
                operating_cash_flow = get_value_from_df(cash_flow, "Operating Cash Flow", date)
                capital_expenditure = get_value_from_df(cash_flow, "Capital Expenditure", date)
                free_cash_flow = (
                    operating_cash_flow + capital_expenditure if operating_cash_flow and capital_expenditure else None
                )

                # Calculate derived metrics
                gross_margin = (
                    get_value_from_df(financial_data, "Gross Profit", date) / total_revenue if total_revenue else None
                )
                operating_margin = (
                    get_value_from_df(financial_data, "Operating Income", date) / total_revenue
                    if total_revenue
                    else None
                )
                net_margin = net_income / total_revenue if net_income and total_revenue else None

                # Return ratios
                return_on_equity = net_income / total_equity if net_income and total_equity else None
                return_on_assets = net_income / total_assets if net_income and total_assets else None

                # Liquidity ratios
                current_assets = get_value_from_df(balance_sheet, "Current Assets", date)
                current_liabilities = get_value_from_df(balance_sheet, "Current Liabilities", date)
                current_ratio = current_assets / current_liabilities if current_assets and current_liabilities else None

                # Debt ratios
                debt_to_equity = total_liabilities / total_equity if total_liabilities and total_equity else None

                # Growth metrics (calculate if previous period available)
                prev_date = sorted_dates[i + 1] if i + 1 < len(sorted_dates) else None
                if prev_date:
                    prev_revenue = get_value_from_df(financial_data, "Total Revenue", prev_date)
                    prev_net_income = get_value_from_df(financial_data, "Net Income", prev_date)

                    revenue_growth = (total_revenue / prev_revenue - 1) if total_revenue and prev_revenue else None
                    earnings_growth = (net_income / prev_net_income - 1) if net_income and prev_net_income else None
                else:
                    revenue_growth = None
                    earnings_growth = None

                # Per share values
                shares_outstanding = info.get("sharesOutstanding")
                if shares_outstanding:
                    earnings_per_share = net_income / shares_outstanding if net_income else None
                    book_value_per_share = total_equity / shares_outstanding if total_equity else None
                    free_cash_flow_per_share = free_cash_flow / shares_outstanding if free_cash_flow else None
                else:
                    earnings_per_share = info.get("trailingEps")
                    book_value_per_share = None
                    free_cash_flow_per_share = None

                # Create the metrics object
                metrics = FinancialMetrics(
                    ticker=ticker,
                    report_period=report_date,
                    period=period,
                    currency=info.get("currency", "USD"),
                    market_cap=market_cap,
                    enterprise_value=enterprise_value,
                    price_to_earnings_ratio=pe_ratio,
                    price_to_book_ratio=pb_ratio,
                    price_to_sales_ratio=ps_ratio,
                    enterprise_value_to_ebitda_ratio=info.get("enterpriseToEbitda"),
                    enterprise_value_to_revenue_ratio=enterprise_value / total_revenue
                    if enterprise_value and total_revenue
                    else None,
                    free_cash_flow_yield=free_cash_flow / market_cap if free_cash_flow and market_cap else None,
                    peg_ratio=info.get("pegRatio"),
                    gross_margin=gross_margin,
                    operating_margin=operating_margin,
                    net_margin=net_margin,
                    return_on_equity=return_on_equity,
                    return_on_assets=return_on_assets,
                    return_on_invested_capital=info.get("returnOnAssets"),  # Approximation
                    asset_turnover=total_revenue / total_assets if total_revenue and total_assets else None,
                    inventory_turnover=None,  # Not easily available
                    receivables_turnover=None,  # Not easily available
                    days_sales_outstanding=None,  # Not easily available
                    operating_cycle=None,  # Not easily available
                    working_capital_turnover=None,  # Not easily available
                    current_ratio=current_ratio,
                    quick_ratio=None,  # Not easily available
                    cash_ratio=None,  # Not easily available
                    operating_cash_flow_ratio=operating_cash_flow / current_liabilities
                    if operating_cash_flow and current_liabilities
                    else None,
                    debt_to_equity=debt_to_equity,
                    debt_to_assets=total_liabilities / total_assets if total_liabilities and total_assets else None,
                    interest_coverage=None,  # Not easily available
                    revenue_growth=revenue_growth,
                    earnings_growth=earnings_growth,
                    book_value_growth=None,  # Requires more historical data
                    earnings_per_share_growth=None,  # Requires more historical data
                    free_cash_flow_growth=None,  # Requires more historical data
                    operating_income_growth=None,  # Requires more historical data
                    ebitda_growth=None,  # Requires more historical data
                    payout_ratio=info.get("payoutRatio"),
                    earnings_per_share=earnings_per_share,
                    book_value_per_share=book_value_per_share,
                    free_cash_flow_per_share=free_cash_flow_per_share,
                )

                financial_metrics.append(metrics)

            except Exception as e:
                logger.debug(f"Error processing metrics for {ticker} on {report_date}: {str(e)}")
                continue

        # Cache the results
        if financial_metrics:
            _cache.set_financial_metrics(ticker, [m.model_dump() for m in financial_metrics])

        return financial_metrics

    except Exception as e:
        logger.debug(f"Error fetching financial metrics for {ticker}: {str(e)}")
        return []


def search_line_items(
    ticker: str, line_items: list[str], end_date: str, period: str = "ttm", limit: int = 10
) -> list[LineItem]:
    """Search financial line items for a ticker."""

    try:
        yf_ticker = yf.Ticker(ticker)

        # Get financial statements
        income_stmt = yf_ticker.income_stmt
        balance_sheet = yf_ticker.balance_sheet
        cash_flow = yf_ticker.cashflow

        # Also get quarterly data
        q_income_stmt = yf_ticker.quarterly_income_stmt
        q_balance_sheet = yf_ticker.quarterly_balance_sheet
        q_cash_flow = yf_ticker.quarterly_cashflow

        # Use info for some common items
        info = yf_ticker.info

        # Get all available dates from the statements
        all_dates = set()
        for df in [income_stmt, balance_sheet, cash_flow, q_income_stmt, q_balance_sheet, q_cash_flow]:
            if hasattr(df, "columns"):
                all_dates.update(df.columns)

        # Sort dates in descending order
        sorted_dates = sorted(all_dates, reverse=True)

        # Create line items for each date
        result_items = []
        for i, date in enumerate(sorted_dates):
            if i >= limit:
                break

            report_date = date.strftime("%Y-%m-%d")
            if report_date > end_date:
                continue

            # Create a base line item with required fields
            line_item_data = {
                "ticker": ticker,
                "report_period": report_date,
                "period": period,
                "currency": info.get("currency", "USD"),
            }

            # Map requested line items to financial statement items
            line_item_mapping = {
                "revenue": ("Total Revenue", income_stmt),
                "net_income": ("Net Income", income_stmt),
                "operating_income": ("Operating Income", income_stmt),
                "gross_margin": (None, None),  # Will calculate from Gross Profit / Revenue
                "operating_margin": (None, None),  # Will calculate from Operating Income / Revenue
                "return_on_invested_capital": (None, None),  # Will calculate
                "free_cash_flow": (None, None),  # Will calculate from OCF - CapEx
                "cash_and_equivalents": ("Cash And Cash Equivalents", balance_sheet),
                "total_debt": ("Total Debt", balance_sheet),
                "total_assets": ("Total Assets", balance_sheet),
                "total_liabilities": ("Total Liabilities Net Minority Interest", balance_sheet),
                "shareholders_equity": ("Stockholders Equity", balance_sheet),
                "working_capital": (None, None),  # Will calculate
                "capital_expenditure": ("Capital Expenditure", cash_flow),
                "depreciation_and_amortization": ("Depreciation And Amortization", cash_flow),
                "research_and_development": ("Research And Development", income_stmt),
                "goodwill_and_intangible_assets": (None, None),  # Will calculate
                "outstanding_shares": (None, None),  # Will get from info
                "dividends_and_other_cash_distributions": ("Dividends Paid", cash_flow),
            }

            # Fill in values for each requested line item
            for item in line_items:
                if item in line_item_mapping:
                    field_name, source_df = line_item_mapping[item]

                    # Direct mapping to a field
                    if field_name and source_df is not None:
                        line_item_data[item] = get_value_from_df(source_df, field_name, date)

                    # Special calculations
                    elif item == "gross_margin":
                        gross_profit = get_value_from_df(income_stmt, "Gross Profit", date)
                        revenue = get_value_from_df(income_stmt, "Total Revenue", date)
                        if gross_profit and revenue:
                            line_item_data[item] = gross_profit / revenue

                    elif item == "operating_margin":
                        op_income = get_value_from_df(income_stmt, "Operating Income", date)
                        revenue = get_value_from_df(income_stmt, "Total Revenue", date)
                        if op_income and revenue:
                            line_item_data[item] = op_income / revenue

                    elif item == "free_cash_flow":
                        ocf = get_value_from_df(cash_flow, "Operating Cash Flow", date)
                        capex = get_value_from_df(cash_flow, "Capital Expenditure", date)
                        if ocf and capex:
                            line_item_data[item] = ocf + capex  # CapEx is usually negative

                    elif item == "working_capital":
                        current_assets = get_value_from_df(balance_sheet, "Current Assets", date)
                        current_liabilities = get_value_from_df(balance_sheet, "Current Liabilities", date)
                        if current_assets and current_liabilities:
                            line_item_data[item] = current_assets - current_liabilities

                    elif item == "goodwill_and_intangible_assets":
                        goodwill = get_value_from_df(balance_sheet, "Goodwill", date)
                        intangibles = get_value_from_df(balance_sheet, "Intangible Assets", date)
                        if goodwill or intangibles:
                            line_item_data[item] = (goodwill or 0) + (intangibles or 0)

                    elif item == "outstanding_shares":
                        line_item_data[item] = info.get("sharesOutstanding")

                    elif item == "return_on_invested_capital":
                        net_income = get_value_from_df(income_stmt, "Net Income", date)
                        total_equity = get_value_from_df(balance_sheet, "Stockholders Equity", date)
                        total_debt = get_value_from_df(balance_sheet, "Total Debt", date)
                        if net_income and (total_equity or total_debt):
                            invested_capital = (total_equity or 0) + (total_debt or 0)
                            if invested_capital > 0:
                                line_item_data[item] = net_income / invested_capital

                    elif item == "debt_to_equity":
                        total_debt = get_value_from_df(balance_sheet, "Total Debt", date)
                        total_equity = get_value_from_df(balance_sheet, "Stockholders Equity", date)
                        if total_debt and total_equity and total_equity > 0:
                            line_item_data[item] = total_debt / total_equity

            # Create the LineItem object
            result_items.append(LineItem(**line_item_data))

        return result_items

    except Exception as e:
        logger.debug(f"Error fetching line items for {ticker}: {str(e)}")
        return []


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[InsiderTrade]:
    """Fetch insider trades from SEC API or Alpha Vantage."""
    # Check cache first
    if cached_data := _cache.get_insider_trades(ticker):
        # Filter cached data by date range
        filtered_data = [
            InsiderTrade(**trade)
            for trade in cached_data
            if (start_date is None or (trade.get("transaction_date") or trade["filing_date"]) >= start_date)
            and (trade.get("transaction_date") or trade["filing_date"]) <= end_date
        ]
        filtered_data.sort(key=lambda x: x.transaction_date or x.filing_date, reverse=True)
        if filtered_data:
            return filtered_data

    # If not in cache or insufficient data, fetch from a free API
    # Using Alpha Vantage (need to get a free API key)
    try:
        ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "test")

        if not ALPHA_VANTAGE_API_KEY:
            logger.debug("No Alpha Vantage API key found. Set ALPHA_VANTAGE_API_KEY in your environment.")
            return []

        url = f"https://www.alphavantage.co/query?function=INSIDER_TRANSACTIONS&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            logger.debug(f"Error fetching insider data from Alpha Vantage: {response.status_code}")
            return []

        data = response.json()

        # Extract insider trades
        insider_trades = []
        if "transactions" in data:
            for trade in data["transactions"]:
                filing_date = trade.get("filingDate", "")
                transaction_date = trade.get("transactionDate", "")

                # Apply date filtering
                if start_date and transaction_date < start_date:
                    continue
                if end_date and transaction_date > end_date:
                    continue

                # Parse values
                try:
                    shares_str = trade.get("numberOfShares", "0").replace(",", "")
                    shares = float(shares_str) if shares_str else 0

                    price_str = trade.get("transactionPrice", "0").replace("$", "").replace(",", "")
                    price = float(price_str) if price_str else 0

                    transaction_value = shares * price
                except (ValueError, TypeError):
                    shares = 0
                    price = 0
                    transaction_value = 0

                # Determine if it's a buy or sell
                transaction_type = "Buy" if "P - Purchase" in trade.get("transactionType", "") else "Sale"

                insider_trade = InsiderTrade(
                    ticker=ticker,
                    issuer=data.get("symbol", ticker),
                    name=trade.get("reportingName", ""),
                    title=trade.get("reportingPerson", {}).get("title", ""),
                    is_board_director="Director" in trade.get("reportingPerson", {}).get("title", ""),
                    transaction_date=transaction_date,
                    transaction_shares=shares * (1 if transaction_type == "Buy" else -1),
                    transaction_price_per_share=price,
                    transaction_value=transaction_value,
                    shares_owned_before_transaction=None,  # Not always available
                    shares_owned_after_transaction=None,  # Not always available
                    security_title=trade.get("securityTitle", ""),
                    filing_date=filing_date,
                )

                insider_trades.append(insider_trade)

        # Sort by transaction date, newest first
        insider_trades.sort(key=lambda x: x.transaction_date or "", reverse=True)

        # Limit results
        insider_trades = insider_trades[:limit]

        # Cache the results
        if insider_trades:
            _cache.set_insider_trades(ticker, [trade.model_dump() for trade in insider_trades])

        return insider_trades

    except Exception as e:
        logger.debug(f"Error fetching insider trades for {ticker}: {str(e)}")

        # Fallback to empty result
        return []


def get_company_news(ticker: str, end_date: str, start_date: str | None = None, limit: int = 100) -> list[CompanyNews]:
    """Fetch news articles for a ticker."""

    # Check cache first
    if cached_data := _cache.get_company_news(ticker):
        # Filter cached data by date range
        filtered_data = [
            CompanyNews(**news)
            for news in cached_data
            if (start_date is None or news["date"] >= start_date) and news["date"] <= end_date
        ]
        filtered_data.sort(key=lambda x: x.date, reverse=True)
        if filtered_data:
            return filtered_data

    # If not in cache or insufficient data, fetch from Yahoo Finance
    try:
        # Convert dates to datetime objects for comparison
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else end_dt - timedelta(days=90)

        # Get news from Yahoo Finance
        yf_ticker = yf.Ticker(ticker)
        news_data = yf_ticker.news

        # Process the news
        news_items = []
        for news in news_data:
            # Get the timestamp and convert to date
            timestamp = news.get("providerPublishTime", 0)
            logger.debug(f"Raw providerPublishTime value: {timestamp} (type: {type(timestamp)})")

            news_date = datetime.fromtimestamp(timestamp)
            date_str = news_date.strftime("%Y-%m-%d")

            # Apply date filtering
            if news_date < start_dt or news_date > end_dt:
                continue

            # Extract source and author
            publisher = news.get("publisher", "")
            author = news.get("publisher", "")

            # Extract sentiment (not available in Yahoo, set neutral as default)
            sentiment = "neutral"

            # Create the news object
            news_item = CompanyNews(
                ticker=ticker,
                title=news.get("title", ""),
                author=author,
                source=publisher,
                date=date_str,
                url=news.get("link", ""),
                sentiment=sentiment,
            )

            news_items.append(news_item)

            # Respect the limit
            if len(news_items) >= limit:
                break

        # Sort by date, newest first
        news_items.sort(key=lambda x: x.date, reverse=True)

        # Cache the results
        if news_items:
            _cache.set_company_news(ticker, [news.model_dump() for news in news_items])

        return news_items

    except Exception as e:
        logger.debug(f"Error fetching company news for {ticker}: {str(e)}")
        return []


def get_market_cap(
    ticker: str,
    end_date: str,
) -> float | None:
    """Fetch market cap from Yahoo Finance."""
    try:
        yf_ticker = yf.Ticker(ticker)
        info = yf_ticker.info

        # Get market cap directly
        market_cap = info.get("marketCap")

        if market_cap:
            return float(market_cap)

        # If not available, try to calculate from price * shares outstanding
        prev_close = info.get("previousClose")
        shares_outstanding = info.get("sharesOutstanding")

        if prev_close and shares_outstanding:
            return float(prev_close * shares_outstanding)

        return None

    except Exception as e:
        logger.debug(f"Error fetching market cap for {ticker}: {str(e)}")

        # Try to get from financial metrics as fallback
        financial_metrics = get_financial_metrics(ticker, end_date)
        if financial_metrics and financial_metrics[0].market_cap:
            return financial_metrics[0].market_cap

        return None


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Get price data as a DataFrame."""
    prices = get_prices(ticker, start_date, end_date)
    return prices_to_df(prices)


# Helper functions
def get_value_from_df(df, field_name, date):
    """Safely extract a value from a dataframe if it exists."""
    if df is None or df.empty or field_name not in df.index:
        return None

    try:
        value = df.loc[field_name, date]
        return float(value) if not pd.isna(value) else None
    except (KeyError, ValueError, TypeError):
        return None
