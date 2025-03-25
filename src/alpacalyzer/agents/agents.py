"""Constants and utilities related to analysts configuration."""

from typing import cast

from alpacalyzer.agents.technicals_agent import technical_analyst_agent

# Define analyst configuration - single source of truth
ANALYST_CONFIG = {
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "agent_func": technical_analyst_agent,
        "order": 0,
    },
}

# Derive ANALYST_ORDER from ANALYST_CONFIG for backwards compatibility
ANALYST_ORDER = [
    (config["display_name"], key)
    for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: cast(int, x[1]["order"]))
]


def get_analyst_nodes():
    """Get the mapping of analyst keys to their (node_name, agent_func) tuples."""
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}
