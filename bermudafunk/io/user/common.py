import abc
import collections.abc
import enum
import typing
import weakref


@enum.unique
class ButtonEvent(enum.Enum):
    PRESSED = enum.auto()
    RELEASED = enum.auto()


class BaseButton(abc.ABC):
    def __init__(self, name: str):
        self.__trigger = weakref.WeakSet()  # type: weakref.WeakSet[typing.Callable]
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

    def trigger_event(self, event: ButtonEvent):
        for trigger in self.__trigger:
            trigger(self, event)


@enum.unique
class LampState(enum.Enum):
    def __new__(cls, frequency: float):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj.frequency = frequency
        obj._value_ = value
        return obj

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
