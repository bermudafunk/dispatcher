import abc
import asyncio
import collections.abc
import enum
import inspect
import itertools
import threading
import time
import typing

from bermudafunk.base import loop


class BaseButton(abc.ABC):
    def __init__(self, name: str):
        self.__trigger = set()  # type: typing.Set[typing.Callable]
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def add_handler(self, handler: typing.Callable):
        if not isinstance(handler, collections.abc.Hashable):
            raise TypeError("The supplied handler isn't hashable")
        if not isinstance(handler, collections.abc.Callable):
            raise TypeError("The supplied handler isn't callable")
        self.__trigger.add(handler)

    def remove_handler(self, handler: typing.Callable):
        if not isinstance(handler, collections.abc.Hashable):
            raise TypeError("The supplied handler isn't hashable")
        if not isinstance(handler, collections.abc.Callable):
            raise TypeError("The supplied handler isn't callable")
        self.__trigger.remove(handler)

    def _trigger_event(self, *args, **kwargs):
        for trigger in self.__trigger:
            if inspect.iscoroutinefunction(trigger):
                asyncio.run_coroutine_threadsafe(trigger(), loop)
            else:
                trigger()


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
    def __init__(self, name: str, on_callable: typing.Callable, off_callable: typing.Callable):
        self._name = name

        self._state = LampState.OFF  # type: LampState
        self._lock = threading.Lock()
        self._blinker = None  # type: typing.Optional[Blinker]

        self._on_callable = on_callable
        self._off_callable = off_callable

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> LampState:
        return self._state

    @state.setter
    def state(self, new_state: LampState):
        if not isinstance(new_state, LampState):
            raise ValueError("This supports only values of {}".format(type(LampState)))
        with self._lock:
            if self._state is not new_state:
                if new_state.frequency > 0:
                    if self._blinker is None:
                        self._blinker = Blinker(
                            name="Blinker thread of lamp {}".format(self.name),
                            frequency=new_state.frequency,
                            output_caller=[self._on_callable, self._off_callable]
                        )
                        self._blinker.start()
                    else:
                        self._blinker.frequency = new_state.frequency
                else:
                    if self._blinker is not None:
                        self._blinker.stop()
                        self._blinker = None
                    if new_state is LampState.OFF:
                        self._off_callable()
                    elif new_state is LampState.ON:
                        self._on_callable()
                    else:
                        raise ValueError("Unknown lamp state with frequency 0")

                self._state = new_state


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
            time.sleep(self._time_to_sleep)
            if self._stop_event.is_set():
                break

    def stop(self):
        self._stop_event.set()
