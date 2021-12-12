import asyncio
import logging
import signal
import typing
from concurrent.futures.thread import ThreadPoolExecutor

import config

loop = asyncio.get_event_loop()
loop.set_debug(config.DEBUG)
loop.set_default_executor(ThreadPoolExecutor(thread_name_prefix="AsyncioLoopDefaultExecutor"))


def exception_handler(exception_loop: asyncio.AbstractEventLoop, context):
    if "exception" in context and isinstance(context["exception"], asyncio.CancelledError):
        return
    exception_loop.default_exception_handler(context)


loop.set_exception_handler(exception_handler)

logging.basicConfig(format="%(asctime)s : %(levelname)8s : %(name)30s : %(funcName)-20s : %(lineno)4d : %(message)s")
logging.getLogger("transitions").setLevel(logging.INFO)

if config.DEBUG:
    logging.getLogger("bermudafunk").setLevel(logging.DEBUG)
    logging.getLogger("bermudafunk.symnet").setLevel(logging.ERROR)
    logging.getLogger("transitions").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

cleanup_event = asyncio.Event(loop=loop)
cleanup_tasks: typing.List[asyncio.Task] = []


def run_loop():
    logger.debug("Install signal handlers on loop")
    for sig_name in ("SIGINT", "SIGTERM", "SIGABRT"):
        loop.add_signal_handler(getattr(signal, sig_name), stop)

    try:
        logger.debug("Start loop forever")
        loop.run_forever()
    finally:
        logger.debug("Loop got stopped... running available cleanup tasks")
        if len(cleanup_tasks) > 0:
            loop.run_until_complete(asyncio.wait(cleanup_tasks))
        loop.stop()
        loop.close()
        logger.warning("End of looping!")


def stop():
    logger.debug("stopping the application, set cleanup event, stop loop")
    cleanup_event.set()
    loop.stop()


def start_cleanup_aware_coroutine(org_func):
    async def cleanup_task():
        await cleanup_event.wait()
        main_task.cancel()

    main_task = loop.create_task(org_func())
    cleanup_task = loop.create_task(cleanup_task())
    cleanup_tasks.append(cleanup_task)
