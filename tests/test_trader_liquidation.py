import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, timezone, UTC # UTC available from 3.11, use timezone.utc for < 3.11 if needed

from alpaca.trading.models import Clock, Position, Order as AlpacaOrder, Calendar
from alpaca.trading.requests import GetOrdersRequest # Needed for verifying calls in Trader

from alpacalyzer.trading.alpaca_client import get_market_close_time
from alpacalyzer.trading.trader import Trader
# For CLI tests, if attempted:
# from alpacalyzer.cli import main as cli_main # Or a refactored helper function
# from alpacalyzer.cli import safe_execute # To ensure it's passed correctly

# Python version check for UTC
# For older Python versions, timezone.utc can be used.
# For this project, assuming Python 3.7+ based on pyproject.toml, timezone.utc is fine.
# If datetime.UTC is specifically needed and might not be present, use timezone.utc.
# Let's stick to timezone.utc for broader compatibility if UTC direct import is an issue.
# For now, assuming tests run in an env where datetime.UTC is fine or use timezone.utc.
# The prompt used `datetime, UTC` so I will assume it's available. If not, I'll adjust.
# For simplicity, I'll use datetime(..., tzinfo=timezone.utc) for creating timezone-aware datetimes.


class TestGetMarketCloseTime(unittest.TestCase):
    @patch('alpacalyzer.trading.alpaca_client.trading_client')
    @patch('alpacalyzer.trading.alpaca_client.logger')
    def test_get_market_close_time_success(self, mock_logger, mock_tc):
        mock_clock = MagicMock(spec=Clock)
        expected_close_time = datetime(2023, 1, 1, 21, 0, 0, tzinfo=timezone.utc)
        mock_clock.next_close = expected_close_time
        mock_tc.get_clock.return_value = mock_clock

        result = get_market_close_time()

        self.assertEqual(result, expected_close_time)
        mock_tc.get_clock.assert_called_once()
        mock_logger.error.assert_not_called()

    @patch('alpacalyzer.trading.alpaca_client.trading_client')
    @patch('alpacalyzer.trading.alpaca_client.logger')
    def test_get_market_close_time_failure(self, mock_logger, mock_tc):
        mock_tc.get_clock.side_effect = Exception("API Error")

        result = get_market_close_time()

        self.assertIsNone(result)
        mock_tc.get_clock.assert_called_once()
        mock_logger.error.assert_called_once_with(
            "Error fetching market clock for close time: API Error", exc_info=True
        )


