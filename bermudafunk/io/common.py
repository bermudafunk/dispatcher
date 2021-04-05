import abc
import asyncio
import collections.abc
import enum
import inspect
import itertools
import logging
import threading
import time
import typing

import attr

from bermudafunk.base import loop

logger = logging.getLogger(__name__)


class BaseButton(abc.ABC):
    def __init__(self, name: str):
        self.__trigger: typing.Set[typing.Callable] = set()
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def add_handler(self, handler: typing.Callable):
        if not isinstance(handler, collections.abc.Hashable):
            raise TypeError("The supplied handler isn't hashable")
        if not callable(handler):
            raise TypeError("The supplied handler isn't callable")
        self.__trigger.add(handler)

    def remove_handler(self, handler: typing.Callable):
        if not isinstance(handler, collections.abc.Hashable):
            raise TypeError("The supplied handler isn't hashable")
        if not callable(handler):
            raise TypeError("The supplied handler isn't callable")
        self.__trigger.remove(handler)

    def _trigger_event(self, *args, **kwargs):
        for trigger in self.__trigger:
            if inspect.iscoroutinefunction(trigger):
                asyncio.run_coroutine_threadsafe(trigger(), loop)
            else:
                trigger()

    def __repr__(self) -> str:
        return '{}(name={!r})'.format(
            type(self).__name__,
            self._name,
        )


@enum.unique
class LampState(enum.Enum):
    OFF = 0
    ON = 0
    BLINK = 2
    BLINK_FAST = 4

    def __new__(cls, frequency: float):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._frequency = frequency
        obj._value_ = value
        return obj

    @property
    def frequency(self) -> float:
        return self._frequency

    def __repr__(self):
        return '{}.{}'.format(type(self).__name__, self.name)


class BaseLamp(abc.ABC):
    def __init__(
        self,
        name: str,
        on_callable: typing.Callable,
        off_callable: typing.Callable,
        state: LampState,
    ):
        self._name = name

        if not isinstance(state, LampState):
            raise ValueError("This supports only values of {}".format(LampState))
        self._state = state
        self._lock = threading.RLock()
        self._blinker: typing.Optional[Blinker] = None

        self._on_callable = on_callable
        self._off_callable = off_callable

        self._assure_state()

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> LampState:
        return self._state

    @state.setter
    def state(self, new_state: LampState):
        logger.debug('Lamp with name <{}> set state <{}>'.format(self.name, new_state))
        if not isinstance(new_state, LampState):
            raise ValueError("This supports only values of {}".format(LampState))
        with self._lock:
            if self._state is not new_state:
                self._state = new_state
                self._assure_state()

    def _assure_state(self):
        if self._state.frequency > 0:
            if self._blinker is None:
                self._blinker = Blinker(
                    name="Blinker thread of lamp {}".format(self.name),
                    frequency=self._state.frequency,
                    output_caller=[self._on_callable, self._off_callable],
                )
                self._blinker.start()
            else:
                self._blinker.frequency = self._state.frequency
        else:
            if self._blinker is not None:
                self._blinker.stop()
                self._blinker = None
            if self._state is LampState.OFF:
                self._off_callable()
            elif self._state is LampState.ON:
                self._on_callable()
            else:
                raise ValueError("Unknown lamp state with frequency 0")

    def __repr__(self) -> str:
        return '{}(name={!r}, state={!r})'.format(
            type(self).__name__,
            self._name,
            self._state,
        )


@enum.unique
class TriColorLampColor(enum.Flag):
    NONE = 0
    GREEN = enum.auto()
    RED = enum.auto()
    YELLOW = GREEN | RED

    def __repr__(self):
        return '{}.{}'.format(type(self).__name__, self.name)


@attr.s(frozen=True)
class TriColorLampState:
    state: LampState = attr.ib(validator=attr.validators.in_(LampState))
    color: TriColorLampColor = attr.ib(validator=attr.validators.in_(TriColorLampColor))


class BaseTriColorLamp(BaseLamp):
    def __init__(
        self,
        name: str,
        on_callable: typing.Callable,
        off_callable: typing.Callable,
        state: LampState,
        color: TriColorLampColor,
    ):
        self._color = color
        super().__init__(
            name=name,
            on_callable=on_callable,
            off_callable=off_callable,
            state=state,
        )

    @property
    def color(self) -> TriColorLampColor:
        return self._color

    @color.setter
    def color(self, new_color: TriColorLampColor):
        logger.debug('Lamp with name <{}> set color <{}>'.format(self.name, new_color))
        if not isinstance(new_color, TriColorLampColor):
            raise ValueError("This supports only values of {}".format(type(TriColorLampColor)))
        with self._lock:
            if self._color is not new_color:
                self._color = new_color
                self._assure_state()

    @property
    def color_lamp_state(self) -> TriColorLampState:
        with self._lock:
            return TriColorLampState(color=self._color, state=self._state)

    @color_lamp_state.setter
    def color_lamp_state(self, new_color_lamp_state: TriColorLampState):
        if not isinstance(new_color_lamp_state, TriColorLampState):
            raise ValueError("This supports only values of {}".format(type(TriColorLampState)))
        with self._lock:
            self.state = new_color_lamp_state.state
            self.color = new_color_lamp_state.color
            self._assure_state()

    def __repr__(self) -> str:
        return '{}(name={!r}, state={!r}, color={!r})'.format(
            type(self).__name__,
            self._name,
            self._state,
            self._color,
        )


class Blinker(threading.Thread):
    def __init__(self, output_caller: typing.List[typing.Callable[[], None]], frequency: float, name="Blinker Thread"):
        super().__init__(name=name, daemon=True)
        self._output_caller = output_caller

        self._frequency = frequency
        self._time_to_sleep = 1 / frequency

        self._stop_event = threading.Event()

    @property
    def frequency(self) -> float:
        return self._frequency

    @frequency.setter
    def frequency(self, new_frequency: float):
        if not isinstance(new_frequency, (float, int)):
            raise ValueError("Frequency have to be a float or int")
        self._frequency = new_frequency
        self._time_to_sleep = 1 / new_frequency

    def run(self):
        for caller in itertools.cycle(self._output_caller):
            caller()
            time.sleep(self._time_to_sleep)
            if self._stop_event.is_set():
                break

    def stop(self):
        self._stop_event.set()
