import asyncio
import datetime
import json
import logging
import random
import time
import typing
import weakref

from transitions import EventData, MachineError

import bermudafunk.SymNet
from bermudafunk import base
from bermudafunk.dispatcher.data_types import Studio, StudioLedStatus, LedStatus, ButtonEvent, Button, DispatcherStudioDefinition
from bermudafunk.dispatcher.transitions import LedAwareMachine as Machine, LedAwareState, LedStateTarget, States

logger = logging.getLogger(__name__)

audit_logger = logging.Logger(__name__)
if not audit_logger.hasHandlers():
    import sys

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    audit_logger.addHandler(stdout_handler)

_save_state = typing.NamedTuple('_save_state', [('x', str), ('y', str), ('state', str)])


class Dispatcher:
    AUTOMAT = 'automat'

    def __init__(self,
                 symnet_controller: bermudafunk.SymNet.SymNetSelectorController,
                 automat_selector_value: int,
                 studio_mapping: typing.List[DispatcherStudioDefinition],
                 audit_internal_state=False
                 ):

        self.file_path = 'state.json'

        if audit_internal_state:
            def _x_get(_self):
                return _self.__x

            def _x_set(_self, new_val: Studio):
                if _self.__x is new_val:
                    return
                import inspect
                stack = inspect.stack()
                logger.debug('stack %s', stack[1].lineno)
                logger.debug('change _x to %s', new_val)
                _self.__x = new_val

            def _y_get(_self):
                return _self.__y

            def _y_set(_self, new_val: Studio):
                if _self.__y is new_val:
                    return
                import inspect
                stack = inspect.stack()
                logger.debug('stack %s', stack[1].lineno)
                logger.debug('change _y to %s', new_val)
                _self.__y = new_val

            def _on_air_selector_value_get(_self):
                return _self.__on_air_selector_value

            def _on_air_selector_value_set(_self, new_val: int):
                if _self.__on_air_selector_value is new_val:
                    return
                logger.debug('change _on_air_selector_value to %s', new_val)
                _self.__on_air_selector_value = new_val

            Dispatcher._x = property(_x_get, _x_set)
            Dispatcher._y = property(_y_get, _y_set)
            Dispatcher._on_air_selector_value = property(_on_air_selector_value_get, _on_air_selector_value_set)

        self.immediate_state_time = 5 * 60  # seconds
        self.immediate_release_time = 30  # seconds

        self._symnet_controller = symnet_controller

        self._next_hour_timer = None  # type: typing.Optional[asyncio.Task]
        self._immediate_state_timer = None  # type: typing.Optional[asyncio.Task]
        self._immediate_release_timer = None  # type: typing.Optional[asyncio.Task]

        self._dispatcher_button_event_queue = asyncio.Queue(maxsize=1, loop=base.loop)

        self._automat_selector_value = automat_selector_value

        self._studios = []  # type: typing.List[Studio]
        self._studios_to_selector_value = {}  # type: typing.Dict[Studio, int]
        self._selector_value_to_studio = {}  # type: typing.Dict[int, Studio]
        for studio_def in studio_mapping:
            assert studio_def.selector_value not in self._selector_value_to_studio.keys()
            self._studios.append(studio_def.studio)
            self._studios_to_selector_value[studio_def.studio] = studio_def.selector_value
            self._selector_value_to_studio[studio_def.selector_value] = studio_def.studio
            studio_def.studio.dispatcher_button_event_queue = self._dispatcher_button_event_queue

        assert self._automat_selector_value not in self._selector_value_to_studio.keys()
        assert Dispatcher.AUTOMAT not in self._studios_to_selector_value.keys()

        # State machine values

        self.__on_air_selector_value = 0  # type: int
        self._on_air_selector_value = self._automat_selector_value
        self.__x = None
        self.__y = None
        self._x = None  # type: typing.Optional[Studio]
        self._y = None  # type: typing.Optional[Studio]

        # State machine initialization

        states = [state.value for _, state in States.__members__.items()]

        self._machine = Machine(states=states,
                                initial='automat_on_air',
                                ignore_invalid_triggers=True,
                                send_event=True,
                                before_state_change=[self._before_state_change],
                                after_state_change=[self._after_state_change],
                                finalize_event=[self._audit_state, self._assure_led_status, self._notify_machine_observers]
                                )

        dispatcher_transitions = [
            {'trigger': 'takeover_X', 'source': States.AUTOMAT_ON_AIR, 'dest': States.FROM_AUTOMAT_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR},
            {'trigger': 'immediate_X', 'source': States.AUTOMAT_ON_AIR, 'dest': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X},

            {'trigger': 'takeover_X', 'source': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X, 'dest': States.STUDIO_X_ON_AIR},
            {'trigger': 'release_X', 'source': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X, 'dest': States.AUTOMAT_ON_AIR},
            {'trigger': 'immediate_X', 'source': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X, 'dest': States.AUTOMAT_ON_AIR},
            {'trigger': 'immediate_state_timeout', 'source': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X, 'dest': States.AUTOMAT_ON_AIR},

            {'trigger': 'takeover_X', 'source': States.FROM_AUTOMAT_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR, 'dest': States.AUTOMAT_ON_AIR},
            {'trigger': 'release_X', 'source': States.FROM_AUTOMAT_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR, 'dest': States.AUTOMAT_ON_AIR},
            {'trigger': 'next_hour', 'source': States.FROM_AUTOMAT_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR},

            {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR, 'dest': States.FROM_STUDIO_X_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR},
            {'trigger': 'immediate_X', 'source': States.STUDIO_X_ON_AIR, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE},
            {'trigger': 'takeover_Y', 'source': States.STUDIO_X_ON_AIR, 'dest': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST},

            {'trigger': 'takeover_X', 'source': States.FROM_STUDIO_X_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR},
            {'trigger': 'release_X', 'source': States.FROM_STUDIO_X_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR},
            {'trigger': 'takeover_Y', 'source': States.FROM_STUDIO_X_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.FROM_STUDIO_X_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR},
            {'trigger': 'next_hour', 'source': States.FROM_STUDIO_X_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.AUTOMAT_ON_AIR},

            {'trigger': 'immediate_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR},
            {'trigger': 'immediate_state_timeout', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR},
            {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE},

            {'trigger': 'takeover_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE},
            {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE},
            {'trigger': 'takeover_Y', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR, 'before': [self._prepare_change_to_y]},
            {'trigger': 'immediate_release_timeout', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.AUTOMAT_ON_AIR},

            {'trigger': 'takeover_Y', 'source': States.FROM_STUDIO_X_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR, 'dest': States.FROM_STUDIO_X_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR},
            {'trigger': 'release_Y', 'source': States.FROM_STUDIO_X_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR, 'dest': States.FROM_STUDIO_X_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR},
            {'trigger': 'next_hour', 'source': States.FROM_STUDIO_X_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR, 'before': [self._prepare_change_to_y]},

            {'trigger': 'takeover_Y', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST, 'dest': States.STUDIO_X_ON_AIR},
            {'trigger': 'release_Y', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST, 'dest': States.STUDIO_X_ON_AIR},
            {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST, 'dest': States.FROM_STUDIO_X_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR},
        ]

        for transition in dispatcher_transitions:
            for name, value in transition.items():
                if isinstance(value, States):
                    transition[name] = value.value
            self._machine.add_transition(**transition)

        for _, button in Button.__members__.items():
            for kind in ['X', 'Y']:
                trigger_name = button.name + '_' + kind
                if trigger_name not in self._machine.events.keys():
                    self._machine.add_transition(trigger=trigger_name, source='noop', dest='noop')  # noops to complete all combinations of buttons presses

        self._machine.on_enter_automat_on_air(self._change_to_automat)
        self._machine.on_enter_studio_X_on_air(self._change_to_studio)

        # Start timers
        self._symnet_controller.add_observer(self._set_current_state)
        base.start_cleanup_aware_coroutine(self._assure_current_state_loop)
        base.start_cleanup_aware_coroutine(self._process_studio_button_events)
        base.cleanup_tasks.append(base.loop.create_task(self._cleanup()))

        self._machine_observers = weakref.WeakSet()  # type: typing.Set[typing.Callable[Dispatcher]]

    def _notify_machine_observers(self, event: EventData):
        for observer in self._machine_observers:
            observer(self, event=event)

    @property
    def machine_observers(self):
        return self._machine_observers

    @property
    def on_air_studio_name(self):
        if self._on_air_selector_value == self._automat_selector_value:
            return Dispatcher.AUTOMAT
        return self._selector_value_to_studio[self._on_air_selector_value].name

    @property
    def machine(self) -> Machine:
        return self._machine

    @property
    def studios(self) -> typing.List[Studio]:
        return self._studios

    def _prepare_change_to_y(self, _: EventData = None):
        self._x, self._y = self._y, None

    def _change_to_automat(self, _: EventData):
        logger.debug('change to automat')
        self._on_air_selector_value = self._automat_selector_value
        base.loop.create_task(self._set_current_state())

    def _change_to_studio(self, _: EventData):
        logger.debug('change to studio %s', self._x)
        self._on_air_selector_value = self._studios_to_selector_value[self._x]
        base.loop.create_task(self._set_current_state())

    def _before_state_change(self, event: EventData):
        if event.transition.dest is None:  # internal transition, don't do anything right now
            return

        # check if button event
        if 'button_event' in event.kwargs.keys():
            button_event = event.kwargs.get('button_event')  # type: ButtonEvent
            event_name = event.event.name
            if 'X' in event_name:
                self._x = button_event.studio
            elif 'Y' in event_name:
                self._y = button_event.studio

        source_state = event.transition.source
        if 'next_hour' in source_state:
            self._stop_next_hour_timer()
        elif 'immediate_state' in source_state:
            self._stop_immediate_state_timer()
        elif 'immediate_release' in source_state:
            self._stop_immediate_release_timer()

    def _after_state_change(self, event: EventData):
        if event.transition.dest is None:  # internal transition, don't do anything right now
            return

        for tmp in ['X', 'Y']:
            if event.transition.dest and tmp not in event.transition.dest:
                setattr(self, '_' + tmp.lower(), None)

        # start timers
        destination_state = event.transition.dest
        if 'next_hour' in destination_state:
            self._start_next_hour_timer()
        elif 'immediate_state' in destination_state:
            self._start_immediate_state_timer()
        elif 'immediate_release' in destination_state:
            self._start_immediate_release_timer()

    async def _cleanup(self):
        await base.cleanup_event.wait()
        logger.debug('cleanup timers')
        self._stop_next_hour_timer()
        self._stop_immediate_state_timer()
        self._stop_immediate_release_timer()
        self.save()

    async def _process_studio_button_events(self):
        while True:
            event = await self._dispatcher_button_event_queue.get()  # type: ButtonEvent
            logger.debug('got new event %s, process now', event)

            append = None
            if self._x is None:
                append = '_X'
            else:
                if self._x == event.studio:
                    append = '_X'
                else:
                    if self._y is None or self._y == event.studio:
                        append = '_Y'

            if append:
                trigger_name = event.button.name + append
                logger.debug('state %s', {'state': self._machine.state, 'x': self._x, 'y': self._y})
                logger.debug('trigger_name trying to call %s', trigger_name)
                try:
                    self._machine.trigger(trigger_name, button_event=event)
                except MachineError as e:
                    logger.info(e)
                    # TODO: Signal error
                    pass

            self._audit_state()
            self._assure_led_status()

    def _assure_led_status(self, _: EventData = None):
        logger.debug('assure led status')
        new_led_state = self._machine.get_state(self._machine.state).led_state_target  # type: LedStateTarget
        for studio in self._studios:
            if studio == self._x:
                logger.debug(new_led_state.x)
                studio.led_status_typed = new_led_state.x
            elif studio == self._y:
                studio.led_status_typed = new_led_state.y
            else:
                studio.led_status_typed = new_led_state.other

    def _audit_state(self, _: EventData = None):
        state = self._machine.state
        if 'X' in state:
            if self._x is None:
                logger.critical('X in state and self._X is None')
        else:
            if self._x is not None:
                logger.critical('X not in state and self._X is not None')

        if 'Y' in state:
            if self._y is None:
                logger.critical('Y in state and self._Y is None')
        else:
            if self._y is not None:
                logger.critical('Y not in state and self._Y is not None')

    async def _assure_current_state_loop(self):
        while True:
            logger.debug('Assure that the controller have the desired state!')
            await self._set_current_state()
            sleep_time = random.randint(300, 600)
            logger.debug('Sleep for %s seconds', sleep_time)
            await asyncio.sleep(sleep_time)

    async def _set_current_state(self, *_, **__):
        logger.info('Set the controller state now to %s!', self._automat_selector_value)
        await self._symnet_controller.set_position(self._automat_selector_value)

    def _start_next_hour_timer(self, _: EventData = None):
        if self._next_hour_timer and not self._next_hour_timer.done():
            return

        self._next_hour_timer = base.loop.create_task(self.__hour_timer())

    async def __hour_timer(self):
        logger.debug('start hour timer')

        try:
            next_hour_timestamp = calc_next_hour_timestamp()
            duration_to_next_hour = next_hour_timestamp - time.time()
            while duration_to_next_hour > 0.3:
                logger.debug('duration to next full hour %s', duration_to_next_hour)

                sleep_time = duration_to_next_hour - 0.3
                if duration_to_next_hour > 2:
                    sleep_time = duration_to_next_hour - 2
                    logger.debug('sleep time %s', sleep_time)
                    await asyncio.sleep(sleep_time)
                else:
                    logger.debug('sleep time %s', sleep_time)
                    await asyncio.sleep(sleep_time)
                    break
                duration_to_next_hour = next_hour_timestamp - time.time()

            logger.info('hourly event %s', time.strftime('%Y-%m-%dT%H:%M:%S%z'))
            try:
                self._machine.next_hour()
            except MachineError as e:
                logger.critical(e)

            self._assure_led_status()
        finally:
            self._next_hour_timer = None

    def _stop_next_hour_timer(self, _: EventData = None):
        if self._next_hour_timer:
            logger.debug('stop next hour timer')
            self._next_hour_timer.cancel()
            self._next_hour_timer = None

    def _start_immediate_state_timer(self, _: EventData = None):
        if self._immediate_state_timer and not self._immediate_state_timer.done():
            return

        self._immediate_state_timer = base.loop.create_task(self.__immediate_state_timer())

    async def __immediate_state_timer(self):
        logger.debug('start immediate state timer')

        try:
            await asyncio.sleep(self.immediate_state_time)
            try:
                self._machine.immediate_state_timeout()
            except MachineError as e:
                logger.critical(e)
        finally:
            self._immediate_state_timer = None

    def _stop_immediate_state_timer(self, _: EventData = None):
        if self._immediate_state_timer:
            logger.debug('stop immediate state timer')
            self._immediate_state_timer.cancel()
            self._immediate_state_timer = None

    def _start_immediate_release_timer(self, _: EventData = None):
        logger.debug('start immediate release timer')

        if self._immediate_release_timer and self._immediate_release_timer.done():
            return

        self._immediate_release_timer = base.loop.create_task(self.__immediate_release_timer())

    async def __immediate_release_timer(self):
        try:
            await asyncio.sleep(self.immediate_release_time)
            try:
                self._machine.immediate_release_timeout()
            except MachineError as e:
                logger.critical(e)
        finally:
            self._immediate_release_timer = None

    def _stop_immediate_release_timer(self, _: EventData = None):
        if self._immediate_release_timer:
            logger.debug('stop immediate release timer')
            self._immediate_release_timer.cancel()
            self._immediate_release_timer = None

    @property
    def status(self):
        return {
            'state': self.machine.state,
            'on_air_studio': self.on_air_studio_name,
            'x': self._x.name if self._x else None,
            'y': self._y.name if self._y else None,
        }

    def load(self):
        try:
            with open(self.file_path, 'r') as fp:
                state = json.load(fp)
                state = _save_state(**state)
                logger.debug(state)

            if state.x:
                self._x = Studio.names[state.x]
                if state.y:
                    self._y = Studio.names[state.y]
            self._machine.trigger('to_' + state.state)
        except IOError as e:
            if e.errno == 2:
                logger.warning('Could load dispatcher state: %s', e)
            else:
                logger.critical('Could load dispatcher state: %s', e)
        except json.JSONDecodeError:
            logger.critical('Could load dispatcher state: %s', e)

    def save(self):
        state = _save_state(
            x=self._x.name if self._x else None,
            y=self._y.name if self._y else None,
            state=self._machine.state
        )
        logger.debug(state)
        try:
            with open(self.file_path, 'w') as fp:
                json.dump(state._asdict(), fp)
        except Exception as e:
            logger.error(e)


def calc_next_hour_timestamp(minutes=0, seconds=0):
    next_datetime = datetime.datetime.now().replace(minute=minutes, second=seconds) + datetime.timedelta(hours=1)
    next_timestamp = next_datetime.timestamp()
    if next_timestamp - time.time() > 3600:
        next_timestamp -= 3600
    return next_timestamp
