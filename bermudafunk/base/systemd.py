import asyncio
import logging
import os
import socket

from bermudafunk import base

logger = logging.getLogger(__name__)

"""
This is based on the work of "D.S. Ljungmark, Modio AB", published under the GPLv3,
on https://gist.github.com/Spindel/1d07533ef94a4589d348

Thanks a lot.
"""

sock = None
reader = None
writer = None
watchdog_sec = None
watchdog_task = None

ready_event = asyncio.Event(loop=base.loop)


def setup(clean_environment=True):
    """Return a tuple of address, socket for future use.
    clean_environment removes the variables from env to prevent children
    from inheriting it and doing something wrong.
    """
    global sock, reader, writer, watchdog_sec, watchdog_task
    if clean_environment:
        address = os.environ.pop("NOTIFY_SOCKET", None)
    else:
        address = os.environ.get("NOTIFY_SOCKET", None)

    if not address or len(address) == 1 or address[0] not in ("@", "/"):
        raise RuntimeError('No suitable address found.')

    if address[0] == "@":
        address = "\0" + address[1:]

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC)

    sock.connect(address)

    reader, writer = base.loop.run_until_complete(asyncio.open_unix_connection(loop=base.loop, sock=sock))

    """Return the time (in seconds) that we need to ping within."""
    val = os.environ.get("WATCHDOG_USEC", None)
    if not val:
        watchdog_sec = None
    else:
        watchdog_sec = int(val) / 1000000
        watchdog_task = base.loop.create_task(watchdog())
        base.cleanup_tasks.append(base.loop.create_task(cleanup()))


async def watchdog():
    global ready_event, watchdog_sec
    await ready_event.wait()
    while True:
        await watchdog_ping()
        await asyncio.sleep(watchdog_sec * 0.9, loop=base.loop)


async def cleanup():
    global watchdog_task, sock
    logger.info('awaiting cleanup')
    await base.cleanup_event.wait()
    logger.info('Cleaning up start')
    watchdog_task.cancel()
    stop()
    sock.close()
    logger.info('Cleaning up finished')


def sd_message(message: bytes):
    global writer
    if writer is None:
        async def empty():
            pass

        return asyncio.ensure_future(empty(), loop=base.loop)
    assert isinstance(message, bytes)
    writer.write(message)
    return asyncio.ensure_future(writer.drain(), loop=base.loop)


def watchdog_ping():
    """Helper function to send a watchdog ping."""
    message = b"WATCHDOG=1"
    return sd_message(message)


def ready():
    """Helper function to send a ready signal."""
    global ready_event
    message = b"READY=1"
    logger.debug("Signaling system ready")
    result = sd_message(message)
    ready_event.set()
    return result


def stop():
    """Helper function to signal service stopping."""
    message = b"STOPPING=1"
    return sd_message(message)


def status(message):
    """Helper function to update the service status."""
    message = ("STATUS=%s" % message).encode('utf8')
    return sd_message(message)
