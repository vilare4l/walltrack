"""APScheduler job definitions.

Main entry point for the background worker that runs scheduled tasks.
"""

import asyncio
import signal
import sys

import structlog

from walltrack.scheduler.discovery_scheduler import get_discovery_scheduler

log = structlog.get_logger()


async def main() -> None:
    """Main entry point for the scheduler worker."""
    log.info("scheduler_worker_starting")

    scheduler = await get_discovery_scheduler()

    # Handle shutdown signals
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def handle_signal() -> None:
        log.info("shutdown_signal_received")
        shutdown_event.set()

    # Register signal handlers (Unix only)
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, handle_signal)

    try:
        # Start the scheduler
        await scheduler.start()

        # Wait for shutdown signal
        if sys.platform == "win32":
            # On Windows, just run forever (Ctrl+C will raise KeyboardInterrupt)
            while True:
                await asyncio.sleep(60)
        else:
            await shutdown_event.wait()

    except KeyboardInterrupt:
        log.info("keyboard_interrupt_received")
    finally:
        # Stop the scheduler gracefully
        await scheduler.stop()
        log.info("scheduler_worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
