import asyncio
import datetime
import enum
import logging
import time
import typing
from collections import namedtuple

import bermudafunk.SymNet
from bermudafunk import GPIO, base
from bermudafunk.base.queues import get_queue

logger = logging.getLogger(__name__)


@enum.unique
class Button(enum.Enum):
    takeover = 'takeover'
    release = 'release'
    immediate = 'immediate'


DispatcherStudioDefinition = namedtuple('DispatcherStudioDefinition', ['studio', 'selector_value'])


class Studio:
    names = {}  # type: typing.Dict[str, Studio]

    def __init__(self,
                 name: str,
                 takeover_button_pin: int = None,
                 release_button_pin: int = None,
                 immediate_button_pin: int = None,
                 takeover_led: GPIO.Led = None,
                 release_led: GPIO.Led = None,
                 immediate_led: GPIO.Led = None
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

        self._takeover_led = takeover_led
        self._release_led = release_led
        self._immediate_led = immediate_led

        self.dispatcher_event_queue_name = None

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
            GPIO.register_button(new_pin, callback=self._gpio_button_callback)

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
            GPIO.register_button(new_pin, callback=self._gpio_button_callback)

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
            GPIO.register_button(new_pin, callback=self._gpio_button_callback)

    @property
    def takeover_led(self) -> GPIO.Led:
        return self._takeover_led

    @property
    def release_led(self) -> GPIO.Led:
        return self._release_led

    @property
    def immediate_led(self) -> GPIO.Led:
        return self._immediate_led

    def _gpio_button_callback(self, pin):
        event = None
        if pin == self._takeover_button_pin:
            event = ButtonEvent(self, Button.takeover)
        elif pin == self._release_button_pin:
            event = ButtonEvent(self, Button.release)
        elif pin == self._immediate_button_pin:
            event = ButtonEvent(self, Button.immediate)

        if event and self.dispatcher_event_queue_name:
            base.loop.create_task(get_queue(self.dispatcher_event_queue_name).put(event))


class ButtonEvent:
    def __init__(self, studio: Studio, button: Button) -> None:
        self._studio = studio
        self._button = button

    @property
    def studio(self) -> Studio:
        return self._studio

    @property
    def button(self) -> Button:
        return self._button


class Dispatcher:
    def __init__(self,
                 symnet_controller: bermudafunk.SymNet.SymNetSelectorController,
                 automat_selector_value: int,
                 studio_mapping: typing.List[DispatcherStudioDefinition]
                 ):

        self.immediate_state_time = 5 * 60  # seconds
        self.immediate_release_time = 30  # seconds

        self._symnet_controller = symnet_controller

        self._takeover_state_value = None  # type: typing.Optional[Studio]
        self._release_state_value = None  # type: typing.Optional[Studio]
        self._immediate_state_value = None  # type: typing.Optional[Studio]

        self._hourly_timer = None  # type: typing.Optional[asyncio.Task]
        self._immediate_state_timer = None  # type: typing.Optional[asyncio.Task]
        self._immediate_release_timer = None  # type: typing.Optional[asyncio.Task]

        self._immediate_release_lock = asyncio.Lock(loop=base.loop)

        self._dispatcher_event_queue_name = 'dispatcher_event_queue'

        self._automat_studio = Studio('automat')
        studio_mapping = list(studio_mapping) + [
            DispatcherStudioDefinition(studio=self._automat_studio, selector_value=automat_selector_value)
        ]

        self._studios = []  # type: typing.List[Studio]
        self._studios_to_selector_value = {}  # type: typing.Dict[Studio, int]
        self._selector_value_to_studio = {}  # type: typing.Dict[int, Studio]
        for studio_def in studio_mapping:
            self._studios.append(studio_def.studio)
            self._studios_to_selector_value[studio_def.studio] = studio_def.selector_value
            self._selector_value_to_studio[studio_def.selector_value] = studio_def.studio
            studio_def.studio.dispatcher_event_queue_name = self._dispatcher_event_queue_name

        self._on_air_studio = self._automat_studio

        self._symnet_controller.add_observer(self._set_current_state)
        base.start_cleanup_aware_coro(self._assure_current_state_loop)
        base.start_cleanup_aware_coro(self._process_studio_button_events)
        base.cleanup_tasks.append(base.loop.create_task(self._cleanup()))

        self._assure_hourly_timer()

    async def _cleanup(self):
        await base.cleanup_event.wait()
        self._stop_timers()

    async def _process_studio_button_events(self):
        while True:
            event = await get_queue(self._dispatcher_event_queue_name).get()  # type: ButtonEvent

            await self._change_state(event)

            self._assure_led_status()

            self._audit_state()

    async def _change_state(self, event: ButtonEvent):
        # Zustand: Automation on Air
        if self._on_air_studio == self._automat_studio:
            # Studio X drückt „Übernahme“
            if event.button is Button.takeover:
                # → nicht „Sofort-Status“
                if self._immediate_state_value is None:
                    # → noch nicht von anderswo angefordert
                    if self._takeover_state_value is None:
                        # → Übernahme anfordern → zum Stundenwechsel wird hierher umgeschaltet
                        self._takeover_state_value = event.studio
                    # → schon vom eigenen Studio Übernahme angefordert
                    elif self._takeover_state_value == event.studio:
                        # → Anforderung löschen
                        self._takeover_state_value = None
                # → schon „Sofort-Status“ vom eigenen Studio aktiviert
                elif self._immediate_state_value == event.studio:
                    # → sofortige Übernahme
                    await self._do_immediate_takeover(event.studio)

            # Studio X drückt „Freigabe“
            elif event.button is Button.release:
                # → Rücksetzung aller eigenen Anforderungen (Übernahme/ Sofort-Status)
                if self._takeover_state_value == event.studio:
                    self._takeover_state_value = None
                if self._release_state_value == event.studio:
                    self._release_state_value = None
                if self._immediate_state_value == event.studio:
                    self._stop_immediate_timers()
                    self._immediate_state_value = None
                    self._assure_hourly_timer()

            # Studio X drückt „Sofort“
            elif event.button is Button.immediate:
                # → Sofort-Status war noch nicht gesetzt
                if self._immediate_state_value is None:
                    # → Sofort-Status wird für das eigene Studio für die Dauer von 5 Minuten gesetzt
                    self._stop_immediate_timers()
                    self._immediate_state_value = event.studio
                    self._start_immediate_state_timer()

                # → Sofort-Status für das eigene Studio war schon gesetzt
                elif self._immediate_state_value == event.studio:
                    # → Sofort-Status wieder löschen
                    self._immediate_state_value = None
                    self._stop_immediate_timers()
                    self._assure_hourly_timer()

        # Zustand: Studio X ist on Air und drückt Buttons
        elif self._on_air_studio == event.studio:
            # Studio X drückt „Übernahme“
            if event.button is Button.takeover:
                # → Wenn Freigabe oder Sofort-Freigabe von uns schon erteilt
                if self._release_state_value == event.studio:
                    # → Noch keine andere Übernahme-Anforderung
                    if self._takeover_state_value is None:
                        # → Freigabe löschen
                        self._release_state_value = None

            # Studio X drückt „Freigabe“
            elif event.button is Button.release:
                # → Wenn kein Sofort-Status gesetzt
                if self._immediate_state_value is None:
                    # → Wenn noch nicht Freigabe erteilt
                    if self._release_state_value is None:
                        # → Freigabe erteilen → Zum Stundenwechsel wird umgeschaltet
                        self._release_state_value = event.studio
                    # → Wenn Freigabe schon erteilt
                    elif self._release_state_value == event.studio:
                        # → Übernahme noch nicht angefordert
                        if self._takeover_state_value is None:
                            # → Freigabe wieder löschen
                            self._release_state_value = None
                # → Wenn Sofort-Status gesetzt
                elif self._immediate_state_value == event.studio:
                    # → Noch keine Sofort-Freigabe gestartet
                    if self._release_state_value is None:
                        # → Sofort-Freigabe starten → Nach 30 Sekunden auf Automation umschalten
                        self._stop_hourly_timer()
                        self._release_state_value = event.studio
                        self._start_immediate_release_timer()
                    # → Sofort-Freigabe bereits gestartet
                    elif self._release_state_value == event.studio:
                        # → Sofort-Freigabe abbrechen
                        self._release_state_value = None
                        self._stop_immediate_release_timer()
                        self._assure_hourly_timer()

            # Studio X drück „Sofort-Button“
            elif event.button is Button.immediate:
                # → Wenn kein Sofort-Status gesetzt ist
                if self._immediate_state_value is None:
                    # → Sofort-Status setzen
                    self._immediate_state_value = event.studio
                    self._start_immediate_state_timer()
                # → Wenn Sofort-Status schon gesetzt
                elif self._immediate_state_value == event.studio:
                    # → Sofort-Status wieder löschen
                    self._immediate_state_value = None
                    self._stop_immediate_timers()
                    self._assure_hourly_timer()

        # Zustand: Studio X ist on Air und Studio Y drückt Buttons
        elif self._on_air_studio != event.studio:
            # Studio Y drückt „Übernahme“
            if event.button is Button.takeover:
                # → Wenn Sofort-Freigabe aktiviert ist
                if self._release_state_value == self._on_air_studio and self._immediate_state_value == self._on_air_studio:
                    # → Sofortige Übernahme
                    await self._do_immediate_takeover(event.studio)
                # Sonst
                else:
                    # → Wenn kein anderes Studio bereits Übernahme angefordert hat
                    if self._takeover_state_value is None:
                        # → Übernahme anfordern
                        self._takeover_state_value = event.studio
                    # → Wenn selbst schon Übernahme angefordert
                    elif self._takeover_state_value == event.studio:
                        # → Übernahme-Anforderung löschen
                        self._takeover_state_value = None

    def _assure_led_status(self):
        pass  # TODO

    def _audit_state(self):
        pass  # TODO

    async def _switch_to_studio(self, studio: Studio):
        logger.info('switch to studio %s', studio.name)
        self._on_air_studio = studio
        await self._set_current_state()

        self._takeover_state_value = None
        self._release_state_value = None
        self._stop_immediate_release_timer()
        self._assure_hourly_timer()

    async def _do_immediate_takeover(self, to_studio: Studio):
        self._takeover_state_value = None
        self._release_state_value = None
        self._immediate_state_value = None
        self._stop_timers()
        await self._switch_to_studio(to_studio)
        self._assure_hourly_timer()

    async def _assure_current_state_loop(self):
        while True:
            logger.info('assure current state')
            await self._symnet_controller.set_position(self._studios_to_selector_value[self._on_air_studio])
            await asyncio.sleep(300)

    async def _set_current_state(self, *args, **kwargs):
        await self._symnet_controller.set_position(self._studios_to_selector_value[self._on_air_studio])

    def _assure_hourly_timer(self):
        if self._hourly_timer and not self._hourly_timer.done():
            return

        self._hourly_timer = base.loop.create_task(self.__hour_timer())

    async def __hour_timer(self):
        logger.debug('start hour timer')

        while True:
            next_hour_timestamp = self.__calc_next_hour_timestamp()
            duration_to_next_hour = next_hour_timestamp - time.time()
            while duration_to_next_hour > 0:
                logger.debug('duration to next full hour %s', duration_to_next_hour)

                sleep_time = duration_to_next_hour
                if duration_to_next_hour > 2:
                    sleep_time = duration_to_next_hour - 2

                logger.debug('sleep time %s', sleep_time)
                await asyncio.sleep(sleep_time)
                duration_to_next_hour = next_hour_timestamp - time.time()

            logger.info('hourly event %s', time.strftime('%Y-%m-%dT%H:%M:%S%z'))
            with await self._immediate_release_lock:
                if self._on_air_studio == self._automat_studio:
                    if self._takeover_state_value is not None:
                        self._switch_to_studio(self._takeover_state_value)

                if self._on_air_studio == self._release_state_value:
                    if self._takeover_state_value is not None:
                        self._switch_to_studio(self._takeover_state_value)
                    else:
                        self._switch_to_studio(self._automat_studio)

            self._assure_led_status()
            self._audit_state()

            await asyncio.sleep(1)

    @staticmethod
    def __calc_next_hour_timestamp(minutes=9, seconds=0):
        next_datetime = datetime.datetime.now().replace(minute=minutes, second=seconds) + datetime.timedelta(hours=1)
        next_timestamp = next_datetime.timestamp()
        if next_timestamp - time.time() > 3600:
            next_timestamp -= 3600
        return next_timestamp

    def _start_immediate_state_timer(self):
        if self._immediate_state_timer is not None:
            logger.error('Called, but a timer is already running')
            return

        self._immediate_state_timer = base.loop.create_task(self.__immediate_state_timer())

    async def __immediate_state_timer(self):
        try:
            await asyncio.sleep(self.immediate_state_time)
            with await self._immediate_release_lock:
                self._immediate_state_value = None
                self._immediate_state_timer = None
        except asyncio.CancelledError:
            self._immediate_state_timer = None

    def _start_immediate_release_timer(self):
        if self._immediate_release_timer is not None:
            logger.error('Called, but a timer is already running')
            return

        self._immediate_release_timer = base.loop.create_task(self.__immediate_release_timer())

    async def __immediate_release_timer(self):
        try:
            with await self._immediate_release_lock:
                await asyncio.sleep(self.immediate_release_time)
                if self._takeover_state_value is None:
                    await self._switch_to_studio(self._automat_studio)
                else:
                    await self._switch_to_studio(self._takeover_state_value)
                self._takeover_state_value = None
                self._release_state_value = None
                self._immediate_state_value = None
        except asyncio.CancelledError:
            self._immediate_release_timer = None

    def _stop_timers(self):
        self._stop_hourly_timer()
        self._stop_immediate_timers()

    def _stop_hourly_timer(self):
        if self._hourly_timer:
            self._hourly_timer.cancel()
            self._hourly_timer = None

    def _stop_immediate_timers(self):
        self._stop_immediate_state_timer()
        self._stop_immediate_release_timer()

    def _stop_immediate_state_timer(self):
        if self._immediate_state_timer:
            self._immediate_state_timer.cancel()
            self._immediate_state_timer = None

    def _stop_immediate_release_timer(self):
        if self._immediate_release_timer:
            self._immediate_release_timer.cancel()
            self._immediate_release_timer = None
