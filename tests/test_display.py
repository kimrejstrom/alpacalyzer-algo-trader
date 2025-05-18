from unittest.mock import patch

import pytest

from alpacalyzer.utils.display import print_trading_output


@pytest.fixture
def sample_result():
    return {
        "decisions": {
            "PLTR": {
                "strategies": [
                    {
                        "ticker": "PLTR",
                        "quantity": 271,
                        "entry_point": 129.35,
                        "stop_loss": 130.64,
                        "target_price": 125.45,
                        "risk_reward_ratio": 3.0,
                        "strategy_notes": "Given the predominantly bearish signals from major investors.",
                        "trade_type": "short",
                        "entry_criteria": [{"entry_type": "breakdown_below", "value": 129.35}],
                    }
                ]
            },
            "KULR": {
                "strategies": [
                    {
                        "ticker": "KULR",
                        "quantity": 3388,
                        "entry_point": 1.33,
                        "stop_loss": 1.37,
                        "target_price": 1.21,
                        "risk_reward_ratio": 3.0,
                        "strategy_notes": "The overall technical picture for KULR is bearish.",
                        "trade_type": "short",
                        "entry_criteria": [{"entry_type": "price_near_resistance", "value": 1.37}],
                    }
                ]
            },
        },
        "analyst_signals": {
            "potential_candidates_agent": {
                "PLTR": {"signal": "neutral", "confidence": 50.0},
                "KULR": {"signal": "neutral", "confidence": 50.0},
            },
            "technical_analyst_agent": {
                "PLTR": {
                    "signal": "neutral",
                    "confidence": 18,
                    "reasoning": "Trend signal: bullish\nMean reversion signal: neutral\nMomentum signal: neutral",
                    "strategy_signals": {
                        "trend_following": {
                            "signal": "bullish",
                            "confidence": 33,
                            "metrics": {"adx": 33.204231601362366, "trend_strength": 0.33204231601362366},
                        },
                        "mean_reversion": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {
                                "z_score": 1.8139776630984512,
                                "price_vs_bb": 0.7887311842570299,
                                "rsi_14": 61.89719130895601,
                                "rsi_28": 71.17587601078165,
                            },
                        },
                        "momentum": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {
                                "momentum_1m": 0.34793780943167096,
                                "momentum_3m": 0.17455695374508196,
                                "momentum_6m": "",
                                "volume_momentum": 0.6661815938239085,
                            },
                        },
                        "volatility": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {
                                "historical_volatility": 0.7380479413749444,
                                "volatility_regime": "",
                                "volatility_z_score": "",
                                "atr_ratio": 0.055143838365817766,
                            },
                        },
                        "statistical_arbitrage": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {
                                "hurst_exponent": 4.4162737839765496e-15,
                                "skewness": 0.0830746984891419,
                                "kurtosis": 0.9470196525563437,
                            },
                        },
                    },
                },
                "KULR": {
                    "signal": "neutral",
                    "confidence": 0,
                    "reasoning": "Trend signal: neutral\nMean reversion signal: neutral\nMomentum signal: neutral",
                    "strategy_signals": {
                        "trend_following": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {"adx": 38.020629932660775, "trend_strength": 0.38020629932660777},
                        },
                        "mean_reversion": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {
                                "z_score": 0.7348428925332574,
                                "price_vs_bb": 0.7689398693568122,
                                "rsi_14": 57.333333333333314,
                                "rsi_28": 59.47712418300654,
                            },
                        },
                        "momentum": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {
                                "momentum_1m": 0.17239361006660514,
                                "momentum_3m": -0.21696079343374952,
                                "momentum_6m": "",
                                "volume_momentum": 2.432625673126647,
                            },
                        },
                        "volatility": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {
                                "historical_volatility": 0.8236812278375306,
                                "volatility_regime": "",
                                "volatility_z_score": "",
                                "atr_ratio": 0.06944498069498073,
                            },
                        },
                        "statistical_arbitrage": {
                            "signal": "neutral",
                            "confidence": 50,
                            "metrics": {
                                "hurst_exponent": 4.4162737839765496e-15,
                                "skewness": 0.5520744931577525,
                                "kurtosis": 0.7610895258892189,
                            },
                        },
                    },
                },
            },
            "cathie_wood_agent": {
                "PLTR": {
                    "signal": "bearish",
                    "confidence": 30.0,
                    "reasoning": "While PLTR's heavy investment in R&D (17.7% of revenue) hints at a potential.",
                },
                "KULR": {
                    "signal": "bearish",
                    "confidence": 80.0,
                    "reasoning": "KULR demonstrates a high R&D investment of 44.1% of revenue.",
                },
            },
            "bill_ackman_agent": {
                "PLTR": {
                    "signal": "bearish",
                    "confidence": 80.0,
                    "reasoning": "PLTR's numbers do not inspire confidence when measured by the high standards.",
                },
                "KULR": {
                    "signal": "bearish",
                    "confidence": 90.0,
                    "reasoning": "KULR presents significant financial and operational weaknesses.",
                },
            },
            "warren_buffett_agent": {
                "PLTR": {
                    "signal": "bearish",
                    "confidence": 20.0,
                    "reasoning": "The available data for PLTR does not meet Warren Buffett’s criteria.",
                },
                "KULR": {
                    "signal": "bearish",
                    "confidence": 95.0,
                    "reasoning": "The analysis of KULR reveals multiple red flags from a Buffett perspective.",
                },
            },
            "ben_graham_agent": {
                "PLTR": {
                    "signal": "bearish",
                    "confidence": 90.0,
                    "reasoning": "The available data for PLTR falls short on several key Benjamin Graham criteria.",
                },
                "KULR": {
                    "signal": "bearish",
                    "confidence": 85.0,
                    "reasoning": "Despite a promising low debt ratio of 0.09, which is well under Graham's threshold.",
                },
            },
            "sentiment_agent": {
                "PLTR": {
                    "signal": "bearish",
                    "confidence": 100.0,
                    "reasoning": "Weighted Bullish signals: 0.0, Weighted Bearish signals: 1.0",
                },
                "KULR": {
                    "signal": "bullish",
                    "confidence": 63.0,
                    "reasoning": "Weighted Bullish signals: 2.4, Weighted Bearish signals: 0.7",
                },
            },
            "risk_management_agent": {
                "PLTR": {
                    "remaining_position_limit": 35217.0095,
                    "current_price": 129.6349,
                    "reasoning": {
                        "portfolio_value": 89463.79,
                        "current_position": -30743.82,
                        "position_limit": 4473.1894999999995,
                        "remaining_limit": 35217.0095,
                        "available_cash": 87075.08,
                    },
                },
                "KULR": {
                    "remaining_position_limit": 4473.1894999999995,
                    "current_price": 1.32,
                    "reasoning": {
                        "portfolio_value": 89463.79,
                        "current_position": 0.0,
                        "position_limit": 4473.1894999999995,
                        "remaining_limit": 4473.1894999999995,
                        "available_cash": 87075.08,
                    },
                },
            },
            "portfolio_management_agent": {
                "PLTR": {
                    "ticker": "PLTR",
                    "action": "short",
                    "quantity": 271,
                    "confidence": 64.0,
                    "reasoning": "The majority of signals for PLTR are bearish.",
                },
                "KULR": {
                    "ticker": "KULR",
                    "action": "short",
                    "quantity": 3388,
                    "confidence": 87.5,
                    "reasoning": "For KULR, although there is one bullish signal from the sentiment agent.",
                },
            },
        },
    }


