import asyncio
import logging
import signal

import config

loop = asyncio.get_event_loop()
loop.set_debug(config.DEBUG)

if config.DEBUG:
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger('umschalter')

cleanup = asyncio.Event(loop=loop)
cleanup_tasks = []


def run_loop():
    global loop

    for sig_name in ('SIGINT', 'SIGTERM', 'SIGABRT'):
        loop.add_signal_handler(getattr(signal, sig_name), stop)

    try:
        loop.run_forever()
    finally:
        if len(cleanup_tasks) > 0:
            loop.run_until_complete(asyncio.wait(cleanup_tasks))
        loop.stop()
        loop.close()


def stop():
    cleanup.set()
    loop.stop()
