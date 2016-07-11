import asyncio
import logging

import config

loop = asyncio.get_event_loop()
loop.set_debug(config.DEBUG)

if config.DEBUG:
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger('umschalter')