@patch("alpacalyzer.utils.display.print")
@patch("alpacalyzer.utils.display.tabulate")
def test_print_trading_output_with_valid_data(mock_tabulate, mock_print, sample_result):
    """Test print_trading_output with valid data containing decisions and signals."""
    mock_tabulate.return_value = "mocked_table"

    print_trading_output(sample_result)

    # Verify print was called with expected outputs
    assert mock_print.call_count > 5  # Multiple print calls are expected

    # Check for specific headers being printed
    expected_headers = [
        "ANALYSIS FOR",
        "AGENT ANALYSIS:",
        "TRADING DECISION:",
        "PORTFOLIO SUMMARY:",
        "TRADING STRATEGY:",
    ]

    # Create a list of all calls and their arguments to check
    print_calls = [call_args[0][0] for call_args in mock_print.call_args_list if call_args[0]]
    print(print_calls)
    # Check for each expected header in any of the print calls
    for header in expected_headers:
        header_found = any(header.upper() in str(call).upper() for call in print_calls)
        assert header_found, f"Expected header '{header}' not found in printed output"

    # Verify tabulate was called for various tables
    assert mock_tabulate.call_count >= 3  # Called for agent analysis, trading decision, and portfolio summary tables


@patch("alpacalyzer.utils.display.print")
@patch("alpacalyzer.utils.display.tabulate")
@patch("alpacalyzer.utils.display.logger")
def test_print_trading_output_with_strategy_display(mock_logger, mock_tabulate, mock_print, sample_result):
    """Test that the trading strategies are properly displayed."""
    mock_tabulate.return_value = "mocked_table"

    print_trading_output(sample_result)

    # Check that trading strategy headers are passed to tabulate
    strategy_headers_call_found = False
    for call in mock_tabulate.call_args_list:
        if "headers" in call[1]:
            headers = call[1]["headers"]
            if (
                any("TICKER" in str(h).upper() for h in headers)
                and any("TRADE TYPE" in str(h).upper() for h in headers)
                and any("RISK/REWARD RATIO" in str(h).upper() for h in headers)
            ):
                strategy_headers_call_found = True
                break

    assert strategy_headers_call_found, "Trading strategy headers not found in tabulate calls"

    # Make sure the TRADING STRATEGY header was printed
    strategy_header_printed = False
    for call_args in mock_print.call_args_list:
        if call_args[0] and "TRADING STRATEGY" in str(call_args[0][0]).upper():
            strategy_header_printed = True
            break

    assert strategy_header_printed, "Trading strategy section header not printed"
