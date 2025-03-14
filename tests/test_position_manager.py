import unittest
import uuid
from unittest.mock import patch

from alpaca.trading.enums import PositionSide
from alpaca.trading.models import Position as AlpacaPosition

from alpacalyzer.trading.position_manager import PositionManager


class TestPositionManager(unittest.TestCase):
    @patch("alpacalyzer.trading.position_manager.trading_client.get_all_positions")
    @patch("alpacalyzer.trading.position_manager.get_strategy_positions")
    @patch("alpacalyzer.trading.position_manager.remove_position")
    @patch("alpacalyzer.trading.position_manager.logger")
    def test_update_positions(
        self, mock_logger, mock_remove_position, mock_get_strategy_positions, mock_get_all_positions
    ):
        # Mock data
        mock_alpaca_positions = [
            AlpacaPosition(
                symbol="AAPL",
                qty="10",
                current_price="150",
                asset_id=uuid.uuid4(),
                exchange="NASDAQ",
                asset_class="us_equity",
                avg_entry_price="145",
                side=PositionSide.LONG,
                cost_basis="1450",
            ),
            AlpacaPosition(
                symbol="GOOGL",
                qty="5",
                current_price="2800",
                asset_id=uuid.uuid4(),
                exchange="NASDAQ",
                asset_class="us_equity",
                avg_entry_price="2750",
                side=PositionSide.LONG,
                cost_basis="13750",
            ),
        ]
        mock_db_positions = [
            {"symbol": "AAPL", "entry_price": "145", "entry_time": "2023-01-01T00:00:00", "high_water_mark": "150"},
            {"symbol": "GOOGL", "entry_price": "2750", "entry_time": "2023-01-01T00:00:00", "high_water_mark": "2800"},
            {"symbol": "MSFT", "entry_price": "876", "entry_time": "2023-01-01T00:00:00", "high_water_mark": "876"},
        ]

        mock_get_all_positions.return_value = mock_alpaca_positions
        mock_get_strategy_positions.return_value = mock_db_positions

        # Initialize PositionManager
        pm = PositionManager()
        pm.positions = {}

        # Call update_positions
        updated_positions = pm.update_positions(show_status=False)

        # Assertions
        self.assertIn("AAPL", updated_positions)
        self.assertIn("GOOGL", updated_positions)
        self.assertNotIn("MSFT", updated_positions)
        self.assertEqual(updated_positions["AAPL"].current_price, 150.0)
        self.assertEqual(updated_positions["GOOGL"].current_price, 2800.0)
        mock_remove_position.assert_called_once_with("MSFT", "day")
        mock_logger.info.assert_called()

    @patch("alpacalyzer.trading.position_manager.trading_client.get_all_positions")
    @patch("alpacalyzer.trading.position_manager.get_strategy_positions")
    @patch("alpacalyzer.trading.position_manager.logger")
    def test_update_positions_exception(self, mock_logger, mock_get_strategy_positions, mock_get_all_positions):
        # Mock an exception
        mock_get_all_positions.side_effect = Exception("Test exception")

        # Initialize PositionManager
        pm = PositionManager()

        # Call update_positions
        updated_positions = pm.update_positions(show_status=False)

        # Assertions
        self.assertEqual(updated_positions, {})
        mock_logger.error.assert_called()


if __name__ == "__main__":
    unittest.main()
