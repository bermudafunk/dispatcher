import functools
import logging
import threading
import typing

import RPi.GPIO

from . import common

logger = logging.getLogger(__name__)


class GPIO:
    _used_pins = set()
    _initialized = False

    def __init__(self, pin: int, direction, initial=-1, pull_up_down=RPi.GPIO.PUD_OFF):
        if pin in GPIO._used_pins:
            raise ValueError("The pin {} was already used".format(pin))

        if direction not in (RPi.GPIO.IN, RPi.GPIO.OUT):
            raise ValueError("Direction has to be one of RPi.GPIO.IN or RPi.GPIO.OUT, given {}".format(direction))

        if direction is not RPi.GPIO.OUT and initial != -1:
            raise ValueError("initial is only supported on direction RPi.GPIO.OUT")
        if direction is RPi.GPIO.OUT and initial not in (None, RPi.GPIO.LOW, RPi.GPIO.HIGH):
            raise ValueError("initial has to be one of RPi.GPIO.LOW, RPi.GPIO.HIGH or None, given {}", initial)

        if direction is not RPi.GPIO.IN and pull_up_down is not RPi.GPIO.PUD_OFF:
            raise ValueError("pull_up_down is only supported on direction RPi.GPIO.IN")
        if direction is RPi.GPIO.IN and pull_up_down not in (None, RPi.GPIO.PUD_UP, RPi.GPIO.PUD_DOWN, RPi.GPIO.PUD_OFF):
            raise ValueError(
                "pull_up_down has to be one of RPi.GPIO.PUD_UP, RPi.GPIO.PUD_DOWN, RPi.GPIO.PUD_OFF or None, given {}".format(pull_up_down))

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


class Input(common.BaseInput, GPIO):
    DEBOUNCE_TIME = 200  # in ms

    def __init__(self, name: str, pin: int, pull_up_down=RPi.GPIO.PUD_UP, internal_pull=False):
        common.BaseInput.__init__(self, name)
        GPIO.__init__(self, pin, direction=RPi.GPIO.IN, pull_up_down=(pull_up_down if internal_pull else RPi.GPIO.PUD_OFF))

        if pull_up_down not in (RPi.GPIO.PUD_UP, RPi.GPIO.PUD_DOWN):
            raise ValueError("Button only support PUD_UP or PUD_DOWN")

        if pull_up_down is RPi.GPIO.PUD_DOWN:
            RPi.GPIO.add_event_detect(pin,
                                      RPi.GPIO.RISING,
                                      callback=self.trigger_event,
                                      bouncetime=Input.DEBOUNCE_TIME)
        elif pull_up_down is RPi.GPIO.PUD_UP:
            RPi.GPIO.add_event_detect(pin,
                                      RPi.GPIO.FALLING,
                                      callback=self.trigger_event,
                                      bouncetime=Input.DEBOUNCE_TIME)

    def __del__(self):
        RPi.GPIO.remove_event_detect(self.pin)
        super().__del__()


class Output(common.BaseOutput, GPIO):
    def __init__(self, name: str, pin: int):
        common.BaseOutput.__init__(self, name)
        GPIO.__init__(self, pin, direction=RPi.GPIO.OUT, initial=RPi.GPIO.LOW)

        self._state = common.OutputState.OFF  # type: common.OutputState
        self._lock = threading.Lock()
        self._blinker = None  # type: typing.Optional[common.Blinker]

    @property
    def state(self) -> common.OutputState:
        return self._state

    @state.setter
    def state(self, new_state: common.OutputState):
        if not isinstance(new_state, common.OutputState):
            raise ValueError("This supports only values of {}".format(type(common.OutputState)))
        with self._lock:
            if self._state is not new_state:
                if new_state.frequency > 0:
                    if self._blinker is None:
                        self._blinker = common.Blinker(
                            name="Blinker thread of GPIO lamp {}".format(self.name),
                            frequency=new_state.frequency,
                            output_caller=[
                                functools.partial(RPi.GPIO.output, self.pin, RPi.GPIO.LOW),
                                functools.partial(RPi.GPIO.output, self.pin, RPi.GPIO.HIGH),
                            ]
                        )
                        self._blinker.start()
                    else:
                        self._blinker.frequency = new_state.frequency
                else:
                    if self._blinker is not None:
                        self._blinker.stop()
                        self._blinker = None
                    if new_state is common.OutputState.OFF:
                        RPi.GPIO.output(self.pin, RPi.GPIO.LOW)
                    elif new_state is common.OutputState.ON:
                        RPi.GPIO.output(self.pin, RPi.GPIO.HIGH)
                    else:
                        raise ValueError("Unknown lamp state with frequency 0")

                self._state = new_state

    def __del__(self):
        self.state = common.OutputState.OFF
        super().__del__()
