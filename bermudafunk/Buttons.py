import asyncio
from RPi import GPIO

from .Base import loop, logger

from . import Queues, Events

_initialized = None

buttons = {}
leds = {}


def setup():
    global _initialized
    if not isinstance(_initialized, asyncio.Task) or _initialized.cancelled():
        logger.debug('setup')
        logger.debug('setup GPIO.setmode')
        GPIO.setmode(GPIO.BOARD)
        logger.debug('setup create process_event loop task')
        _initialized = loop.create_task(process_event())
        logger.debug('setup create cleanup task')
        Events.cleanup_tasks.append(loop.create_task(cleanup()))


async def cleanup():
    logger.debug('cleanup awaiting')
    await Events.cleanup.wait()
    logger.debug('cleanup cancel process_event')
    _initialized.cancel()
    logger.debug('cleanup reset GPIO')
    GPIO.cleanup()


def register_button(pin, coroutine=None, override=False, **kwargs):
    global buttons
    setup()
    if not override and pin in buttons:
        logger.debug('register_button override not forced so do not override')
        return False
    logger.debug('register_button %s', pin)
    GPIO.setup(pin, GPIO.IN, **kwargs)
    GPIO.add_event_detect(pin, GPIO.RISING, callback=callback, bouncetime=300)
    buttons[str(pin)] = {'pin': pin, 'coroutine': coroutine}


async def process_event():
    global buttons
    while True:
        pin = await Queues.get_queue('gpio_raw').get()
        if pin in buttons and buttons[pin]['coroutine'] is not None:
            print('Create Task with coroutine defined')
            loop.call_soon(buttons[pin]['coroutine'])
        else:
            print('No callback coroutine defined')


def callback(pin):
    loop.call_soon_threadsafe(asyncio.ensure_future, Queues.put_in_queue(str(pin), 'gpio_raw'))
