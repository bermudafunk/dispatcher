import asyncio
import enum
import functools
import typing

from bermudafunk.io.common import BaseLamp, LampState, BaseButton
from bermudafunk.io.dummy import DummyLamp


@enum.unique
class StudioLamps(enum.Enum):
    red = 'red'
    yellow = 'yellow'
    green = 'green'


StudioLampStatus = typing.NamedTuple('StudioLampStatus', [('green', LampState),
                                                         ('yellow', LampState),
                                                         ('red', LampState)])


@enum.unique
class Button(enum.Enum):
    takeover = 'takeover'
    release = 'release'
    immediate = 'immediate'


class Studio:
    names = {}  # type: typing.Dict[str, Studio]

    def __init__(self,
                 name: str,
                 takeover_button: BaseButton = None,
                 release_button: BaseButton = None,
                 immediate_button: BaseButton = None,
                 green_led: BaseLamp = None,
                 yellow_led: BaseLamp = None,
                 red_led: BaseLamp = None
                 ):
        self._name = name
        if name in Studio.names.keys():
            raise ValueError('name already used %s' % name)
        Studio.names[name] = self

        self._takeover_button = None  # type: typing.Optional[BaseButton]
        self._release_button = None  # type: typing.Optional[BaseButton]
        self._immediate_button = None  # type: typing.Optional[BaseButton]

        self.takeover_button = takeover_button
        self.release_button = release_button
        self.immediate_button = immediate_button

        self._green_led = green_led if green_led else DummyLamp(name="Green dummy " + name)
        self._yellow_led = yellow_led if yellow_led else DummyLamp(name="yellow dummy " + name)
        self._red_led = red_led if red_led else DummyLamp(name="red dummy " + name)

        self.dispatcher_button_event_queue = None  # type: typing.Optional[asyncio.Queue]

    def __del__(self):
        self.takeover_button = None
        self.release_button = None
        self.immediate_button = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def takeover_button(self) -> BaseButton:
        return self._takeover_button

    @takeover_button.setter
    def takeover_button(self, new_button: BaseButton):
        if new_button == self._takeover_button:
            return
        if self._takeover_button is not None:
            self._takeover_button.remove_handler(self.__takeover_button_coroutine)

        self._takeover_button = new_button

        if new_button is not None:
            self._takeover_button.add_handler(self.__takeover_button_coroutine)

    @property
    def release_button(self) -> BaseButton:
        return self._release_button

    @release_button.setter
    def release_button(self, new_button: BaseButton):
        if new_button == self._release_button:
            return
        if self._release_button is not None:
            self._release_button.remove_handler(self.__release_button_coroutine)

        self._release_button = new_button

        if new_button is not None:
            self._release_button.add_handler(self.__release_button_coroutine)

    @property
    def immediate_button(self) -> BaseButton:
        return self._immediate_button

    @immediate_button.setter
    def immediate_button(self, new_button: BaseButton):
        if new_button == self._immediate_button:
            return
        if self._immediate_button is not None:
            self._immediate_button.remove_handler(self.__immediate_button_coroutine)

        self._immediate_button = new_button

        if new_button is not None:
            self._immediate_button.add_handler(self.__immediate_button_coroutine)

    @property
    def green_led(self) -> BaseLamp:
        return self._green_led

    @property
    def yellow_led(self) -> BaseLamp:
        return self._yellow_led

    @property
    def red_led(self) -> BaseLamp:
        return self._red_led

    @property
    def led_status(self) -> typing.Dict[str, typing.Dict[str, typing.Union[str, int]]]:
        return {
            'green':
                {
                    'state': self.green_led.state.name,
                    'blink_freq': self.green_led.state.frequency
                },
            'yellow':
                {
                    'state': self.yellow_led.state.name,
                    'blink_freq': self.yellow_led.state.frequency
                },
            'red':
                {
                    'state': self.red_led.state.name,
                    'blink_freq': self.red_led.state.frequency
                },
        }

    @property
    def led_status_typed(self) -> StudioLampStatus:
        return StudioLampStatus(
            green=self.green_led.state,
            yellow=self.yellow_led.state,
            red=self.red_led.state,
        )

    @led_status_typed.setter
    def led_status_typed(self, studio_led_status: StudioLampStatus):
        self.green_led.state = studio_led_status.green
        self.yellow_led.state = studio_led_status.yellow
        self.red_led.state = studio_led_status.red

    async def __button_coroutine(self, button):
        event = ButtonEvent(self, button)

        if event and self.dispatcher_button_event_queue:
            await self.dispatcher_button_event_queue.put(event)

    __takeover_button_coroutine = functools.partialmethod(__button_coroutine, Button.takeover)
    __release_button_coroutine = functools.partialmethod(__button_coroutine, Button.release)
    __immediate_button_coroutine = functools.partialmethod(__button_coroutine, Button.immediate)

    def __repr__(self):
        return '<Studio: name=%s>' % self.name


DispatcherStudioDefinition = typing.NamedTuple('DispatcherStudioDefinition', [('studio', Studio), ('selector_value', int)])
ButtonEvent = typing.NamedTuple('ButtonEvent', [('studio', Studio), ('button', Button)])
