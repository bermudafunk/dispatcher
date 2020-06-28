import abc
import collections.abc
import enum
import typing


class BaseButton(abc.ABC):
    def __init__(self):
        self.__trigger = set()  # type: typing.Set[typing.Callable]

    def register(self, trigger: typing.Callable):
        if not isinstance(trigger, collections.abc.Hashable):
            raise TypeError("The supplied trigger isn't hashable")
        if not isinstance(trigger, collections.abc.Callable):
            raise TypeError("The supplied trigger isn't callable")
        self.__trigger.add(trigger)

    def deregister(self, trigger: typing.Callable):
        if not isinstance(trigger, collections.abc.Hashable):
            raise TypeError("The supplied trigger isn't hashable")
        if not isinstance(trigger, collections.abc.Callable):
            raise TypeError("The supplied trigger isn't callable")
        self.__trigger.remove(trigger)

    def trigger(self):
        for trigger in self.__trigger:
            trigger(self)


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
    @property
    @abc.abstractmethod
    def state(self) -> LampState:
        pass

    @state.setter
    @abc.abstractmethod
    def state(self, state: LampState):
        pass
