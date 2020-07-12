import abc
import asyncio
import collections.abc
import enum
import inspect
import itertools
import threading
import time
import typing
import weakref

from bermudafunk.base.asyncio import loop


@enum.unique
class ButtonEvent(enum.Enum):
    PRESSED = enum.auto()
    RELEASED = enum.auto()


class BaseButton(abc.ABC):
    def __init__(self, name: str):
        self.__trigger = weakref.WeakSet()  # type: typing.Set[typing.Callable]
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def add_handler(self, handler: typing.Callable[[ButtonEvent], None]):
        if not isinstance(handler, collections.abc.Hashable):
            raise TypeError("The supplied handler isn't hashable")
        if not isinstance(handler, collections.abc.Callable):
            raise TypeError("The supplied handler isn't callable")
        self.__trigger.add(handler)

    def remove_handler(self, handler: typing.Callable[[ButtonEvent], None]):
        if not isinstance(handler, collections.abc.Hashable):
            raise TypeError("The supplied handler isn't hashable")
        if not isinstance(handler, collections.abc.Callable):
            raise TypeError("The supplied handler isn't callable")
        self.__trigger.remove(handler)

    def trigger_event(self, event: ButtonEvent, *args, **kwargs):
        for trigger in self.__trigger:
            if inspect.iscoroutinefunction(trigger):
                asyncio.run_coroutine_threadsafe(trigger(event), loop)
            else:
                trigger(event)


@enum.unique
class LampState(enum.Enum):
    def __new__(cls, frequency: float):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._frequency = frequency
        obj._value_ = value
        return obj

    @property
    def frequency(self) -> float:
        return self._frequency

    OFF = 0
    ON = 0
    BLINK = 2
    BLINK_FAST = 4


class BaseLamp(abc.ABC):
    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    @abc.abstractmethod
    def state(self) -> LampState:
        pass

    @state.setter
    @abc.abstractmethod
    def state(self, state: LampState):
        pass


class Blinker(threading.Thread):
    def __init__(self, output_caller: typing.List[typing.Callable[[], None]], frequency: float, name="Blinker Thread"):
        super().__init__(name=name, daemon=True)
        self._output_caller = output_caller

        self._frequency = frequency
        self._time_to_sleep = 1 / frequency
        self._frequency_lock = threading.Lock()

        self._stop_event = threading.Event()

    @property
    def frequency(self) -> float:
        return self._frequency

    @frequency.setter
    def frequency(self, new_frequency: float):
        if not isinstance(new_frequency, (float, int)):
            raise ValueError("Frequency have to be a float or int")
        with self._frequency_lock:
            self._frequency = new_frequency
            self._time_to_sleep = 1 / new_frequency

    def run(self):
        for caller in itertools.cycle(self._output_caller):
            caller()
            if self._stop_event.is_set():
                break
            time.sleep(self._time_to_sleep)

    def stop(self):
        self._stop_event.set()
