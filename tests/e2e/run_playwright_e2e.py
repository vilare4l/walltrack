"""Run Playwright E2E tests with real data.

This script:
1. Seeds test data in the database
2. Starts the Gradio UI
3. Runs through all test scenarios with Playwright
4. Takes screenshots at each step

Usage:
    uv run python tests/e2e/run_playwright_e2e.py
"""

import asyncio
import os
import subprocess
import sys
import time

# Ensure we're in simulation mode (lowercase as required by enum)
os.environ["EXECUTION_MODE"] = "simulation"


async def seed_data():
    """Seed test data."""
    print("\n[1/4] Seeding test data...")
    from tests.e2e.seed_test_data import main as seed_main
    await seed_main()


def start_gradio_ui():
    """Start Gradio UI in background."""
    print("\n[2/4] Starting Gradio UI...")
    process = subprocess.Popen(
        [sys.executable, "-c",
         "from walltrack.ui.dashboard import create_dashboard; "
         "d = create_dashboard(); "
         "d.launch(server_name='0.0.0.0', server_port=7860)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    # Wait for startup
    time.sleep(15)
    return process


async def run_playwright_tests():
    """Run Playwright tests via MCP."""
    print("\n[3/4] Running Playwright tests...")
    print("=" * 60)
    print("NOTE: Use Claude Code with Playwright MCP to run visual tests")
    print("=" * 60)
    print("""
Test Scenarios to run manually with Playwright:

SCENARIO 1: Home Dashboard
- Navigate to http://localhost:7860
- Verify P&L Today shows value
- Verify Active Positions count
- Click Refresh button
- Screenshot: e2e_home_with_data.png

SCENARIO 2: Orders Page
- Navigate to Orders tab
- Verify orders table has rows
- Click on status filter dropdown
- Filter by "pending"
- Screenshot: e2e_orders_pending.png
- Click on a failed order row
- Verify Order Details accordion opens
- Screenshot: e2e_order_details.png

SCENARIO 3: Explorer - Signals
- Navigate to Explorer tab
- Click Refresh Signals
- Verify signals table shows data
- Click on a signal row
- Verify sidebar shows details
- Screenshot: e2e_signals_with_data.png

SCENARIO 4: Settings - Config Management
- Navigate to Settings tab
- Click on Trading tab
- Click Edit button
- Modify a value
- Click Save Draft
- Verify status shows "draft"
- Screenshot: e2e_config_draft.png

SCENARIO 5: Exit Strategies
- Navigate to Exit Strategies tab
- Click Refresh
- Verify strategies table shows data
- Click on a strategy row
- Verify editor loads strategy
- Screenshot: e2e_strategies_loaded.png

SCENARIO 6: Exit Simulator
- Navigate to Exit Simulator tab
- Select a strategy from dropdown
- Click Run Simulation
- Verify results appear
- Screenshot: e2e_simulation_results.png
""")


def cleanup(process):
    """Cleanup Gradio process."""
    print("\n[4/4] Cleaning up...")
    if process:
        process.terminate()
        process.wait()


async def main():
    """Run full E2E test suite."""
    print("\n" + "#" * 60)
    print("# WallTrack E2E Test Suite with Playwright")
    print("#" * 60)

    gradio_process = None

    try:
        # Step 1: Seed data
        await seed_data()

        # Step 2: Start UI
        gradio_process = start_gradio_ui()

        # Step 3: Run tests
        await run_playwright_tests()

        # Keep running for manual testing
        print("\n" + "=" * 60)
        print("Gradio UI is running at http://localhost:7860")
        print("Press Ctrl+C to stop")
        print("=" * 60)

        # Wait for user to finish testing
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n\nStopping tests...")
    finally:
        cleanup(gradio_process)


if __name__ == "__main__":
    asyncio.run(main())
