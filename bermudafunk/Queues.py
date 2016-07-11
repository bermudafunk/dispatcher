from asyncio import Queue
from .Base import logger, loop

queues = {}


def get_queue(name: str, *args, **kwargs) -> Queue:
    logger.debug('get_queue called %s', name)
    if name not in queues:
        logger.debug('get_queue create queue %s', name)
        queues[name] = Queue(loop=loop, *args, **kwargs)
    return queues[name]


def get_from_queue(name: str):
    logger.debug('get_from_queue called %s', name)
    return get_queue(name).get()


def put_in_queue(item, name: str):
    logger.debug('put_in_queue called %s %s', item, name)
    return get_queue(name).put(item)
