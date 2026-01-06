"""Tests for StrategyConfig functionality."""

import tempfile
from pathlib import Path

import pytest

from alpacalyzer.strategies.config import StrategyConfig


def test_strategy_config_default_values():
    """Test StrategyConfig has correct default values."""
    config = StrategyConfig()

    assert config.name == "default"
    assert config.description == "Default trading strategy configuration"

    assert config.max_position_pct == 0.05
    assert config.min_position_value == 100.0

    assert config.stop_loss_pct == 0.03
    assert config.target_pct == 0.09
    assert config.trailing_stop is False
    assert config.trailing_stop_pct == 0.02
    assert config.max_loss_per_day == 0.02

    assert config.min_confidence == 70.0
    assert config.min_ta_score == 0.6
    assert config.min_momentum == -5.0
    assert config.min_rvol == 1.0
    assert config.entry_conditions_ratio == 0.7

    assert config.exit_momentum_threshold == -15.0
    assert config.exit_score_threshold == 0.3
    assert config.catastrophic_momentum == -25.0

    assert config.cooldown_hours == 3
    assert config.max_hold_days == 5

    assert config.price_tolerance_pct == 0.015
    assert config.candlestick_pattern_confidence == 80.0

    assert config.params == {}


def test_strategy_config_custom_values():
    """Test StrategyConfig accepts custom values."""
    config = StrategyConfig(
        name="custom_strategy",
        description="Custom momentum strategy",
        max_position_pct=0.10,
        stop_loss_pct=0.05,
        target_pct=0.15,
    )

    assert config.name == "custom_strategy"
    assert config.description == "Custom momentum strategy"
    assert config.max_position_pct == 0.10
    assert config.stop_loss_pct == 0.05
    assert config.target_pct == 0.15


def test_strategy_config_validate_success():
    """Test validate() succeeds with valid config."""
    config = StrategyConfig(
        max_position_pct=0.10,
        min_position_value=100.0,
        stop_loss_pct=0.03,
        target_pct=0.09,
        trailing_stop=True,
        trailing_stop_pct=0.02,
        max_loss_per_day=0.02,
    )

    errors = config.validate()
    assert errors == []


