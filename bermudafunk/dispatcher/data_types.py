import asyncio
import enum
import typing

from bermudafunk import GPIO
from bermudafunk.GPIO import LedState


@enum.unique
class StudioLeds(enum.Enum):
    red = 'red'
    yellow = 'yellow'
    green = 'green'


LedStatus = typing.NamedTuple('LedStatus', [('state', LedState), ('blink_freq', float)])
StudioLedStatus = typing.NamedTuple('StudioLedStatus', [('green', LedStatus),
                                                        ('yellow', LedStatus),
                                                        ('red', LedStatus)])


@enum.unique
class Button(enum.Enum):
    takeover = 'takeover'
    release = 'release'
    immediate = 'immediate'


class Studio:
    names = {}  # type: typing.Dict[str, Studio]

    def __init__(self,
                 name: str,
                 takeover_button_pin: int = None,
                 release_button_pin: int = None,
                 immediate_button_pin: int = None,
                 green_led: GPIO.Led = None,
                 yellow_led: GPIO.Led = None,
                 red_led: GPIO.Led = None
                 ):
        self._name = name
        if name in Studio.names.keys():
            raise ValueError('name already used %s' % name)
        Studio.names[name] = self

        self._takeover_button_pin = None
        self._release_button_pin = None
        self._immediate_button_pin = None

        self.takeover_button_pin = takeover_button_pin
        self.release_button_pin = release_button_pin
        self.immediate_button_pin = immediate_button_pin

        self._green_led = green_led if green_led else GPIO.DummyLed()
        self._yellow_led = yellow_led if yellow_led else GPIO.DummyLed()
        self._red_led = red_led if red_led else GPIO.DummyLed()

        self.dispatcher_button_event_queue = None  # type: typing.Optional[asyncio.Queue]

    def __del__(self):
        self.takeover_button_pin = None
        self.release_button_pin = None
        self.immediate_button_pin = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def takeover_button_pin(self) -> int:
        return self._takeover_button_pin

    @takeover_button_pin.setter
    def takeover_button_pin(self, new_pin: int):
        if new_pin != self._takeover_button_pin:
            return
        if self._takeover_button_pin is not None:
            GPIO.remove_button(self._takeover_button_pin)

        self._takeover_button_pin = new_pin

        if new_pin is not None:
            GPIO.register_button(new_pin, coroutine=self._gpio_button_coroutine)

    @property
    def release_button_pin(self) -> int:
        return self._release_button_pin

    @release_button_pin.setter
    def release_button_pin(self, new_pin: int):
        if new_pin != self._release_button_pin:
            return
        if self._release_button_pin is not None:
            GPIO.remove_button(self._release_button_pin)

        self._release_button_pin = new_pin

        if new_pin is not None:
            GPIO.register_button(new_pin, coroutine=self._gpio_button_coroutine)

    @property
    def immediate_button_pin(self) -> int:
        return self._immediate_button_pin

    @immediate_button_pin.setter
    def immediate_button_pin(self, new_pin: int):
        if new_pin != self._immediate_button_pin:
            return
        if self._immediate_button_pin is not None:
            GPIO.remove_button(self._immediate_button_pin)

        self._immediate_button_pin = new_pin

        if new_pin is not None:
            GPIO.register_button(new_pin, coroutine=self._gpio_button_coroutine)

    @property
    def green_led(self) -> GPIO.DummyLed:
        return self._green_led

    @property
    def yellow_led(self) -> GPIO.DummyLed:
        return self._yellow_led

    @property
    def red_led(self) -> GPIO.DummyLed:
        return self._red_led

    @property
    def led_status(self) -> typing.Dict[str, typing.Dict[str, typing.Union[str, int]]]:
        return {
            'green':
                {
                    'state': self.green_led.state.name,
                    'blink_freq': self.green_led.blink_freq
                },
            'yellow':
                {
                    'state': self.yellow_led.state.name,
                    'blink_freq': self.yellow_led.blink_freq
                },
            'red':
                {
                    'state': self.red_led.state.name,
                    'blink_freq': self.red_led.blink_freq
                },
        }

    @property
    def led_status_typed(self) -> StudioLedStatus:
        return StudioLedStatus(
            green=LedStatus(state=self.green_led.state, blink_freq=self.green_led.blink_freq),
            yellow=LedStatus(state=self.yellow_led.state, blink_freq=self.yellow_led.blink_freq),
            red=LedStatus(state=self.red_led.state, blink_freq=self.red_led.blink_freq)
        )

    @led_status_typed.setter
    def led_status_typed(self, studio_led_status: StudioLedStatus):
        self.green_led.state = studio_led_status.green.state
        self.green_led.blink_freq = studio_led_status.green.blink_freq

        self.yellow_led.state = studio_led_status.yellow.state
        self.yellow_led.blink_freq = studio_led_status.yellow.blink_freq

        self.red_led.state = studio_led_status.red.state
        self.red_led.blink_freq = studio_led_status.red.blink_freq

    async def _gpio_button_coroutine(self, pin):
        event = None
        if pin == self._takeover_button_pin:
            event = ButtonEvent(self, Button.takeover)
        elif pin == self._release_button_pin:
            event = ButtonEvent(self, Button.release)
        elif pin == self._immediate_button_pin:
            event = ButtonEvent(self, Button.immediate)

        if event and self.dispatcher_button_event_queue:
            await self.dispatcher_button_event_queue.put(event)

    def __repr__(self):
        return '<Studio: name=%s>' % self.name


DispatcherStudioDefinition = typing.NamedTuple('DispatcherStudioDefinition', [('studio', Studio), ('selector_value', int)])
ButtonEvent = typing.NamedTuple('ButtonEvent', [('studio', Studio), ('button', Button)])
