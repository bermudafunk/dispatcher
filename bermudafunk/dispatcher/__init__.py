import asyncio
import datetime
import enum
import logging
import time
import typing
from collections import namedtuple

import bermudafunk.SymNet
from bermudafunk import GPIO, base

logger = logging.getLogger(__name__)

audit_logger = logging.Logger(__name__)
if not audit_logger.hasHandlers():
    import sys

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    audit_logger.addHandler(stdout_handler)


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

        self._takeover_led = takeover_led if takeover_led else GPIO.DummyLed()
        self._release_led = release_led if release_led else GPIO.DummyLed()
        self._immediate_led = immediate_led if immediate_led else GPIO.DummyLed()

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
    def takeover_led(self) -> GPIO.DummyLed:
        return self._takeover_led

    @property
    def release_led(self) -> GPIO.DummyLed:
        return self._release_led

    @property
    def immediate_led(self) -> GPIO.DummyLed:
        return self._immediate_led

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


ButtonEvent = typing.NamedTuple('ButtonEvent', [('studio', Studio), ('button', Button)])


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

        self._automat_studio = Studio('automat')
        studio_mapping = list(studio_mapping) + [
            DispatcherStudioDefinition(studio=self._automat_studio, selector_value=automat_selector_value)
        ]

        self._dispatcher_button_event_queue = asyncio.Queue(maxsize=1, loop=base.loop)

        self._studios = []  # type: typing.List[Studio]
        self._studios_to_selector_value = {}  # type: typing.Dict[Studio, int]
        self._selector_value_to_studio = {}  # type: typing.Dict[int, Studio]
        for studio_def in studio_mapping:
            self._studios.append(studio_def.studio)
            self._studios_to_selector_value[studio_def.studio] = studio_def.selector_value
            self._selector_value_to_studio[studio_def.selector_value] = studio_def.studio
            studio_def.studio.dispatcher_button_event_queue = self._dispatcher_button_event_queue

        self._on_air_studio = self._automat_studio

        self._symnet_controller.add_observer(self._set_current_state)
        base.start_cleanup_aware_coro(self._assure_current_state_loop)
        base.start_cleanup_aware_coro(self._process_studio_button_events)
        base.cleanup_tasks.append(base.loop.create_task(self._cleanup()))

        self._assure_hourly_timer()

    async def _cleanup(self):
        await base.cleanup_event.wait()
        logger.debug('cleanup timers')
        self._stop_timers()

    async def _process_studio_button_events(self):
        while True:
            event = await self._dispatcher_button_event_queue.get()  # type: ButtonEvent
            logger.debug('got new event %s, process now', event)

            await self._change_state(event)

            self._assure_led_status()

            self._audit_state()

    async def _change_state(self, event: ButtonEvent):
        if self._on_air_studio == self._automat_studio:
            audit_logger.info("Zustand: Automation on Air")
            if event.button is Button.takeover:
                audit_logger.info("Studio X drückt „Übernahme“")
                if self._immediate_state_value is None:
                    audit_logger.info("→ nicht „Sofort-Status“")
                    if self._takeover_state_value is None:
                        audit_logger.info("→ noch nicht von anderswo angefordert")
                        audit_logger.info("→ Übernahme anfordern → zum Stundenwechsel wird hierher umgeschaltet")
                        self._takeover_state_value = event.studio
                    elif self._takeover_state_value == event.studio:
                        audit_logger.info("→ schon vom eigenen Studio Übernahme angefordert")
                        audit_logger.info("→ Anforderung löschen")
                        self._takeover_state_value = None
                elif self._immediate_state_value == event.studio:
                    audit_logger.info("→ schon „Sofort-Status“ vom eigenen Studio aktiviert")
                    audit_logger.info("→ sofortige Übernahme")
                    await self._do_immediate_takeover(event.studio)

            elif event.button is Button.release:
                audit_logger.info("Studio X drückt „Freigabe“")
                audit_logger.info("→ Rücksetzung aller eigenen Anforderungen (Übernahme/ Sofort-Status)")
                if self._takeover_state_value == event.studio:
                    self._takeover_state_value = None
                if self._release_state_value == event.studio:
                    self._release_state_value = None
                if self._immediate_state_value == event.studio:
                    self._stop_immediate_timers()
                    self._immediate_state_value = None
                    self._assure_hourly_timer()

            elif event.button is Button.immediate:
                audit_logger.info("Studio X drückt „Sofort“")
                if self._immediate_state_value is None:
                    audit_logger.info("→ Sofort-Status war noch nicht gesetzt")
                    audit_logger.info("→ Sofort-Status wird für das eigene Studio für die Dauer von 5 Minuten gesetzt")
                    self._stop_immediate_timers()
                    self._immediate_state_value = event.studio
                    self._start_immediate_state_timer()

                elif self._immediate_state_value == event.studio:
                    audit_logger.info("→ Sofort-Status für das eigene Studio war schon gesetzt")
                    audit_logger.info("→ Sofort-Status wieder löschen")
                    self._immediate_state_value = None
                    self._stop_immediate_timers()
                    self._assure_hourly_timer()

        elif self._on_air_studio == event.studio:
            audit_logger.info("Zustand: Studio X ist on Air und drückt Buttons")
            if event.button is Button.takeover:
                audit_logger.info("Studio X drückt „Übernahme“")
                if self._release_state_value == event.studio:
                    audit_logger.info("→ Wenn Freigabe oder Sofort-Freigabe von uns schon erteilt")
                    if self._takeover_state_value is None:
                        audit_logger.info("→ Noch keine andere Übernahme-Anforderung")
                        audit_logger.info("→ Freigabe löschen")
                        self._release_state_value = None

            elif event.button is Button.release:
                audit_logger.info("Studio X drückt „Freigabe“")
                if self._immediate_state_value is None:
                    audit_logger.info("→ Wenn kein Sofort-Status gesetzt")
                    if self._release_state_value is None:
                        audit_logger.info("→ Wenn noch nicht Freigabe erteilt")
                        audit_logger.info("→ Freigabe erteilen → Zum Stundenwechsel wird umgeschaltet")
                        self._release_state_value = event.studio
                    elif self._release_state_value == event.studio:
                        audit_logger.info("→ Wenn Freigabe schon erteilt")
                        if self._takeover_state_value is None:
                            audit_logger.info("→ Übernahme noch nicht angefordert")
                            audit_logger.info("→ Freigabe wieder löschen")
                            self._release_state_value = None
                elif self._immediate_state_value == event.studio:
                    audit_logger.info("→ Wenn Sofort-Status gesetzt")
                    if self._release_state_value is None:
                        audit_logger.info("→ Noch keine Sofort-Freigabe gestartet")
                        audit_logger.info("→ Sofort-Freigabe starten → Nach 30 Sekunden auf Automation umschalten")
                        self._stop_hourly_timer()
                        self._release_state_value = event.studio
                        self._start_immediate_release_timer()
                    elif self._release_state_value == event.studio:
                        audit_logger.info("→ Sofort-Freigabe bereits gestartet")
                        audit_logger.info("→ Sofort-Freigabe abbrechen")
                        self._release_state_value = None
                        self._stop_immediate_release_timer()
                        self._assure_hourly_timer()

            elif event.button is Button.immediate:
                audit_logger.info("Studio X drück „Sofort-Button“")
                if self._immediate_state_value is None:
                    audit_logger.info("→ Wenn kein Sofort-Status gesetzt ist")
                    audit_logger.info("→ Sofort-Status setzen")
                    self._immediate_state_value = event.studio
                    self._start_immediate_state_timer()
                elif self._immediate_state_value == event.studio:
                    audit_logger.info("→ Wenn Sofort-Status schon gesetzt")
                    audit_logger.info("→ Sofort-Status wieder löschen")
                    self._immediate_state_value = None
                    self._stop_immediate_timers()
                    self._assure_hourly_timer()

        elif self._on_air_studio != event.studio:
            audit_logger.info("Zustand: Studio X ist on Air und Studio Y drückt Buttons")
            if event.button is Button.takeover:
                audit_logger.info("Studio Y drückt „Übernahme“")
                if self._release_state_value == self._on_air_studio and self._immediate_state_value == self._on_air_studio:
                    audit_logger.info("→ Wenn Sofort-Freigabe aktiviert ist")
                    audit_logger.info("→ Sofortige Übernahme")
                    await self._do_immediate_takeover(event.studio)
                else:
                    audit_logger.info("Sonst")
                    if self._takeover_state_value is None:
                        audit_logger.info("→ Wenn kein anderes Studio bereits Übernahme angefordert hat")
                        audit_logger.info("→ Übernahme anfordern")
                        self._takeover_state_value = event.studio
                    elif self._takeover_state_value == event.studio:
                        audit_logger.info("→ Wenn selbst schon Übernahme angefordert")
                        audit_logger.info("→ Übernahme-Anforderung löschen")
                        self._takeover_state_value = None

    def _assure_led_status(self):
        pass  # TODO

    def _audit_state(self):
        pass  # TODO

    async def _switch_to_studio(self, studio: Studio):
        logger.info('Wechsel zu Studio %s', studio)
        audit_logger.warning('Wechsel zu Studio %s', studio)

        self._on_air_studio = studio
        await self._set_current_state()

        self._takeover_state_value = None
        self._release_state_value = None
        self._stop_immediate_release_timer()
        self._assure_hourly_timer()

    async def _do_immediate_takeover(self, to_studio: Studio):
        logger.info('Sofort-Wechsel zu Studio %s', to_studio)
        audit_logger.warning('Sofort-Wechsel zu Studio %s', to_studio)
        self._takeover_state_value = None
        self._release_state_value = None
        self._immediate_state_value = None
        self._stop_timers()
        await self._switch_to_studio(to_studio)
        self._assure_hourly_timer()

    async def _assure_current_state_loop(self):
        while True:
            logger.debug('Assure that the controller have the desired state!')
            await self._symnet_controller.set_position(self._studios_to_selector_value[self._on_air_studio])
            await asyncio.sleep(300)

    async def _set_current_state(self, *args, **kwargs):
        logger.debug('The the controller state now!')
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
    def __calc_next_hour_timestamp(minutes=0, seconds=0):
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
