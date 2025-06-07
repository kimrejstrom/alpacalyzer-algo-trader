import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from alpaca.trading.models import Position, Order, Asset
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass, AssetStatus, OrderStatus, OrderType

# Assuming models and Trader are accessible via these paths
from alpacalyzer.data.models import TradingStrategy, EntryCriteria, EntryType
from alpacalyzer.trading.trader import Trader
from alpacalyzer.analysis.technical_analysis import TradingSignals # Or wherever it's defined

# A dummy asset for mocking
def mock_asset(symbol="AAPL", tradable=True, shortable=True):
    return Asset(
        id=f"asset_{symbol}",
        asset_class=AssetClass.US_EQUITY,
        exchange="NASDAQ",
        symbol=symbol,
        name=f"{symbol} Inc.",
        status=AssetStatus.ACTIVE,
        tradable=tradable,
        marginable=True,
        shortable=shortable,
        easy_to_borrow=True,
        fractionable=True,
        maintenance_margin_requirement=0.3,
        min_order_size=None,
        min_trade_increment=None,
        price_increment=None,
        attributes=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        deleted_at=None,
    )

# A dummy position for mocking
def mock_position(symbol="AAPL", qty="10", side="long", avg_entry_price="150.00", current_price="155.00"):
    return Position(
        asset_id=f"asset_{symbol}",
        symbol=symbol,
        exchange="NASDAQ",
        asset_class=AssetClass.US_EQUITY,
        avg_entry_price=avg_entry_price,
        qty=qty,
        side=side,
        market_value=str(float(qty) * float(current_price)),
        cost_basis=str(float(qty) * float(avg_entry_price)),
        unrealized_pl=str(float(qty) * (float(current_price) - float(avg_entry_price))),
        unrealized_plpc=str((float(current_price) - float(avg_entry_price)) / float(avg_entry_price)),
        unrealized_intraday_pl="0",
        unrealized_intraday_plpc="0",
        current_price=current_price,
        lastday_price="149.00",
        change_today="0.01",
        asset_marginable=True,
        qty_available="10",
    )

# A dummy order for mocking
def mock_order(symbol="AAPL", qty="10", side=OrderSide.BUY, status=OrderStatus.FILLED, limit_price=None, stop_price=None, take_profit_price=None):
    return Order(
        id=f"order_{symbol}_{side}_{datetime.now().timestamp()}",
        client_order_id=f"client_order_{symbol}_{side}",
        created_at=datetime.now() - timedelta(seconds=10),
        updated_at=datetime.now() - timedelta(seconds=5),
        submitted_at=datetime.now() - timedelta(seconds=10),
        filled_at=datetime.now() - timedelta(seconds=5) if status == OrderStatus.FILLED else None,
        expired_at=None,
        canceled_at=None,
        failed_at=None,
        replaced_at=None,
        replaced_by=None,
        replaces=None,
        asset_id=f"asset_{symbol}",
        symbol=symbol,
        asset_class=AssetClass.US_EQUITY,
        notional=str(float(qty) * float(limit_price)) if limit_price else None,
        qty=qty,
        filled_qty=qty if status == OrderStatus.FILLED else "0",
        filled_avg_price=limit_price if status == OrderStatus.FILLED and limit_price else None,
        order_class="simple", # or "bracket"
        order_type=OrderType.LIMIT if limit_price else OrderType.MARKET,
        type=OrderType.LIMIT if limit_price else OrderType.MARKET,
        side=side,
        time_in_force=TimeInForce.GTC,
        limit_price=limit_price,
        stop_price=stop_price,
        status=status,
        extended_hours=False,
        legs=None,
        trail_percent=None,
        trail_price=None,
        hwm=None,
        subtag=None,
        source=None,
        commission=None,
    )

