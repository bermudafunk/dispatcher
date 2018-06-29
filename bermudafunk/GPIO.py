import asyncio
import enum
import logging

from RPi import GPIO

from bermudafunk import base
from bermudafunk.base import loop

logger = logging.getLogger(__name__)

_initialized = None

_buttons = {}
_leds = {}

_used_pins = {}

_pin_events = asyncio.Queue(loop=base.loop)


class LedState(enum.Enum):
    OFF = 'off'
    ON = 'on'
    BLINK = 'blink'


class Led:
    def __init__(self, pin):
        global _leds
        _leds[str(pin)] = self

        self.pin = int(pin)
        self.state = LedState.OFF
        self.blink_freq = 2

        self._blink_task = None

        _setup()
        _check_pin(self.pin, 'led')
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

    def __del__(self):
        if self._blink_task is not None:
            self._blink_task.cancel()
        GPIO.output(self.pin, GPIO.LOW)

    def get_state(self):
        return self.state

    def set_state(self, new_state: LedState, force=False, blink_freq=2):
        self.blink_freq = blink_freq

        if self.state == new_state and not force:
            return  # Same state, nothing to change

        self.state = new_state

        if self._blink_task is not None:
            self._blink_task.cancel()
            self._blink_task = None

        if new_state is LedState.ON:
            GPIO.output(self.pin, GPIO.HIGH)
        elif new_state is LedState.OFF:
            GPIO.output(self.pin, GPIO.LOW)
        elif new_state is LedState.BLINK:
            self._blink_task = loop.create_task(self._blink())

    async def _blink(self):
        while True:
            GPIO.output(self.pin, GPIO.HIGH)
            await asyncio.sleep(1 / self.blink_freq)
            GPIO.output(self.pin, GPIO.LOW)
            await asyncio.sleep(1 / self.blink_freq)


def _setup():
    global _initialized
    if not isinstance(_initialized, asyncio.Task) or _initialized.cancelled():
        logger.debug('setup')
        logger.debug('setup GPIO.setmode')
        GPIO.setmode(GPIO.BOARD)
        logger.debug('setup create process_event loop task')
        _initialized = loop.create_task(_process_event())
        logger.debug('setup create cleanup task')
        base.cleanup_tasks.append(loop.create_task(_cleanup()))


def _check_pin(pin, usage):
    global _used_pins
    pin = int(pin)
    if pin not in _used_pins:
        _used_pins[pin] = usage
    if pin in _used_pins and _used_pins[pin] == usage:
        return True
    raise Exception('pin %s already used as %s instead of %s' % (pin, _used_pins[pin], usage))


async def _cleanup():
    logger.debug('cleanup awaiting')
    await base.cleanup_event.wait()
    logger.debug('cleanup cancel process_event')
    _initialized.cancel()
    logger.debug('cleanup reset GPIO')
    GPIO.cleanup()


def register_button(pin, callback=None, coroutine=None, override=False, **kwargs):
    global _buttons
    _setup()
    pin = int(pin)
    if not override and pin in _buttons:
        logger.debug('register_button override not forced so do not override')
        return False
    logger.debug('register_button %s', pin)
    _check_pin(pin, 'button')
    GPIO.setup(pin, GPIO.IN, **kwargs)
    GPIO.add_event_detect(pin, GPIO.RISING, callback=_callback, bouncetime=300)
    _buttons[str(pin)] = {'pin': pin, 'callback': callback, 'coroutine': coroutine}


def remove_button(pin):
    global _buttons
    GPIO.remove_event_detect(pin)
    del _buttons[str(pin)]


async def _process_event():
    global _buttons
    while True:
        pin = await _pin_events.get()
        something_executed = False
        if pin in _buttons:
            if _buttons[pin]['callback'] is not None:
                logger.debug('callback will be called soon')
                loop.call_soon(_buttons[pin]['callback'], int(pin))
                something_executed = True
            if _buttons[pin]['coroutine'] is not None:
                logger.debug('coroutine scheduled as a task')
                loop.create_task(_buttons[pin]['coroutine'](int(pin)))
                something_executed = True
        if not something_executed:
            logger.debug('No callback & no coroutine defined')


def _callback(pin):
    logger.debug('Button press detected; put pin in queue %s' % (pin,))
    loop.call_soon_threadsafe(asyncio.ensure_future, _pin_events.put(str(pin)))
