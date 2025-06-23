"""Constants and utilities related to analysts configuration."""

from typing import cast

from alpacalyzer.agents.ben_graham_agent import ben_graham_agent
from alpacalyzer.agents.bill_ackman_agent import bill_ackman_agent
from alpacalyzer.agents.cathie_wood_agent import cathie_wood_agent
from alpacalyzer.agents.charlie_munger import charlie_munger_agent
from alpacalyzer.agents.fundamentals_agent import fundamentals_agent
from alpacalyzer.agents.quant_agent import quant_agent
from alpacalyzer.agents.sentiment_agent import sentiment_agent
from alpacalyzer.agents.technicals_agent import technical_analyst_agent
from alpacalyzer.agents.warren_buffet_agent import warren_buffett_agent

# Define analyst configuration - single source of truth
ANALYST_CONFIG = {
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "agent_func": technical_analyst_agent,
        "order": 0,
    },
    "fundamental_analyst": {
        "display_name": "Fundamental Analyst",
        "agent_func": fundamentals_agent,
        "order": 1,
    },
    "sentiment_agent": {
        "display_name": "Sentiment Analyst",
        "agent_func": sentiment_agent,
        "order": 2,
    },
    "ben_graham": {
        "display_name": "Ben Graham",
        "agent_func": ben_graham_agent,
        "order": 3,
    },
    "bill_ackman": {
        "display_name": "Bill Ackman",
        "agent_func": bill_ackman_agent,
        "order": 4,
    },
    "cathie_wood": {
        "display_name": "Cathie Wood",
        "agent_func": cathie_wood_agent,
        "order": 5,
    },
    "charlie_munger": {
        "display_name": "Charlie Munger",
        "agent_func": charlie_munger_agent,
        "order": 6,
    },
    "warren_buffett": {
        "display_name": "Warren Buffett",
        "agent_func": warren_buffett_agent,
        "order": 7,
    },
    "quant_agent": {
        "display_name": "Quant Analyst",
        "agent_func": quant_agent,
        "order": 8,
    },
    # "web_agent": {
    #     "display_name": "Web Agent",
    #     "agent_func": web_agent,
    #     "order": 9,
    # },
}

# Derive ANALYST_ORDER from ANALYST_CONFIG for backwards compatibility
ANALYST_ORDER = [
    (config["display_name"], key)
    for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: cast(int, x[1]["order"]))
]


def get_analyst_nodes():
    """Get the mapping of analyst keys to their (node_name, agent_func) tuples."""
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}