class TestTraderCooldown(unittest.TestCase):

    def setUp(self):
        # Mock external dependencies
        self.mock_trading_client = MagicMock()
        self.mock_technical_analyzer = MagicMock()

        # Patch the trading_client and technical_analyzer where they are imported in the Trader module
        self.trading_client_patch = patch('alpacalyzer.trading.trader.trading_client', self.mock_trading_client)
        self.technical_analyzer_patch = patch('alpacalyzer.trading.trader.TechnicalAnalyzer', return_value=self.mock_technical_analyzer)

        self.trading_client_patch.start()
        self.technical_analyzer_patch.start()

        # Mock get_positions and get_market_status if Trader calls them directly at init or elsewhere
        patch('alpacalyzer.trading.trader.get_positions', return_value=[]).start()
        patch('alpacalyzer.trading.trader.get_market_status', return_value="open").start()
        self.addCleanup(patch.stopall)


    def tearDown(self):
        patch.stopall() # Stops all patches started with start()

    @patch('alpacalyzer.trading.trader.datetime')
    def test_cooldown_timestamp_recorded_on_close(self, mock_dt):
        now = datetime(2023, 1, 1, 12, 0, 0)
        mock_dt.now.return_value = now

        trader = Trader(cooldown_hours=1)
        ticker = "AAPL"
        strategy = TradingStrategy(
            ticker=ticker,
            quantity=10,
            entry_point=150.0,
            stop_loss=140.0,
            target_price=160.0,
            risk_reward_ratio=1.0,
            strategy_notes="Test",
            trade_type="long",
            entry_criteria=[],
            cooldown_until=None  # Explicitly set for clarity
        )
        trader.latest_strategies = [strategy]

        # Mock position and order returned by close_position
        current_position = mock_position(symbol=ticker)
        closed_order = mock_order(symbol=ticker, side=OrderSide.SELL, status=OrderStatus.FILLED)

        self.mock_trading_client.get_positions.return_value = [current_position]
        self.mock_trading_client.close_position.return_value = closed_order
        self.mock_trading_client.get_orders.return_value = [] # No open orders to cancel

        # Mock technical signals for exit condition (simplified)
        self.mock_technical_analyzer.analyze_stock.return_value = TradingSignals(
            raw_data_daily=MagicMock(), raw_data_intraday=MagicMock(),
            price=140.0, signals=['TA: Some Exit Signal'], momentum=-6, score=0.4, atr=2.0, rvol=1.5 # Trigger exit
        )

        trader.monitor_and_trade() # This should trigger close_position

        self.mock_trading_client.close_position.assert_called_once_with(ticker)
        self.assertIsNotNone(strategy.cooldown_until)
        self.assertEqual(strategy.cooldown_until, now + timedelta(hours=1))

    @patch('alpacalyzer.trading.trader.datetime')
    def test_entry_blocked_during_cooldown(self, mock_dt):
        now = datetime(2023, 1, 1, 12, 0, 0)
        mock_dt.now.return_value = now

        trader = Trader(cooldown_hours=1)
        ticker = "MSFT"
        cooldown_end_time = now + timedelta(minutes=30) # Still in cooldown

        strategy = TradingStrategy(
            ticker=ticker, quantity=5, entry_point=300.0, stop_loss=290.0, target_price=310.0,
            risk_reward_ratio=1.0, strategy_notes="Test", trade_type="long", entry_criteria=[],
            cooldown_until=cooldown_end_time
        )
        trader.latest_strategies = [strategy]

        # Mock asset tradable
        self.mock_trading_client.get_asset.return_value = mock_asset(symbol=ticker)

        # Mock technical signals for entry condition (simplified)
        # Price is at entry point, RSI good, etc. -> should normally enter
        self.mock_technical_analyzer.analyze_stock.return_value = TradingSignals(
            raw_data_daily=MagicMock(iloc=MagicMock(return_value={"RSI": 50, "SMA_20": 290, "SMA_50": 280})),
            raw_data_intraday=MagicMock(iloc=MagicMock(return_value={})), # No specific candle needed for this test
            price=300.0, signals=['TA: Strong Buy'], momentum=5, score=0.9, atr=2.0, rvol=1.5
        )
        # Ensure check_entry_conditions uses the mocked daily/intraday data correctly
        strategy.entry_criteria = [EntryCriteria(entry_type=EntryType.ABOVE_MOVING_AVERAGE_20, value=0)] # Dummy criteria

        with patch('alpacalyzer.trading.trader.logger') as mock_logger:
            trader.monitor_and_trade()

        self.mock_trading_client.submit_order.assert_not_called()
        mock_logger.info.assert_any_call(f"Ticker {ticker} is in cooldown until {cooldown_end_time}. Entry blocked.")

    @patch('alpacalyzer.trading.trader.datetime')
    def test_entry_allowed_after_cooldown(self, mock_dt):
        now = datetime(2023, 1, 1, 12, 0, 0)
        mock_dt.now.return_value = now

        trader = Trader(cooldown_hours=1)
        ticker = "GOOG"
        cooldown_end_time = now - timedelta(minutes=30) # Cooldown expired

        strategy = TradingStrategy(
            ticker=ticker, quantity=3, entry_point=2500.0, stop_loss=2400.0, target_price=2600.0,
            risk_reward_ratio=1.0, strategy_notes="Test", trade_type="long", entry_criteria=[],
            cooldown_until=cooldown_end_time
        )
        trader.latest_strategies = [strategy]

        self.mock_trading_client.get_asset.return_value = mock_asset(symbol=ticker)
        self.mock_trading_client.submit_order.return_value = mock_order(symbol=ticker, status=OrderStatus.ACCEPTED)


        # Mock technical signals for entry
        self.mock_technical_analyzer.analyze_stock.return_value = TradingSignals(
            raw_data_daily=MagicMock(iloc=MagicMock(return_value={"RSI": 50, "SMA_20": 2450, "SMA_50": 2400})),
            raw_data_intraday=MagicMock(iloc=MagicMock(return_value={})),
            price=2500.0, signals=['TA: Strong Buy'], momentum=5, score=0.9, atr=20.0, rvol=1.5
        )
        strategy.entry_criteria = [EntryCriteria(entry_type=EntryType.ABOVE_MOVING_AVERAGE_20, value=0)]


        trader.monitor_and_trade()

        self.mock_trading_client.submit_order.assert_called_once()
        # Further assertions can be made on the order details if necessary


if __name__ == '__main__':
    unittest.main()