def test_strategy_config_validate_max_position_pct_invalid():
    """Test validate() fails with invalid max_position_pct."""
    config = StrategyConfig(max_position_pct=1.5)

    with pytest.raises(ValueError, match="max_position_pct must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_min_position_value_invalid():
    """Test validate() fails with negative min_position_value."""
    config = StrategyConfig(min_position_value=-50.0)

    with pytest.raises(ValueError, match="min_position_value must be positive"):
        config.validate()


def test_strategy_config_validate_stop_loss_pct_invalid():
    """Test validate() fails with invalid stop_loss_pct."""
    config = StrategyConfig(stop_loss_pct=1.5)

    with pytest.raises(ValueError, match="stop_loss_pct must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_target_pct_invalid():
    """Test validate() fails with invalid target_pct."""
    config = StrategyConfig(target_pct=0.0)

    with pytest.raises(ValueError, match="target_pct must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_trailing_stop_pct_invalid():
    """Test validate() fails with invalid trailing_stop_pct when trailing_stop is True."""
    config = StrategyConfig(trailing_stop=True, trailing_stop_pct=1.5)

    with pytest.raises(ValueError, match="trailing_stop_pct must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_max_loss_per_day_invalid():
    """Test validate() fails with invalid max_loss_per_day."""
    config = StrategyConfig(max_loss_per_day=1.5)

    with pytest.raises(ValueError, match="max_loss_per_day must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_min_confidence_invalid():
    """Test validate() fails with invalid min_confidence."""
    config = StrategyConfig(min_confidence=150.0)

    with pytest.raises(ValueError, match="min_confidence must be between 0 and 100"):
        config.validate()


def test_strategy_config_validate_min_ta_score_invalid():
    """Test validate() fails with invalid min_ta_score."""
    config = StrategyConfig(min_ta_score=1.5)

    with pytest.raises(ValueError, match="min_ta_score must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_entry_conditions_ratio_invalid():
    """Test validate() fails with invalid entry_conditions_ratio."""
    config = StrategyConfig(entry_conditions_ratio=1.5)

    with pytest.raises(ValueError, match="entry_conditions_ratio must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_exit_score_threshold_invalid():
    """Test validate() fails with invalid exit_score_threshold."""
    config = StrategyConfig(exit_score_threshold=1.5)

    with pytest.raises(ValueError, match="exit_score_threshold must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_cooldown_hours_invalid():
    """Test validate() fails with negative cooldown_hours."""
    config = StrategyConfig(cooldown_hours=-1)

    with pytest.raises(ValueError, match="cooldown_hours must be non-negative"):
        config.validate()


def test_strategy_config_validate_max_hold_days_invalid():
    """Test validate() fails with non-positive max_hold_days."""
    config = StrategyConfig(max_hold_days=0)

    with pytest.raises(ValueError, match="max_hold_days must be positive"):
        config.validate()


def test_strategy_config_validate_price_tolerance_pct_invalid():
    """Test validate() fails with invalid price_tolerance_pct."""
    config = StrategyConfig(price_tolerance_pct=1.5)

    with pytest.raises(ValueError, match="price_tolerance_pct must be between 0 and 1"):
        config.validate()


def test_strategy_config_validate_candlestick_pattern_confidence_invalid():
    """Test validate() fails with invalid candlestick_pattern_confidence."""
    config = StrategyConfig(candlestick_pattern_confidence=150.0)

    with pytest.raises(ValueError, match="candlestick_pattern_confidence must be between 0 and 100"):
        config.validate()


def test_strategy_config_validate_target_less_than_stop_loss():
    """Test validate() fails when target_pct <= stop_loss_pct."""
    config = StrategyConfig(stop_loss_pct=0.05, target_pct=0.03)

    with pytest.raises(ValueError, match="target_pct.*must be greater than stop_loss_pct"):
        config.validate()


def test_strategy_config_validate_exit_score_greater_than_min_ta():
    """Test validate() fails when exit_score_threshold > min_ta_score."""
    config = StrategyConfig(exit_score_threshold=0.7, min_ta_score=0.5)

    with pytest.raises(ValueError, match="exit_score_threshold.*should be less than or equal to min_ta_score"):
        config.validate()


def test_strategy_config_validate_exit_momentum_greater_than_min():
    """Test validate() fails when exit_momentum_threshold > min_momentum."""
    config = StrategyConfig(exit_momentum_threshold=-5.0, min_momentum=-10.0)

    with pytest.raises(ValueError, match="exit_momentum_threshold.*should be less than or equal to min_momentum"):
        config.validate()


def test_strategy_config_validate_catastrophic_greater_than_exit():
    """Test validate() fails when catastrophic_momentum > exit_momentum_threshold."""
    config = StrategyConfig(catastrophic_momentum=-10.0, exit_momentum_threshold=-15.0)

    with pytest.raises(ValueError, match="catastrophic_momentum.*should be less than or equal to exit_momentum_threshold"):
        config.validate()


def test_strategy_config_to_yaml():
    """Test to_yaml() saves configuration correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "strategy_config.yaml"

        config = StrategyConfig(
            name="test_strategy",
            description="Test description",
            max_position_pct=0.10,
            stop_loss_pct=0.05,
            target_pct=0.15,
        )

        config.to_yaml(config_path)

        assert config_path.exists()

        with open(config_path) as f:
            import yaml

            loaded_data = yaml.safe_load(f)

        assert loaded_data["name"] == "test_strategy"
        assert loaded_data["description"] == "Test description"
        assert loaded_data["position_sizing"]["max_position_pct"] == 0.10
        assert loaded_data["risk_management"]["stop_loss_pct"] == 0.05
        assert loaded_data["risk_management"]["target_pct"] == 0.15


def test_strategy_config_from_yaml():
    """Test from_yaml() loads configuration correctly."""
    yaml_content = """
name: test_strategy
description: Test description
position_sizing:
  max_position_pct: 0.10
  min_position_value: 200.0
risk_management:
  stop_loss_pct: 0.05
  target_pct: 0.15
  trailing_stop: true
  trailing_stop_pct: 0.03
  max_loss_per_day: 0.03
entry_filters:
  min_confidence: 80.0
  min_ta_score: 0.7
  min_momentum: 0.0
  min_rvol: 1.2
  entry_conditions_ratio: 0.8
exit_filters:
  exit_momentum_threshold: -10.0
  exit_score_threshold: 0.4
  catastrophic_momentum: -20.0
timing:
  cooldown_hours: 5
  max_hold_days: 7
price_tolerance_pct: 0.02
candlestick_pattern_confidence: 85.0
params:
  custom_param: value
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "strategy_config.yaml"

        with open(config_path, "w") as f:
            f.write(yaml_content)

        config = StrategyConfig.from_yaml(config_path)

        assert config.name == "test_strategy"
        assert config.description == "Test description"
        assert config.max_position_pct == 0.10
        assert config.min_position_value == 200.0
        assert config.stop_loss_pct == 0.05
        assert config.target_pct == 0.15
        assert config.trailing_stop is True
        assert config.trailing_stop_pct == 0.03
        assert config.max_loss_per_day == 0.03
        assert config.min_confidence == 80.0
        assert config.min_ta_score == 0.7
        assert config.min_momentum == 0.0
        assert config.min_rvol == 1.2
        assert config.entry_conditions_ratio == 0.8
        assert config.exit_momentum_threshold == -10.0
        assert config.exit_score_threshold == 0.4
        assert config.catastrophic_momentum == -20.0
        assert config.cooldown_hours == 5
        assert config.max_hold_days == 7
        assert config.price_tolerance_pct == 0.02
        assert config.candlestick_pattern_confidence == 85.0
        assert config.params == {"custom_param": "value"}


def test_strategy_config_from_yaml_file_not_found():
    """Test from_yaml() raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        StrategyConfig.from_yaml("/nonexistent/path/config.yaml")


def test_strategy_config_yaml_roundtrip():
    """Test roundtrip: to_yaml -> from_yaml preserves all values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "strategy_config.yaml"

        original_config = StrategyConfig(
            name="roundtrip_test",
            description="Test roundtrip",
            max_position_pct=0.08,
            stop_loss_pct=0.04,
            target_pct=0.12,
            min_confidence=75.0,
            params={"key1": "value1", "key2": 42},
        )

        original_config.to_yaml(config_path)
        loaded_config = StrategyConfig.from_yaml(config_path)

        assert loaded_config.name == original_config.name
        assert loaded_config.description == original_config.description
        assert loaded_config.max_position_pct == original_config.max_position_pct
        assert loaded_config.stop_loss_pct == original_config.stop_loss_pct
        assert loaded_config.target_pct == original_config.target_pct
        assert loaded_config.min_confidence == original_config.min_confidence
        assert loaded_config.params == original_config.params


def test_strategy_config_default_values_match_trader_hardcoded_values():
    """Test default values match hardcoded values from trader.py."""
    config = StrategyConfig()

    assert config.entry_conditions_ratio == 0.7
    assert config.price_tolerance_pct == 0.015
    assert config.candlestick_pattern_confidence == 80.0
    assert config.exit_momentum_threshold == -15.0
    assert config.exit_score_threshold == 0.3
    assert config.cooldown_hours == 3
    assert config.catastrophic_momentum == -25.0


def test_strategy_config_from_yaml_invalid_target_less_than_stop():
    """Test from_yaml() raises when target_pct <= stop_loss_pct."""
    yaml_content = """
name: test_strategy
description: Test description
position_sizing:
  max_position_pct: 0.10
  min_position_value: 200.0
risk_management:
  stop_loss_pct: 0.05
  target_pct: 0.03
entry_filters:
  min_confidence: 80.0
  min_ta_score: 0.7
  min_momentum: 0.0
  min_rvol: 1.2
  entry_conditions_ratio: 0.8
exit_filters:
  exit_momentum_threshold: -10.0
  exit_score_threshold: 0.4
  catastrophic_momentum: -20.0
timing:
  cooldown_hours: 5
  max_hold_days: 7
price_tolerance_pct: 0.02
candlestick_pattern_confidence: 85.0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "strategy_config.yaml"

        with open(config_path, "w") as f:
            f.write(yaml_content)

        with pytest.raises(ValueError, match="target_pct.*must be greater than stop_loss_pct"):
            StrategyConfig.from_yaml(config_path)


def test_strategy_config_from_yaml_invalid_max_position_pct():
    """Test from_yaml() raises when max_position_pct > 1."""
    yaml_content = """
name: test_strategy
description: Test description
position_sizing:
  max_position_pct: 1.5
  min_position_value: 200.0
risk_management:
  stop_loss_pct: 0.05
  target_pct: 0.15
entry_filters:
  min_confidence: 80.0
  min_ta_score: 0.7
  min_momentum: 0.0
  min_rvol: 1.2
  entry_conditions_ratio: 0.8
exit_filters:
  exit_momentum_threshold: -10.0
  exit_score_threshold: 0.4
  catastrophic_momentum: -20.0
timing:
  cooldown_hours: 5
  max_hold_days: 7
price_tolerance_pct: 0.02
candlestick_pattern_confidence: 85.0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "strategy_config.yaml"

        with open(config_path, "w") as f:
            f.write(yaml_content)

        with pytest.raises(ValueError, match="max_position_pct must be between 0 and 1"):
            StrategyConfig.from_yaml(config_path)


def test_strategy_config_yaml_preserves_default_params_when_omitted():
    """Test from_yaml() preserves default empty params dict when section is omitted."""
    yaml_content = """
name: test_strategy
description: Test description
position_sizing:
  max_position_pct: 0.10
  min_position_value: 200.0
risk_management:
  stop_loss_pct: 0.05
  target_pct: 0.15
entry_filters:
  min_confidence: 80.0
  min_ta_score: 0.7
  min_momentum: 0.0
  min_rvol: 1.2
  entry_conditions_ratio: 0.8
exit_filters:
  exit_momentum_threshold: -10.0
  exit_score_threshold: 0.4
  catastrophic_momentum: -20.0
timing:
  cooldown_hours: 5
  max_hold_days: 7
price_tolerance_pct: 0.02
candlestick_pattern_confidence: 85.0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "strategy_config.yaml"

        with open(config_path, "w") as f:
            f.write(yaml_content)

        config = StrategyConfig.from_yaml(config_path)

        assert config.params == {}
        assert isinstance(config.params, dict)
