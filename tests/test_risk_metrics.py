"""Tests for risk-adjusted performance metrics."""

from alpacalyzer.analysis.risk_metrics import (
    calculate_calmar_ratio,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
)


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_sharpe_ratio_basic(self):
        """Test basic Sharpe ratio calculation."""
        returns = [0.01, 0.02, -0.01, 0.015, 0.025]
        risk_free_rate = 0.0

        result = calculate_sharpe_ratio(returns, risk_free_rate)

        assert result is not None
        assert isinstance(result, float)

    def test_sharpe_ratio_with_risk_free_rate(self):
        """Test Sharpe ratio with non-zero risk-free rate."""
        returns = [0.02, 0.03, 0.01, 0.025, 0.015]
        risk_free_rate = 0.02 / 252

        result = calculate_sharpe_ratio(returns, risk_free_rate)

        assert result is not None

    def test_sharpe_ratio_zero_volatility(self):
        """Test Sharpe ratio when returns have zero standard deviation."""
        returns = [0.01, 0.01, 0.01, 0.01]

        result = calculate_sharpe_ratio(returns, 0.0)

        assert result == 0.0

    def test_sharpe_ratio_empty_returns(self):
        """Test Sharpe ratio with empty returns."""
        returns = []

        result = calculate_sharpe_ratio(returns, 0.0)

        assert result == 0.0


class TestSortinoRatio:
    """Tests for Sortino ratio calculation."""

    def test_sortino_ratio_basic(self):
        """Test basic Sortino ratio calculation."""
        returns = [0.01, 0.02, -0.01, 0.015, 0.025]
        risk_free_rate = 0.0

        result = calculate_sortino_ratio(returns, risk_free_rate)

        assert result is not None
        assert isinstance(result, float)

    def test_sortino_ratio_with_upside_volatility(self):
        """Test Sortino ratio only penalizes downside volatility."""
        returns = [0.05, 0.05, 0.05, 0.05]
        risk_free_rate = 0.0

        result = calculate_sortino_ratio(returns, risk_free_rate)

        assert result > 0

    def test_sortino_ratio_zero_downside_deviation(self):
        """Test Sortino ratio when there is no downside deviation."""
        returns = [0.01, 0.02, 0.03, 0.01]

        result = calculate_sortino_ratio(returns, 0.0)

        assert result > 0

    def test_sortino_ratio_empty_returns(self):
        """Test Sortino ratio with empty returns."""
        returns = []

        result = calculate_sortino_ratio(returns, 0.0)

        assert result == 0.0


class TestCalmarRatio:
    """Tests for Calmar ratio calculation."""

    def test_calmar_ratio_basic(self):
        """Test basic Calmar ratio calculation."""
        returns = [0.01, 0.02, 0.015, 0.025, 0.03]
        max_drawdown = 0.10

        result = calculate_calmar_ratio(returns, max_drawdown)

        assert result is not None
        assert isinstance(result, float)

    def test_calmar_ratio_zero_drawdown(self):
        """Test Calmar ratio when max drawdown is zero."""
        returns = [0.01, 0.02, 0.015]
        max_drawdown = 0.0

        result = calculate_calmar_ratio(returns, max_drawdown)

        assert result == 0.0

    def test_calmar_ratio_negative_returns(self):
        """Test Calmar ratio with negative returns."""
        returns = [-0.01, -0.02, -0.015, -0.025]
        max_drawdown = 0.15

        result = calculate_calmar_ratio(returns, max_drawdown)

        assert result is not None

    def test_calmar_ratio_empty_returns(self):
        """Test Calmar ratio with empty returns."""
        returns = []
        max_drawdown = 0.10

        result = calculate_calmar_ratio(returns, max_drawdown)

        assert result == 0.0
