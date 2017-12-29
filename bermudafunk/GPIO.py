import asyncio
from RPi import GPIO

from .Base import loop, logger
from . import Queues, Base

_initialized = None

buttons = {}
leds = {}

used_pins = {}


class Led:
    STATE_OFF = 'off'
    STATE_ON = 'on'
    STATE_BLINK = 'blink'
    STATES = [STATE_OFF, STATE_ON, STATE_BLINK]

    def __init__(self, pin):
        global leds
        leds[str(pin)] = self

        self.pin = int(pin)
        self.state = self.STATE_OFF
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

    def set_state(self, new_state, force=False, blink_freq=2):
        if new_state not in self.STATES:
            raise Exception('Unknown state %s' % new_state)

        self.blink_freq = blink_freq

        if self.state == new_state and not force:
            return  # Same state, nothing to change

        old_state = self.state
        self.state = new_state

        if self._blink_task is not None:
            self._blink_task.cancel()
            self._blink_task = None

        if new_state is self.STATE_ON:
            GPIO.output(self.pin, GPIO.HIGH)
        elif new_state is self.STATE_OFF:
            GPIO.output(self.pin, GPIO.LOW)
        elif new_state is self.STATE_BLINK:
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
        Base.cleanup_tasks.append(loop.create_task(_cleanup()))


def _check_pin(pin, usage):
    global used_pins
    pin = int(pin)
    if pin not in used_pins:
        used_pins[pin] = usage
    if pin in used_pins and used_pins[pin] == usage:
        return True
    raise Exception('pin %s already used as %s instead of %s' % (pin, used_pins[pin], usage))


async def _cleanup():
    logger.debug('cleanup awaiting')
    await Base.cleanup.wait()
    logger.debug('cleanup cancel process_event')
    _initialized.cancel()
    logger.debug('cleanup reset GPIO')
    GPIO.cleanup()


def register_button(pin, callback=None, coroutine=None, override=False, **kwargs):
    global buttons
    _setup()
    pin = int(pin)
    if not override and pin in buttons:
        logger.debug('register_button override not forced so do not override')
        return False
    logger.debug('register_button %s', pin)
    _check_pin(pin, 'button')
    GPIO.setup(pin, GPIO.IN, **kwargs)
    GPIO.add_event_detect(pin, GPIO.RISING, callback=_callback, bouncetime=300)
    buttons[str(pin)] = {'pin': pin, 'callback': callback, 'coroutine': coroutine}


def remove_button(pin):
    global buttons
    GPIO.remove_event_detect(pin)
    del buttons[str(pin)]


async def _process_event():
    global buttons
    while True:
        pin = await Queues.get_queue('gpio_raw').get()
        something_executed = False
        if pin in buttons:
            if buttons[pin]['callback'] is not None:
                print('callback will be called soon')
                loop.call_soon(buttons[pin]['callback'], int(pin))
                something_executed = True
            if buttons[pin]['coroutine'] is not None:
                print('coroutine scheduled as a task')
                loop.create_task(buttons[pin]['coroutine'](int(pin)))
                something_executed = True
        if not something_executed:
            print('No callback & no coroutine defined')


def _callback(pin):
    logger.debug('Button press detected; put pin in queue %s' % (pin,))
    loop.call_soon_threadsafe(asyncio.ensure_future, Queues.put_in_queue(str(pin), 'gpio_raw'))
