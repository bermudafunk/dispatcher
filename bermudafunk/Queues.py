import logging

logger = logging.getLogger(__name__)

from asyncio import Queue
from .Base import loop

queues = {}


def get_queue(name: str, *args, **kwargs) -> Queue:
    logger.debug('get_queue called on queue <%s>', name)
    if name not in queues:
        logger.debug('get_queue create queue <%s>', name)
        queues[name] = Queue(loop=loop, *args, **kwargs)
    return queues[name]


def get_from_queue(name: str):
    logger.debug('get_from_queue called queue <%s>', name)
    return get_queue(name).get()


def put_in_queue(item, name: str):
    logger.debug('put_in_queue called item <%s> into queue <%s>', item, name)
    return get_queue(name).put(item)
