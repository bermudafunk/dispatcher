import asyncio
import logging
import signal

import config

loop = asyncio.get_event_loop()
loop.set_debug(config.DEBUG)

if config.DEBUG:
    logging.basicConfig(format='%(asctime)s : %(levelname)8s : %(name)20s : %(funcName)20s : %(lineno)4d : %(message)s')
    logging.getLogger('bermudafunk').setLevel(logging.DEBUG)
    logging.getLogger('bermudafunk.Symnet').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

cleanup = asyncio.Event(loop=loop)
cleanup_tasks = []


def run_loop():
    global loop

    logger.debug("Install signal handlers on loop")
    for sig_name in ('SIGINT', 'SIGTERM', 'SIGABRT'):
        loop.add_signal_handler(getattr(signal, sig_name), stop)

    logger.debug("Setup systemd notification")
    from bermudafunk import Systemd
    Systemd.ready()

    try:
        logger.debug("Start loop forever")
        loop.run_forever()
    finally:
        logger.debug("Loop got stopped... running available cleanup tasks")
        if len(cleanup_tasks) > 0:
            loop.run_until_complete(asyncio.wait(cleanup_tasks))
        loop.stop()
        loop.close()


def stop():
    logger.debug("stopping the application, set cleanup event, stop loop")
    cleanup.set()
    loop.stop()
