"""
Finviz data access for ownership and stock data.

This module provides data-fetching primitives from Finviz that are used
by agents and other packages. The full screening/scoring logic stays in
scanners/finviz_scanner.py.

See docs/architecture/overview.md for import boundary rules.
"""

from __future__ import annotations

import pandas as pd
from finviz.screener import Screener

from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


def get_ownership_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Fetch ownership data for the given tickers from Finviz."""
    try:
        stock_list = Screener(
            tickers=list(tickers),
            table="Ownership",
        )
        return pd.DataFrame(stock_list.data)
    except Exception as e:
        logger.error(f"Error fetching ownership data from Finviz: {e}", exc_info=True)
        return pd.DataFrame()
