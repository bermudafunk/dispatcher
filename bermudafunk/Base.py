import asyncio
import logging

import config

loop = asyncio.get_event_loop()
loop.set_debug(config.DEBUG)

if config.DEBUG:
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger('umschalter')

cleanup = asyncio.Event()
cleanup_tasks = []


def run_loop():
    global loop
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    cleanup.set()
    loop.run_until_complete(asyncio.wait(cleanup_tasks))

    loop.stop()
