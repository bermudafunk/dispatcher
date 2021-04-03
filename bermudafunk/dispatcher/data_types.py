import asyncio
import enum
import functools
import typing

import attr

from bermudafunk.io.common import BaseButton, BaseTriColorLamp, TriColorLampState
from bermudafunk.io.dummy import DummyTriColorLamp


@attr.frozen
class StudioLampState:
    main: TriColorLampState = attr.field(validator=attr.validators.instance_of(TriColorLampState))
    immediate: TriColorLampState = attr.field(validator=attr.validators.instance_of(TriColorLampState))


@enum.unique
class Button(enum.Enum):
    takeover = 'takeover'
    release = 'release'
    immediate = 'immediate'


class BaseStudio:
    names = {}  # type: typing.Dict[str, BaseStudio]

    def __init__(
        self,
        name: str,
        main_lamp: BaseTriColorLamp = None,
        immediate_lamp: BaseTriColorLamp = None,
    ):
        self._name = name
        if name in BaseStudio.names.keys():
            raise ValueError('name already used %s' % name)
        Studio.names[name] = self

        self._main_lamp = main_lamp if main_lamp else DummyTriColorLamp(name="main dummy of " + name)
        self._immediate_lamp = immediate_lamp if immediate_lamp else DummyTriColorLamp(name="immediate dummy of " + name)

        self.dispatcher_button_event_queue = None  # type: typing.Optional[asyncio.Queue]

    @property
    def name(self) -> str:
        return self._name

    @property
    def main_lamp(self) -> BaseTriColorLamp:
        return self._main_lamp

    @property
    def immediate_lamp(self) -> BaseTriColorLamp:
        return self._immediate_lamp

    @property
    def lamp_state(self) -> StudioLampState:
        return StudioLampState(
            main=self._main_lamp.color_lamp_state,
            immediate=self._immediate_lamp.color_lamp_state,
        )

    @lamp_state.setter
    def lamp_state(self, studio_lamp_status: StudioLampState):
        self._main_lamp.color_lamp_state = studio_lamp_status.main
        self._immediate_lamp.color_lamp_state = studio_lamp_status.immediate


class Automat(BaseStudio):
    def __init__(self, main_lamp: BaseTriColorLamp = None):
        super().__init__(name='Automat', main_lamp=main_lamp)


class Studio(BaseStudio):
    def __init__(
        self,
        name: str,
        takeover_button: BaseButton = None,
        release_button: BaseButton = None,
        immediate_button: BaseButton = None,
        main_lamp: BaseTriColorLamp = None,
        immediate_lamp: BaseTriColorLamp = None,
    ):
        super(Studio, self).__init__(name=name, main_lamp=main_lamp, immediate_lamp=immediate_lamp)
        self._takeover_button = None  # type: typing.Optional[BaseButton]
        self._release_button = None  # type: typing.Optional[BaseButton]
        self._immediate_button = None  # type: typing.Optional[BaseButton]

        self.takeover_button = takeover_button
        self.release_button = release_button
        self.immediate_button = immediate_button

    def __del__(self):
        self.takeover_button = None
        self.release_button = None
        self.immediate_button = None

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

    async def __button_coroutine(self, button):
        event = ButtonEvent(self, button)

        if event and self.dispatcher_button_event_queue:
            await self.dispatcher_button_event_queue.put(event)

    __takeover_button_coroutine = functools.partialmethod(__button_coroutine, Button.takeover)
    __release_button_coroutine = functools.partialmethod(__button_coroutine, Button.release)
    __immediate_button_coroutine = functools.partialmethod(__button_coroutine, Button.immediate)

    def __repr__(self):
        return '<Studio: name=%s>' % self.name


@attr.frozen
class DispatcherStudioDefinition:
    studio: BaseStudio = attr.field(validator=attr.validators.instance_of(BaseStudio))
    selector_value: int = attr.field(validator=attr.validators.instance_of(int))


@attr.frozen
class ButtonEvent:
    studio: Studio = attr.field(validator=attr.validators.instance_of(Studio))
    button: Button = attr.field(validator=attr.validators.instance_of(Button))


triggers = {"next_hour", "immediate_state_timeout", "immediate_release_timeout"} | set(
    ("{}_{}".format(button.value, studio) for button in Button for studio in ("X", "Y"))
)
