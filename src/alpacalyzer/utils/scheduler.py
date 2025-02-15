# Schedule analyze_and_swing_trade every 4 hours
import threading
import time

import schedule


def run_scheduler():
    """Run the scheduled tasks in an infinite loop."""
    while True:
        schedule.run_pending()
        time.sleep(1)  # Avoid high CPU usage


# Function to start the scheduler in a background thread
def start_scheduler():
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