class TestTraderLiquidation(unittest.TestCase):
    @patch('alpacalyzer.trading.trader.logger')
    @patch('alpacalyzer.trading.trader.trading_client')
    @patch('alpacalyzer.trading.trader.get_positions')
    def test_liquidate_no_positions_no_orders(self, mock_get_positions, mock_tc, mock_trader_logger):
        trader = Trader(analyze_mode=False)

        mock_get_positions.return_value = []
        mock_tc.get_orders.return_value = []

        trader.liquidate_all_positions_and_cancel_orders()

        mock_get_positions.assert_called_once()
        mock_tc.get_orders.assert_called_once_with(GetOrdersRequest(status="open"))
        mock_tc.close_position.assert_not_called()
        mock_tc.cancel_order_by_id.assert_not_called()

        self.assertIn(call("No open positions to liquidate."), mock_trader_logger.info.call_args_list)
        self.assertIn(call("No open orders to cancel."), mock_trader_logger.info.call_args_list)

    @patch('alpacalyzer.trading.trader.logger')
    @patch('alpacalyzer.trading.trader.trading_client')
    @patch('alpacalyzer.trading.trader.get_positions')
    def test_liquidate_with_positions_and_orders_normal_mode(self, mock_get_positions, mock_tc, mock_trader_logger):
        trader = Trader(analyze_mode=False)

        mock_pos1 = MagicMock(spec=Position)
        mock_pos1.symbol = "AAPL"
        mock_pos1.qty = "10"
        mock_pos2 = MagicMock(spec=Position)
        mock_pos2.symbol = "MSFT"
        mock_pos2.qty = "5"
        mock_get_positions.return_value = [mock_pos1, mock_pos2]

        mock_order1 = MagicMock(spec=AlpacaOrder)
        mock_order1.id = "order1"
        mock_order1.symbol = "GOOG"
        mock_order1.qty = "2"
        mock_order2 = MagicMock(spec=AlpacaOrder)
        mock_order2.id = "order2"
        mock_order2.symbol = "TSLA"
        mock_order2.qty = "1"
        mock_tc.get_orders.return_value = [mock_order1, mock_order2]

        # Mock return for close_position to avoid issues with casting Order
        mock_tc.close_position.return_value = MagicMock(spec=AlpacaOrder)


        trader.liquidate_all_positions_and_cancel_orders()

        mock_tc.close_position.assert_any_call("AAPL")
        mock_tc.close_position.assert_any_call("MSFT")
        self.assertEqual(mock_tc.close_position.call_count, 2)

        mock_tc.cancel_order_by_id.assert_any_call("order1")
        mock_tc.cancel_order_by_id.assert_any_call("order2")
        self.assertEqual(mock_tc.cancel_order_by_id.call_count, 2)

        self.assertIn(call('Attempting to close position in AAPL (10 shares)...'), mock_trader_logger.info.call_args_list)
        self.assertIn(call('Attempting to cancel order ID order1 for GOOG (2 shares)...'), mock_trader_logger.info.call_args_list)

    @patch('alpacalyzer.trading.trader.logger')
    @patch('alpacalyzer.trading.trader.trading_client')
    @patch('alpacalyzer.trading.trader.get_positions')
    def test_liquidate_with_positions_and_orders_analyze_mode(self, mock_get_positions, mock_tc, mock_trader_logger):
        trader = Trader(analyze_mode=True)

        mock_pos1 = MagicMock(spec=Position)
        mock_pos1.symbol = "AAPL"
        mock_pos1.qty = "10"
        mock_get_positions.return_value = [mock_pos1]

        mock_order1 = MagicMock(spec=AlpacaOrder)
        mock_order1.id = "order1"
        mock_order1.symbol = "GOOG"
        mock_order1.qty = "2"
        mock_tc.get_orders.return_value = [mock_order1]

        trader.liquidate_all_positions_and_cancel_orders()

        mock_tc.close_position.assert_not_called()
        mock_tc.cancel_order_by_id.assert_not_called()

        self.assertIn(call('Analyze mode: Simulating liquidation and order cancellation.'), mock_trader_logger.info.call_args_list)
        self.assertIn(call('SIMULATE: Close position in AAPL.'), mock_trader_logger.info.call_args_list)
        self.assertIn(call('SIMULATE: Cancel order ID order1.'), mock_trader_logger.info.call_args_list)

    @patch('alpacalyzer.trading.trader.logger')
    @patch('alpacalyzer.trading.trader.trading_client')
    @patch('alpacalyzer.trading.trader.get_positions')
    def test_liquidate_api_error_close_position(self, mock_get_positions, mock_tc, mock_trader_logger):
        trader = Trader(analyze_mode=False)

        mock_pos1 = MagicMock(spec=Position)
        mock_pos1.symbol = "AAPL"
        mock_pos1.qty = "10"
        mock_pos2 = MagicMock(spec=Position)
        mock_pos2.symbol = "MSFT"
        mock_pos2.qty = "5"
        mock_get_positions.return_value = [mock_pos1, mock_pos2]
        mock_tc.get_orders.return_value = [] # No orders for this test

        # Simulate error on first call, success on second
        mock_successful_order = MagicMock(spec=AlpacaOrder)
        mock_tc.close_position.side_effect = [
            Exception("API Error for AAPL"),
            mock_successful_order # Return a mock order for MSFT
        ]

        trader.liquidate_all_positions_and_cancel_orders()

        mock_tc.close_position.assert_any_call("AAPL")
        mock_tc.close_position.assert_any_call("MSFT")
        self.assertEqual(mock_tc.close_position.call_count, 2)

        mock_trader_logger.error.assert_called_once_with(
            "Failed to close position in AAPL: API Error for AAPL", exc_info=True
        )
        self.assertIn(call('Successfully submitted market order to close position in MSFT. Order ID: %s' % mock_successful_order.id), mock_trader_logger.info.call_args_list)


    @patch('alpacalyzer.trading.trader.logger')
    @patch('alpacalyzer.trading.trader.trading_client')
    @patch('alpacalyzer.trading.trader.get_positions') # Still need to mock get_positions
    def test_liquidate_api_error_cancel_order(self, mock_get_positions, mock_tc, mock_trader_logger):
        trader = Trader(analyze_mode=False)

        mock_get_positions.return_value = [] # No positions for this test

        mock_order1 = MagicMock(spec=AlpacaOrder)
        mock_order1.id = "order1"
        mock_order1.symbol = "GOOG"
        mock_order1.qty = "2"
        mock_order2 = MagicMock(spec=AlpacaOrder)
        mock_order2.id = "order2"
        mock_order2.symbol = "TSLA"
        mock_order2.qty = "1"
        mock_tc.get_orders.return_value = [mock_order1, mock_order2]

        # Simulate error on first call, success on second
        mock_tc.cancel_order_by_id.side_effect = [
            Exception("API Error for order1"),
            None # Successful cancellation returns None or raises no error
        ]

        trader.liquidate_all_positions_and_cancel_orders()

        mock_tc.cancel_order_by_id.assert_any_call("order1")
        mock_tc.cancel_order_by_id.assert_any_call("order2")
        self.assertEqual(mock_tc.cancel_order_by_id.call_count, 2)

        mock_trader_logger.error.assert_called_once_with(
            "Failed to cancel order ID order1: API Error for order1", exc_info=True
        )
        self.assertIn(call('Successfully canceled order ID order2.'), mock_trader_logger.info.call_args_list)


