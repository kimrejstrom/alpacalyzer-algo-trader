import sqlite3
from datetime import UTC, datetime

from alpacalyzer.utils.logger import logger

DB_FILE = "trading_positions.db"


def init_db():
    """Initialize the SQLite database for tracking positions."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            symbol TEXT NOT NULL,
            qty REAL NOT NULL,
            entry_price REAL NOT NULL,
            current_price REAL NOT NULL,
            high_water_mark REAL NOT NULL,
            pl_pct REAL DEFAULT 0.0,
            entry_time TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
            UNIQUE(strategy, symbol)
        )
    """)
    conn.commit()
    conn.close()


def upsert_position(
    strategy, symbol, qty, entry_price, current_price, high_water_mark, pl_pct, entry_time=None, side="BUY"
):
    """
    Insert a new position or update an existing one using SQLite's UPSERT functionality.

    The UNIQUE constraint on (strategy, symbol) ensures that if a record exists,
    it will be updated rather than duplicated.
    """
    entry_time = entry_time or datetime.now(UTC).isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
    INSERT INTO positions (strategy, symbol, qty, entry_price, current_price, high_water_mark, pl_pct, entry_time, side)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(strategy, symbol) DO UPDATE SET
        qty = excluded.qty,
        entry_price = excluded.entry_price,
        current_price = excluded.current_price,
        high_water_mark = excluded.high_water_mark,
        pl_pct = excluded.pl_pct,
        entry_time = excluded.entry_time,
        side = excluded.side
    """,
        (strategy, symbol, qty, entry_price, current_price, high_water_mark, pl_pct, entry_time, side),
    )
    conn.commit()
    conn.close()
    logger.debug(
        f"Upserted position for ticker: {symbol} - values: "
        "{strategy}, {qty}, {entry_price}, {current_price}, {high_water_mark}, {pl_pct}, {entry_time}, {side}"
    )


def update_prices(strategy, symbol, current_price, high_water_mark, pl_pct):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE positions
        SET current_price = ?, high_water_mark = ?, pl_pct = ?
        WHERE strategy = ? AND symbol = ?
    """,
        (current_price, high_water_mark, pl_pct, strategy, symbol),
    )
    conn.commit()
    conn.close()
    logger.debug(
        f"Updated prices for ticker: {symbol} - values: {strategy}, {current_price}, {high_water_mark}, {pl_pct}"
    )


def remove_position(symbol, strategy=None):
    """
    Remove a position from the database when closed.

    If a strategy is provided, remove only the position for that strategy and symbol;
    otherwise, remove all positions for the symbol.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if strategy:
        cursor.execute("DELETE FROM positions WHERE symbol = ? AND strategy = ?", (symbol, strategy))
    else:
        cursor.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
    conn.commit()
    conn.close()
    logger.debug(f"Removed position for ticker: {symbol} - Strategy: {strategy}")


def get_position_by_symbol_and_strategy(symbol, strategy):
    """Retrieve a position record by symbol and strategy."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions WHERE symbol = ? AND strategy = ?", (symbol, strategy))
    row = cursor.fetchone()
    conn.close()
    return row


def get_strategy_positions(strategy):
    """Retrieve all positions for a specific strategy."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions WHERE strategy = ?", (strategy,))
    positions = cursor.fetchall()
    conn.close()
    return positions


def get_all_positions():
    """Retrieve all positions in the database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions")
    positions = cursor.fetchall()
    conn.close()
    return positions
