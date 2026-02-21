from rich.console import Console
from rich.live import Live
from rich.style import Style
from rich.table import Table
from rich.text import Text

console = Console()


class AgentProgress:
    """Manages progress tracking for multiple agents."""

    def __init__(self):
        self.agent_status: dict[str, dict[str, str]] = {}
        self.live = Live(Table(), console=console, refresh_per_second=4)
        self.started = False

    def start(self):
        """Start the progress display."""
        if not self.started:
            self.agent_status.clear()
            self.live.start()
            self.started = True

    def stop(self):
        """Stop the progress display."""
        if self.started:
            self.live.stop()
            self.started = False
            console.print()  # ensure clean newline after spinner output

    def add_reasoning(self, agent_name: str, ticker: str, signal: str, confidence, reasoning_snippet: str):
        """
        Print a reasoning summary line above the Live display.

        Uses Live.console.print() which correctly inserts the line above
        the live-updating status table without getting overwritten.
        """
        line = Text()
        signal_lower = signal.lower()
        if signal_lower == "bearish":
            sig_style = Style(color="red")
        elif signal_lower == "bullish":
            sig_style = Style(color="green")
        else:
            sig_style = Style(color="yellow")

        line.append(f"[{agent_name}] ", style=Style(color="white", dim=True))
        line.append(f"{ticker} ", style=Style(color="cyan"))
        line.append(f"{signal} ", style=sig_style)
        line.append(f"({confidence}%) ", style=Style(color="white", dim=True))
        if reasoning_snippet:
            line.append(reasoning_snippet[:100], style=Style(color="white", dim=True))

        if self.started:
            self.live.console.print(line)
        else:
            console.print(line)

    def update_status(self, agent_name: str, ticker: str | None = None, status: str = ""):
        """Update the status of an agent."""
        if agent_name not in self.agent_status:
            self.agent_status[agent_name] = {"status": "", "ticker": ""}

        if ticker:
            self.agent_status[agent_name]["ticker"] = ticker
        if status:
            self.agent_status[agent_name]["status"] = status

        self._refresh_display()

    def _refresh_display(self):
        """Refresh the progress display."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(width=100)

        # Sort agents with Risk Management and Portfolio Management at the bottom
        def sort_key(item):
            agent_name = item[0]
            if "risk_management" in agent_name:
                return (2, agent_name)
            if "portfolio_management" in agent_name:
                return (3, agent_name)
            if "trading_strategist" in agent_name:
                return (4, agent_name)
            return (1, agent_name)

        for agent_name, info in sorted(self.agent_status.items(), key=sort_key):
            status = info["status"]
            ticker = info["ticker"]

            # Create the status text with appropriate styling
            if status.lower() == "done":
                style = Style(color="green", bold=True)
                symbol = "✓"
            elif status.lower() == "error":
                style = Style(color="red", bold=True)
                symbol = "✗"
            else:
                style = Style(color="yellow")
                symbol = "⋯"

            agent_display = agent_name.replace("_agent", "").replace("_", " ").title()
            status_text = Text()
            status_text.append(f"{symbol} ", style=style)
            status_text.append(f"{agent_display:<20}", style=Style(bold=True))

            if ticker:
                status_text.append(f"[{ticker}] ", style=Style(color="cyan"))
            status_text.append(status, style=style)

            table.add_row(status_text)

        table.add_row("")
        self.live.update(table)


# Create a global instance
progress = AgentProgress()
