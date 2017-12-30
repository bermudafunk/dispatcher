import logging

logger = logging.getLogger(__name__)

import asyncio
import os
import socket
from bermudafunk import Base



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

ready_event = asyncio.Event(loop=Base.loop)


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

    # SOCK_CLOEXEC was added in Python 3.2 and requires Linux >= 2.6.27.
    # It means "close this socket after fork/exec()
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC)
    except AttributeError:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    sock.connect(address)

    reader, writer = Base.loop.run_until_complete(asyncio.open_unix_connection(loop=Base.loop, sock=sock))

    """Return the time (in seconds) that we need to ping within."""
    val = os.environ.get("WATCHDOG_USEC", None)
    if not val:
        watchdog_sec = None
    else:
        watchdog_sec = int(val) / 1000000
        watchdog_task = Base.loop.create_task(watchdog())
        Base.cleanup_tasks.append(Base.loop.create_task(cleanup()))


async def watchdog():
    global ready_event, watchdog_sec
    await ready_event.wait()
    while True:
        await watchdog_ping()
        await asyncio.sleep(watchdog_sec * 0.9)


async def cleanup():
    global watchdog_task, reader, writer
    print('awaiting cleanup')
    await Base.cleanup.wait()
    print('Cleaning up start')
    watchdog_task.cancel()
    stop()
    sock.close()
    print('Cleaning up finished')


def sd_message(message):
    global writer
    if writer is None:
        async def empty():
            pass

        return asyncio.ensure_future(empty())
    """Send a message to the systemd bus/socket.
    message is expected to be bytes.
    """
    assert isinstance(message, bytes)
    writer.write(message)
    return asyncio.ensure_future(writer.drain())


def watchdog_ping():
    """Helper function to send a watchdog ping."""
    global sock, reader, writer, watchdog_sec
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
    global sock, reader, writer, watchdog_sec
    message = b"STOPPING=1"
    return sd_message(message)


def status(message):
    """Helper function to update the service status."""
    global sock, reader, writer, watchdog_sec
    message = ("STATUS=%s" % message).encode('utf8')
    return sd_message(message)
