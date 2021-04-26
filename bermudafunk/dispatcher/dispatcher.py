import asyncio
import json
import logging
import random
import typing
import weakref
from datetime import datetime

import attr
from dateutil import tz
from transitions import EventData, MachineError

from bermudafunk import base
from bermudafunk import symnet
from bermudafunk.dispatcher.data_types import BaseStudio, ButtonEvent, DispatcherStudioDefinition, Studio
from bermudafunk.dispatcher.transitions import LampAwareMachine as Machine, LampStateTarget, load_timers_states_transitions
from bermudafunk.dispatcher.utils import calc_next_hour
from bermudafunk.io import common

logger = logging.getLogger(__name__)

audit_logger = logging.Logger(__name__)
if not audit_logger.hasHandlers():
    import sys

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    audit_logger.addHandler(stdout_handler)


class Dispatcher:
    """
    This is the main state machine handler of bermudafunk

    A state can be build up from at most two studios. The first studio is called X, the second one is called Y.
    If the automat isn't on air, studio X is always the studio which could be currently on air.
    Studio Y is only able to signal takeover requests.

    There are three timers which could be used:
    - the hourly timer which sends triggers the 'next_hour' event
    - two timeout timers:
        - the immediate state, triggers 'immediate_state_timeout'
        - the immediate release, triggers 'immediate_release_timeout'
    They are activated if the name of the timer is contained in the state name.
    The timers are not reset if the name of the timer is in both src and dest state name.
    """

    @attr.s(frozen=True, slots=True, auto_attribs=True)
    class _SaveState:
        x: str
        y: str
        state: str

    def __init__(
        self,
        symnet_controller: symnet.SymNetSelectorController,
        automat: DispatcherStudioDefinition,
        dispatcher_studios: typing.List[DispatcherStudioDefinition],
        audit_internal_state=False,
    ):

        self.file_path = 'state.json'

        # convert _x, _y and _on_air_selector_value to properties to audit their values
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

        self._symnet_controller = symnet_controller

        # task holders
        self._next_hour_timer: typing.Optional[asyncio.Task] = None
        self._timer_tasks: typing.Dict[str, asyncio.Task] = {}
        self._signal_error_task: typing.Optional[asyncio.Task] = None

        # collecting button presses
        self._dispatcher_button_event_queue: asyncio.Queue = asyncio.Queue(maxsize=1, loop=base.loop)

        # the value of the automat source in the SymNetSelectorController
        if not 1 <= automat.selector_value <= symnet_controller.position_count:
            raise ValueError(
                "Automat selector value have to be in the range of valid selector values "
                f"[1, {symnet_controller.position_count}]: {automat.selector_value} was given"
            )
        self._automat = automat

        # studios to switch between and automat
        self._studios: typing.List[BaseStudio] = []
        # caching dictionaries to provide lookups
        self._studios_to_selector_value: typing.Dict[BaseStudio, int] = {}
        self._selector_value_to_studio: typing.Dict[int, BaseStudio] = {}
        for dispatcher_studio in dispatcher_studios:
            assert dispatcher_studio.selector_value not in self._selector_value_to_studio.keys()
            self._studios.append(dispatcher_studio.studio)
            self._studios_to_selector_value[dispatcher_studio.studio] = dispatcher_studio.selector_value
            self._selector_value_to_studio[dispatcher_studio.selector_value] = dispatcher_studio.studio
            dispatcher_studio.studio.dispatcher_button_event_queue = self._dispatcher_button_event_queue

        if self._automat.selector_value in self._selector_value_to_studio.keys():
            raise ValueError("Automat selector value als assigned to studio {}".format(
                self._selector_value_to_studio[self._automat.selector_value].name))
        if self._automat.studio in self._studios_to_selector_value.keys():
            raise ValueError("A studio has the magic studio name 'automat'")

        # on air selector value hold the value we expect to be set in the SymNetSelectorController
        self.__on_air_selector_value: int = 0
        self._on_air_selector_value = self._automat.selector_value

        # == State machine initialization ==

        # = State machine values =
        # Studio X
        self.__x = None
        self._x: typing.Optional[Studio] = None
        # Studio Y
        self.__y = None
        self._y: typing.Optional[Studio] = None

        self._timers, states, transitions = load_timers_states_transitions()

        states['automat_on_air'].add_callback('enter', self._change_to_automat)
        states['studio_X_on_air'].add_callback('enter', self._change_to_studio)

        # Initialize the underlying transitions machine
        self._machine = Machine(
            states=list(states.values()),
            initial=states['automat_on_air'],
            send_event=True,
            before_state_change=[self._before_state_change],
            after_state_change=[self._after_state_change],
            finalize_event=[self._audit_state, self._assure_lamp_state, self._notify_machine_observers],
            show_state_attributes=True,
        )

        # Add the transitions between the states to the machine
        for transition in transitions:
            if 'switch_xy' in transition:
                if transition['switch_xy']:
                    if 'before' not in transition:
                        transition['before'] = []
                    transition['before'].append(self._switch_xy)
                del transition['switch_xy']
            self._machine.add_transition(**transition)

        self._machine_observers: typing.Set[typing.Callable[[Dispatcher, EventData], typing.Any]] = weakref.WeakSet()

        self._started = False

    def start(self):
        """Start the long running dispatcher tasks"""
        if self._started:
            return
        self._started = True

        # Start timers
        self._symnet_controller.add_observer(self._set_current_state)
        base.start_cleanup_aware_coroutine(self._assure_current_state_loop)
        base.start_cleanup_aware_coroutine(self._process_studio_button_events)
        base.cleanup_tasks.append(base.loop.create_task(self._cleanup()))

    def _notify_machine_observers(self, event: EventData):
        for observer in self._machine_observers:
            observer(self, event)

    @property
    def machine_observers(self):
        return self._machine_observers

    @property
    def on_air_studio_name(self) -> str:
        if self._on_air_selector_value == self._automat.selector_value:
            return self._automat.studio.name
        return self._selector_value_to_studio[self._on_air_selector_value].name

    @property
    def machine(self) -> Machine:
        return self._machine

    @property
    def studios(self) -> typing.List[BaseStudio]:
        return self._studios

    @property
    def studios_with_automat(self) -> typing.List[BaseStudio]:
        return [self._automat.studio] + self._studios

    def _switch_xy(self, _: EventData = None):
        self._x, self._y = self._y, self._x

    def _change_to_automat(self, _: EventData = None):
        logger.debug('change to automat')
        self._on_air_selector_value = self._automat.selector_value
        base.loop.create_task(self._set_current_state())

    def _change_to_studio(self, _: EventData = None):
        logger.debug('change to studio %s', self._x)
        self._on_air_selector_value = self._studios_to_selector_value[self._x]
        base.loop.create_task(self._set_current_state())

    def _before_state_change(self, event: EventData):
        if event.transition.dest is None:  # internal transition, don't do anything right now
            return

        # check if button event
        if 'button_event' in event.kwargs.keys():
            button_event: ButtonEvent = event.kwargs.get('button_event')
            event_name = event.event.name
            # set the studio accordingly
            if 'X' in event_name:
                self._x = button_event.studio
            elif 'Y' in event_name:
                self._y = button_event.studio

        # stop timers if the destination event doesn't require them
        destination_state = event.transition.dest
        if 'next_hour' not in destination_state:
            self._stop_next_hour_timer()
        for timer in self._timers:
            if timer not in destination_state:
                self._stop_timer(timer)

    def _after_state_change(self, event: EventData):
        if event.transition.dest is None:  # internal transition, don't do anything right now
            return

        # if the destination state doesn't require a studio, set it to None
        for tmp in ['X', 'Y']:
            if event.transition.dest and tmp not in event.transition.dest:
                setattr(self, '_' + tmp.lower(), None)

        # start timers as needed
        destination_state = event.transition.dest
        if 'next_hour' in destination_state:
            self._start_next_hour_timer()
        for timer in self._timers:
            if timer in destination_state:
                self._start_timer(timer)

    async def _cleanup(self):
        await base.cleanup_event.wait()
        logger.debug('cleanup timers')
        self._stop_next_hour_timer()
        for timer in self._timers:
            self._stop_timer(timer)
        self.save()

    async def _process_studio_button_events(self):
        while True:
            event: ButtonEvent = await self._dispatcher_button_event_queue.get()
            logger.debug('got new event %s, process now', event)

            # a studio is active, to be the X event the button has to be pressed in the X studio
            if self._x is None or self._x == event.studio:
                append = '_X'
            elif self._y is None or self._y == event.studio:
                append = '_Y'
            else:
                append = '_other'

            # if the button press can be mapped to a studio trigger the machine
            trigger_name = event.button.name + append
            logger.debug('state %s', {'state': self._machine.state, 'x': self._x, 'y': self._y})
            logger.debug('trigger_name trying to call %s', trigger_name)
            # noinspection PyBroadException
            try:
                self._machine.trigger(trigger_name, button_event=event)
            except:
                logger.warning("Unable to process trigger %s of studio %s", trigger_name, event.studio.name)
                self._signal_error_task = base.loop.create_task(self._signal_error(event.studio))
                continue
            finally:
                self._audit_state()

            self._assure_lamp_state()

    async def _signal_error(self, studio: Studio):
        studio.immediate_lamp.color_lamp_state = common.TriColorLampState(
            state=common.LampState.BLINK_REALLY_FAST,
            color=common.TriColorLampColor.RED,
        )
        await asyncio.sleep(1)
        self._assure_lamp_state()

    def _assure_lamp_state(self, _: EventData = None):
        """Set the lamp state in studios"""
        logger.debug('assure lamp status')
        if self._signal_error_task:
            self._signal_error_task.cancel()
            self._signal_error_task = None
        lamp_state_target: LampStateTarget = self._machine.get_state(self._machine.state).lamp_state_target
        self._automat.studio.lamp_state = lamp_state_target.automat
        for studio in self._studios:
            if studio == self._x:
                studio.lamp_state = lamp_state_target.x
            elif studio == self._y:
                studio.lamp_state = lamp_state_target.y
            else:
                studio.lamp_state = lamp_state_target.other

    def _audit_state(self, _: EventData = None):
        """Assure the required studios and only these are set"""
        logger.debug("Audit state")
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
        """In case something is going terrible wrong regarding the communication with the SymNetController, just the value again on a regular time frame"""
        while True:
            logger.debug('Assure that the controller have the desired state!')
            await self._set_current_state()
            sleep_time = random.randint(300, 600)
            logger.debug('Sleep for %s seconds', sleep_time)
            await asyncio.sleep(sleep_time)

    async def _set_current_state(self, *_, **__):
        logger.info('Set the controller state now to %s!', self._on_air_selector_value)
        await self._symnet_controller.set_position(self._on_air_selector_value)

    def _start_next_hour_timer(self, _: EventData = None):
        """Start the next hour timer if it isn't running already or has already completed"""
        if self._next_hour_timer and not self._next_hour_timer.done():
            return

        self._next_hour_timer = base.loop.create_task(self.__hour_timer())

    async def __hour_timer(self):
        """Try to issue the trigger event as closely as possible to the full hour"""
        logger.debug('start hour timer')

        try:
            next_hour = calc_next_hour()
            duration_to_next_hour_seconds = (next_hour - datetime.now(tz=tz.UTC)).total_seconds()
            while duration_to_next_hour_seconds > 0.3:
                logger.debug('duration to next full hour %s', duration_to_next_hour_seconds)

                sleep_time = duration_to_next_hour_seconds
                if duration_to_next_hour_seconds > 2:
                    sleep_time = duration_to_next_hour_seconds - 2
                    logger.debug('sleep time %s', sleep_time)
                    await asyncio.sleep(sleep_time)
                else:
                    logger.debug('sleep time %s', sleep_time)
                    await asyncio.sleep(sleep_time)
                    break
                duration_to_next_hour_seconds = (next_hour - datetime.now(tz=tz.UTC)).total_seconds()

            logger.info('hourly event %s', next_hour)
            try:
                self._machine.trigger('next_hour')
            except MachineError as e:
                logger.critical(e)

            self._assure_lamp_state()
        finally:
            self._next_hour_timer = None

    def _stop_next_hour_timer(self, _: EventData = None):
        if self._next_hour_timer:
            logger.debug('stop next hour timer')
            self._next_hour_timer.cancel()
            self._next_hour_timer = None

    def _start_timer(self, timer: str):
        if timer in self._timer_tasks:
            task = self._timer_tasks[timer]
            if task and not task.done():
                return

        logger.debug('start %s timer', timer)
        self._timer_tasks[timer] = base.loop.create_task(self.__timer(timer))

    async def __timer(self, timer: str):
        logger.debug('started %s timer', timer)

        try:
            await asyncio.sleep(self._timers[timer])
            try:
                self._machine.trigger(f'{timer}_timeout')
            except MachineError as e:
                logger.critical(e)
        finally:
            self._timer_tasks[timer] = None
            logger.debug('finished %s timer', timer)

    def _stop_timer(self, timer: str):
        if timer in self._timer_tasks and self._timer_tasks[timer]:
            logger.debug('stop %s timer', timer)
            self._timer_tasks[timer].cancel()
            del self._timer_tasks[timer]

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
                state = self._SaveState(**state)
                logger.debug(state)

            if state.x:
                self._x = Studio.names[state.x]
                if state.y:
                    self._y = Studio.names[state.y]

            # assure that the correct studio is on air
            if 'automat_on_air' in state.state:
                logger.debug('switch to automat')
                self._change_to_automat()
            elif 'studio_X_on_air' in state.state:
                logger.debug('switch to studio')
                self._change_to_studio()

            self._machine.trigger('to_' + state.state)
        except KeyError as e:
            logger.critical('Could not load specific studio: %s', e)
        except IOError as e:
            if e.errno == 2:
                logger.warning('Could load dispatcher state: %s', e)
            else:
                logger.critical('Could load dispatcher state: %s', e)
        except json.JSONDecodeError as e:
            logger.critical('Could load dispatcher state: %s', e)

    def save(self):
        state = self._SaveState(
            x=self._x.name if self._x else None,
            y=self._y.name if self._y else None,
            state=self._machine.state
        )
        logger.debug(state)
        try:
            with open(self.file_path, 'w') as fp:
                json.dump(attr.asdict(state), fp)
        except Exception as e:
            logger.error(e)
