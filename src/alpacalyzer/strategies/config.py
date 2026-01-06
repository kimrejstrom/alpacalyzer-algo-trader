"""
Strategy configuration dataclass.

This module defines StrategyConfig dataclass that holds all configurable
parameters for a trading strategy, enabling strategies to be customized
without code changes.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StrategyConfig:
    """
    Configuration dataclass for trading strategies.

    All parameters can be customized per-strategy, allowing for different
    risk profiles, entry/exit criteria, and timing rules.

    Default values match current behavior for backwards compatibility.

    Attributes:
        name: Strategy name for identification
        description: Human-readable strategy description
    """

    name: str = "default"
    description: str = "Default trading strategy configuration"

    max_position_pct: float = 0.05
    min_position_value: float = 100.0

    stop_loss_pct: float = 0.03
    target_pct: float = 0.09
    trailing_stop: bool = False
    trailing_stop_pct: float = 0.02
    max_loss_per_day: float = 0.02

    min_confidence: float = 70.0
    min_ta_score: float = 0.6
    min_momentum: float = -5.0
    min_rvol: float = 1.0
    entry_conditions_ratio: float = 0.7

    exit_momentum_threshold: float = -15.0
    exit_score_threshold: float = 0.3
    catastrophic_momentum: float = -25.0

    cooldown_hours: int = 3
    max_hold_days: int = 5

    price_tolerance_pct: float = 0.015

    candlestick_pattern_confidence: float = 80.0

    params: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """
        Validate config for logical consistency.

        Returns:
            List of validation error messages. Empty if config is valid.

        Raises:
            ValueError: If critical validation errors are found.
        """
        errors = []

        if not 0.0 < self.max_position_pct <= 1.0:
            errors.append("max_position_pct must be between 0 and 1")

        if self.min_position_value <= 0:
            errors.append("min_position_value must be positive")

        if not 0.0 < self.stop_loss_pct < 1.0:
            errors.append("stop_loss_pct must be between 0 and 1")

        if not 0.0 < self.target_pct < 1.0:
            errors.append("target_pct must be between 0 and 1")

        if self.trailing_stop and not (0.0 < self.trailing_stop_pct < 1.0):
            errors.append("trailing_stop_pct must be between 0 and 1 when trailing_stop is True")

        if not 0.0 < self.max_loss_per_day < 1.0:
            errors.append("max_loss_per_day must be between 0 and 1")

        if not 0.0 <= self.min_confidence <= 100.0:
            errors.append("min_confidence must be between 0 and 100")

        if not 0.0 <= self.min_ta_score <= 1.0:
            errors.append("min_ta_score must be between 0 and 1")

        if not 0.0 <= self.entry_conditions_ratio <= 1.0:
            errors.append("entry_conditions_ratio must be between 0 and 1")

        if not 0.0 <= self.exit_score_threshold <= 1.0:
            errors.append("exit_score_threshold must be between 0 and 1")

        if self.cooldown_hours < 0:
            errors.append("cooldown_hours must be non-negative")

        if self.max_hold_days <= 0:
            errors.append("max_hold_days must be positive")

        if not 0.0 <= self.price_tolerance_pct < 1.0:
            errors.append("price_tolerance_pct must be between 0 and 1")

        if not 0.0 <= self.candlestick_pattern_confidence <= 100.0:
            errors.append("candlestick_pattern_confidence must be between 0 and 100")

        if self.target_pct <= self.stop_loss_pct:
            errors.append(f"target_pct ({self.target_pct}) must be greater than stop_loss_pct ({self.stop_loss_pct})")

        if self.exit_score_threshold > self.min_ta_score:
            errors.append(f"exit_score_threshold ({self.exit_score_threshold}) should be less than or equal to min_ta_score ({self.min_ta_score})")

        if self.exit_momentum_threshold > self.min_momentum:
            errors.append(f"exit_momentum_threshold ({self.exit_momentum_threshold}) should be less than or equal to min_momentum ({self.min_momentum})")

        if self.catastrophic_momentum > self.exit_momentum_threshold:
            errors.append(f"catastrophic_momentum ({self.catastrophic_momentum}) should be less than or equal to exit_momentum_threshold ({self.exit_momentum_threshold})")

        if errors:
            raise ValueError("StrategyConfig validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

        return errors

    def to_yaml(self, path: str | Path) -> None:
        """
        Save configuration to a YAML file.

        Args:
            path: Path to save YAML file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        config_dict = {
            "name": self.name,
            "description": self.description,
            "position_sizing": {
                "max_position_pct": self.max_position_pct,
                "min_position_value": self.min_position_value,
            },
            "risk_management": {
                "stop_loss_pct": self.stop_loss_pct,
                "target_pct": self.target_pct,
                "trailing_stop": self.trailing_stop,
                "trailing_stop_pct": self.trailing_stop_pct,
                "max_loss_per_day": self.max_loss_per_day,
            },
            "entry_filters": {
                "min_confidence": self.min_confidence,
                "min_ta_score": self.min_ta_score,
                "min_momentum": self.min_momentum,
                "min_rvol": self.min_rvol,
                "entry_conditions_ratio": self.entry_conditions_ratio,
            },
            "exit_filters": {
                "exit_momentum_threshold": self.exit_momentum_threshold,
                "exit_score_threshold": self.exit_score_threshold,
                "catastrophic_momentum": self.catastrophic_momentum,
            },
            "timing": {
                "cooldown_hours": self.cooldown_hours,
                "max_hold_days": self.max_hold_days,
            },
            "price_tolerance_pct": self.price_tolerance_pct,
            "candlestick_pattern_confidence": self.candlestick_pattern_confidence,
            "params": self.params,
        }

        with open(path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "StrategyConfig":
        """
        Load configuration from a YAML file.

        Args:
            path: Path to YAML file

        Returns:
            StrategyConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            config_dict = yaml.safe_load(f)

        position_sizing = config_dict.pop("position_sizing", {})
        risk_management = config_dict.pop("risk_management", {})
        entry_filters = config_dict.pop("entry_filters", {})
        exit_filters = config_dict.pop("exit_filters", {})
        timing = config_dict.pop("timing", {})

        flat_config = config_dict.copy()
        flat_config.update(position_sizing)
        flat_config.update(risk_management)
        flat_config.update(entry_filters)
        flat_config.update(exit_filters)
        flat_config.update(timing)

        instance = cls(**flat_config)
        instance.validate()
        return instance
