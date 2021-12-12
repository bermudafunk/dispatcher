import functools
import logging
import typing

import RPi.GPIO

from bermudafunk.io import common

logger = logging.getLogger(__name__)


class GPIO:
    _used_pins: typing.Set[int] = set()
    _initialized = False

    def __init__(self, pin: int, direction, initial=None, pull_up_down=RPi.GPIO.PUD_OFF):
        if pin in GPIO._used_pins:
            raise ValueError("The pin {} was already used".format(pin))

        if direction not in (RPi.GPIO.IN, RPi.GPIO.OUT):
            raise ValueError("Direction has to be one of RPi.GPIO.IN or RPi.GPIO.OUT, given {}".format(direction))

        if direction is not RPi.GPIO.OUT and initial is not None:
            raise ValueError("initial is only supported on direction RPi.GPIO.OUT")
        if direction is RPi.GPIO.OUT and initial not in (None, RPi.GPIO.LOW, RPi.GPIO.HIGH):
            raise ValueError("initial has to be one of RPi.GPIO.LOW, RPi.GPIO.HIGH or None, given {}", initial)

        if direction is not RPi.GPIO.IN and pull_up_down is not RPi.GPIO.PUD_OFF:
            raise ValueError("pull_up_down is only supported on direction RPi.GPIO.IN")
        if direction is RPi.GPIO.IN and pull_up_down not in (None, RPi.GPIO.PUD_UP, RPi.GPIO.PUD_DOWN, RPi.GPIO.PUD_OFF):
            raise ValueError(
                "pull_up_down has to be one of RPi.GPIO.PUD_UP, RPi.GPIO.PUD_DOWN, RPi.GPIO.PUD_OFF or None, given {}".format(pull_up_down)
            )

        GPIO._used_pins.add(pin)
        self._pin = pin
        self._direction = direction
        self._initial = initial
        self._pull_up_down = pull_up_down

        if not GPIO._initialized:
            if RPi.GPIO.getmode() is not None:
                raise RuntimeError("RPi.GPIO seems to have been already used.")
            RPi.GPIO.setmode(RPi.GPIO.BOARD)
            GPIO._initialized = True

        RPi.GPIO.setup(pin, direction, initial=initial, pull_up_down=pull_up_down)

    @property
    def pin(self) -> int:
        return self._pin

    def __del__(self):
        RPi.GPIO.cleanup(self._pin)

    def __repr__(self) -> str:
        return "{}(pin={!r}, direction={!r}, initial={!r}, pull_up_down={!r})".format(
            type(self).__name__,
            self._pin,
            self._direction,
            self._initial,
            self._pull_up_down,
        )


class GPIOButton(common.BaseButton, GPIO):
    DEBOUNCE_TIME = 150  # in ms

    def __init__(self, name: str, pin: int, pull_up_down=RPi.GPIO.PUD_UP, internal_pull=False):
        self._internal_pull = bool(internal_pull)

        GPIO.__init__(self, pin, direction=RPi.GPIO.IN, pull_up_down=(pull_up_down if self._internal_pull else RPi.GPIO.PUD_OFF))
        common.BaseButton.__init__(self, name)

        if pull_up_down not in (RPi.GPIO.PUD_UP, RPi.GPIO.PUD_DOWN):
            raise ValueError("Button only support PUD_UP or PUD_DOWN")

        if pull_up_down is RPi.GPIO.PUD_DOWN:
            RPi.GPIO.add_event_detect(pin, RPi.GPIO.RISING, callback=self._trigger_observers, bouncetime=GPIOButton.DEBOUNCE_TIME)
        elif pull_up_down is RPi.GPIO.PUD_UP:
            RPi.GPIO.add_event_detect(pin, RPi.GPIO.FALLING, callback=self._trigger_observers, bouncetime=GPIOButton.DEBOUNCE_TIME)

    def __del__(self):
        RPi.GPIO.remove_event_detect(self.pin)
        super().__del__()

    def __repr__(self) -> str:
        return "{}(name={!r}, pin={!r}, pull_up_down={!r}, internal_pull={!r})".format(
            type(self).__name__,
            self._name,
            self._pin,
            self._pull_up_down,
            self._internal_pull,
        )


class GPIOLamp(common.BaseLamp, GPIO):
    def __init__(self, name: str, pin: int):
        GPIO.__init__(self, pin, direction=RPi.GPIO.OUT, initial=RPi.GPIO.LOW)
        common.BaseLamp.__init__(
            self,
            name,
            on_callable=functools.partial(RPi.GPIO.output, self._pin, RPi.GPIO.HIGH),
            off_callable=functools.partial(RPi.GPIO.output, self._pin, RPi.GPIO.LOW),
            state=common.LampState.OFF,
        )

    def __del__(self):
        self.state = common.LampState.OFF
        super().__del__()

    def __repr__(self) -> str:
        return "{}(name={!r}, pin={!r})".format(
            type(self).__name__,
            self._name,
            self._pin,
        )