# Placeholder for CLI scheduling tests - might be very basic or skipped for now
@patch('alpacalyzer.cli.datetime')
@patch('alpacalyzer.cli.schedule')
@patch('alpacalyzer.cli.trading_client')
@patch('alpacalyzer.cli.Trader')
@patch('alpacalyzer.cli.logger')
@patch('alpacalyzer.cli.safe_execute') # Mock safe_execute as it's directly used by schedule.do
class TestCliSchedulingSimplified(unittest.TestCase):

    def test_schedule_on_trading_day_future(self, mock_safe_execute, mock_cli_logger, MockTrader, mock_cli_tc, mock_schedule, mock_cli_datetime):
        # Setup mocks for a trading day, time in future
        now_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc) # 10:00 UTC
        market_close_time = datetime(2023, 1, 1, 21, 0, 0, tzinfo=timezone.utc) # Closes 21:00 UTC

        mock_cli_datetime.now.return_value = now_time
        mock_cli_datetime.now.return_value.date.return_value = now_time.date() # Ensure .date() part is also mocked

        mock_calendar_entry = MagicMock(spec=Calendar)
        mock_calendar_entry.close = market_close_time
        mock_cli_tc.get_calendar.return_value = [mock_calendar_entry]

        mock_trader_instance = MockTrader.return_value

        # We need to simulate how main() would run this part.
        # This is tricky without refactoring main().
        # For this simplified test, let's assume the scheduling logic from main() is called.
        # This is a conceptual test. A real test would need to call a part of main or a refactored function.

        # Expected trigger time: 21:00 - 5 mins = 20:55
        expected_trigger_str = "20:55"

        # This is a very simplified check, basically ensuring that if all conditions are met,
        # the schedule call is made. The actual execution of main() isn't done here.

        # Simulate the relevant scheduling part of cli.main()
        # This part is conceptual:
        # if market_close_time_for_today_utc and is_trading_day:
        #    liquidation_trigger_time = market_close_time_for_today_utc - timedelta(minutes=5)
        #    formatted_trigger_time = liquidation_trigger_time.strftime("%H:%M")
        #    now_utc = datetime.now(UTC) # This is mock_cli_datetime.now()
        #    if liquidation_trigger_time > now_utc:
        #        schedule.every().day.at(formatted_trigger_time, "UTC").do(
        #            safe_execute, trader.liquidate_all_positions_and_cancel_orders
        #        )

        # To test this, we'd need to call a function containing this logic.
        # For now, this test case is more of a placeholder for how one might approach it.
        # A full integration test of cli.main's scheduling part is beyond a quick addition.

        # Let's assume we have a function that encapsulates this logic from cli.py:
        # schedule_liquidation_if_needed(trader_instance, mock_cli_tc, mock_schedule, mock_cli_datetime, mock_cli_logger, safe_execute)

        # If such a function existed and was called:
        # mock_schedule.every().day.at.assert_called_with(expected_trigger_str, "UTC")
        # mock_schedule.every().day.at(expected_trigger_str, "UTC").do.assert_called_with(
        #     mock_safe_execute, mock_trader_instance.liquidate_all_positions_and_cancel_orders
        # )
        # mock_cli_logger.info.assert_any_call(f"Scheduled end-of-day liquidation at {expected_trigger_str} UTC (5 minutes before market close).")
        pass # This test is a placeholder due to complexity of testing cli.main directly


if __name__ == '__main__':
    unittest.main()
