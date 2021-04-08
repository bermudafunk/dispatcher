import abc
import asyncio
import collections.abc
import enum
import functools
import inspect
import itertools
import logging
import threading
import time
from typing import Callable, List, Optional, Set

import attr

from bermudafunk import base

logger = logging.getLogger(__name__)


class BaseButton(abc.ABC):
    def __init__(self, name: str):
        self.__trigger: Set[Callable] = set()
        self._name = str(name)

    @property
    def name(self) -> str:
        return self._name

    def add_handler(self, handler: Callable):
        if not isinstance(handler, collections.abc.Hashable):
            raise TypeError("The supplied handler isn't hashable")
        if not callable(handler):
            raise TypeError("The supplied handler isn't callable")
        self.__trigger.add(handler)

    def remove_handler(self, handler: Callable):
        if not isinstance(handler, collections.abc.Hashable):
            raise TypeError("The supplied handler isn't hashable")
        if not callable(handler):
            raise TypeError("The supplied handler isn't callable")
        self.__trigger.remove(handler)

    def _trigger_event(self, *_, **__):
        for trigger in self.__trigger:
            if inspect.iscoroutinefunction(trigger) or (
                isinstance(trigger, functools.partial) and inspect.iscoroutinefunction(trigger.func)):
                asyncio.run_coroutine_threadsafe(trigger(), base.loop)
            else:
                trigger()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self._name!r})"


@enum.unique
class LampState(enum.Enum):
    OFF = 0
    ON = 0
    BLINK = 2
    BLINK_FAST = 4

    def __new__(cls, frequency: float):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._frequency = float(frequency)
        obj._value_ = value
        return obj

    @property
    def frequency(self) -> float:
        return self._frequency

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


class BaseLamp(abc.ABC):
    def __init__(
        self,
        name: str,
        on_callable: Callable,
        off_callable: Callable,
        state: LampState,
    ):
        self._name = str(name)

        if not isinstance(state, LampState):
            raise TypeError(f"This supports only values of {LampState}")
        self._state = state
        self._lock = threading.RLock()
        self._blinker: Optional[Blinker] = None

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
        logger.debug('Lamp with name <%s> set state <%s>', self.name, new_state)
        if not isinstance(new_state, LampState):
            raise TypeError(f"This supports only values of {LampState}")
        with self._lock:
            if self._state is not new_state:
                self._state = new_state
                self._assure_state()

    def _assure_state(self):
        if self._state.frequency > 0:
            if self._blinker is None:
                self._blinker = Blinker(
                    name=f"Blinker thread of lamp {self.name}",
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
                raise ValueError(f"Unknown lamp state with frequency 0: {self._state!r}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self._name!r}, state={self._state!r})"


@enum.unique
class TriColorLampColor(enum.Flag):
    NONE = 0
    GREEN = enum.auto()
    RED = enum.auto()
    YELLOW = GREEN | RED

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


@attr.s(frozen=True, slots=True)
class TriColorLampState:
    state: LampState = attr.ib(validator=attr.validators.instance_of(LampState))
    color: TriColorLampColor = attr.ib(validator=attr.validators.instance_of(TriColorLampColor))


class BaseTriColorLamp(BaseLamp):
    def __init__(
        self,
        name: str,
        on_callable: Callable,
        off_callable: Callable,
        state: LampState,
        color: TriColorLampColor,
    ):
        if not isinstance(color, TriColorLampColor):
            raise TypeError(f"This supports only values of {TriColorLampColor}")
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
        logger.debug("Lamp with name <%s> set color <%s>", self.name, new_color)
        if not isinstance(new_color, TriColorLampColor):
            raise TypeError(f"This supports only values of {TriColorLampColor}")
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
            raise TypeError(f"This supports only values of {TriColorLampState}")
        with self._lock:
            if self.color_lamp_state != new_color_lamp_state:
                self._state = new_color_lamp_state.state
                self._color = new_color_lamp_state.color
                self._assure_state()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self._name!r}, state={self._state!r}, color={self._color!r})"


class Blinker(threading.Thread):
    def __init__(self, output_caller: List[Callable[[], None]], frequency: float, name="Blinker Thread"):
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
            raise TypeError("Frequency have to be a float or int")
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
