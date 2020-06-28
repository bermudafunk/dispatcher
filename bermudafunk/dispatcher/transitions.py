import enum
import typing

from transitions import State
from transitions.extensions import LockedGraphMachine as Machine
from transitions.extensions.diagrams import GraphMachine

from bermudafunk.dispatcher.data_types import StudioLedStatus, LedStatus, LedState

GraphMachine.style_attributes['node']['default']['shape'] = 'octagon'
GraphMachine.style_attributes['node']['active']['shape'] = 'doubleoctagon'

LedStateTarget = typing.NamedTuple('LedStateTarget', [('x', StudioLedStatus), ('y', StudioLedStatus), ('other', StudioLedStatus)])


class LedAwareState(State):
    def __init__(self, name, led_state_target: LedStateTarget, on_enter=None, on_exit=None, ignore_invalid_triggers=False):
        super().__init__(name, on_enter, on_exit, ignore_invalid_triggers)
        self._led_state_target = led_state_target

    @property
    def led_state_target(self) -> LedStateTarget:
        return self._led_state_target


class LedAwareMachine(Machine):
    state_cls = LedAwareState

    def add_states(self, states, on_enter=None, on_exit=None,
                   ignore_invalid_triggers=None, **kwargs):
        """ Add new state(s).
        Args:
            states (list, str, dict, Enum or State): a list, a State instance, the
                name of a new state, an enumeration (member) or a dict with keywords to pass on to the
                State initializer. If a list, each element can be a string, State or enumeration member.
            on_enter (str or list): callbacks to trigger when the state is
                entered. Only valid if first argument is string.
            on_exit (str or list): callbacks to trigger when the state is
                exited. Only valid if first argument is string.
            ignore_invalid_triggers: when True, any calls to trigger methods
                that are not valid for the present state (e.g., calling an
                a_to_b() trigger when the current state is c) will be silently
                ignored rather than raising an invalid transition exception.
                Note that this argument takes precedence over the same
                argument defined at the Machine level, and is in turn
                overridden by any ignore_invalid_triggers explicitly
                passed in an individual state's initialization arguments.

            **kwargs additional keyword arguments used by state mixins.
        """

        ignore = ignore_invalid_triggers
        if ignore is None:
            ignore = self.ignore_invalid_triggers

        from transitions.core import listify
        states = listify(states)

        for state in states:
            from six import string_types
            from transitions.core import Enum
            if not isinstance(state, self.state_cls):
                if isinstance(state, (string_types, Enum)):
                    state = self._create_state(
                        state, on_enter=on_enter, on_exit=on_exit,
                        ignore_invalid_triggers=ignore, **kwargs)
                elif isinstance(state, dict):
                    if 'ignore_invalid_triggers' not in state:
                        state['ignore_invalid_triggers'] = ignore
                    state = self._create_state(**state)
            self.states[state.name] = state
            for model in self.models:
                self._add_model_to_state(state, model)
            if self.auto_transitions:
                for a_state in self.states.keys():
                    # add all states as sources to auto transitions 'to_<state>' with dest <state>
                    if a_state == state.name:
                        self.add_transition('to_%s' % a_state, self.wildcard_all, a_state)
                    # add auto transition with source <state> to <a_state>
                    else:
                        self.add_transition('to_%s' % a_state, state.name, a_state)


class LedStatuses(enum.Enum):
    OFF = LedStatus(state=LedState.OFF, blink_freq=2)
    ON = LedStatus(state=LedState.ON, blink_freq=2)
    BLINK = LedStatus(state=LedState.BLINK, blink_freq=2)
    BLINK_FAST = LedStatus(state=LedState.BLINK, blink_freq=4)


# @enum.unique
class States(LedAwareState, enum.Enum):
    AUTOMAT_ON_AIR = ('automat_on_air', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))
    AUTOMAT_ON_AIR_IMMEDIATE_STATE_X = ('automat_on_air_immediate_state_X', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.ON.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))
    FROM_AUTOMAT_ON_AIR_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR = ('from_automat_on_air_change_to_studio_X_on_next_hour', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.BLINK.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))
    STUDIO_X_ON_AIR = ('studio_X_on_air', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))
    FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR = ('from_studio_X_on_air_change_to_automat_on_next_hour', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.BLINK.value,
            red=LedStatuses.OFF.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))
    STUDIO_X_ON_AIR_IMMEDIATE_STATE = ('studio_X_on_air_immediate_state', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.ON.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))
    STUDIO_X_ON_AIR_IMMEDIATE_RELEASE = ('studio_X_on_air_immediate_release', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.BLINK.value,
            red=LedStatuses.ON.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.BLINK.value,
            red=LedStatuses.BLINK.value,
        )
    ))
    FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR = ('from_studio_X_on_air_change_to_studio_Y_on_next_hour', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.OFF.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.BLINK.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))
    STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST = ('studio_X_on_air_studio_Y_takeover_request', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.BLINK.value,
            red=LedStatuses.OFF.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))
    NOOP = ('noop', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        )
    ))


transitions = [
    {'trigger': 'takeover_X', 'source': States.AUTOMAT_ON_AIR, 'dest': States.FROM_AUTOMAT_ON_AIR_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR},
    {'trigger': 'immediate_X', 'source': States.AUTOMAT_ON_AIR, 'dest': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X},

    {'trigger': 'takeover_X', 'source': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'release_X', 'source': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X, 'dest': States.AUTOMAT_ON_AIR},
    {'trigger': 'immediate_X', 'source': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X, 'dest': States.AUTOMAT_ON_AIR},
    {'trigger': 'immediate_state_timeout', 'source': States.AUTOMAT_ON_AIR_IMMEDIATE_STATE_X, 'dest': States.AUTOMAT_ON_AIR},

    {'trigger': 'takeover_X', 'source': States.FROM_AUTOMAT_ON_AIR_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR, 'dest': States.AUTOMAT_ON_AIR},
    {'trigger': 'release_X', 'source': States.FROM_AUTOMAT_ON_AIR_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR, 'dest': States.AUTOMAT_ON_AIR},
    {'trigger': 'next_hour', 'source': States.FROM_AUTOMAT_ON_AIR_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR},

    {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR, 'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR},
    {'trigger': 'immediate_X', 'source': States.STUDIO_X_ON_AIR, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE},
    {'trigger': 'takeover_Y', 'source': States.STUDIO_X_ON_AIR, 'dest': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST},

    {'trigger': 'takeover_X', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'release_X', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'takeover_Y', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR},
    {'trigger': 'next_hour', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.AUTOMAT_ON_AIR},

    {'trigger': 'immediate_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'immediate_state_timeout', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE},

    {'trigger': 'takeover_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE},
    {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE},
    {'trigger': 'takeover_Y', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR, 'switch_to_y': True},
    {'trigger': 'immediate_release_timeout', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.AUTOMAT_ON_AIR},

    {'trigger': 'takeover_Y', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR, 'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR},
    {'trigger': 'release_Y', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR, 'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR},
    {'trigger': 'next_hour', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR, 'switch_to_y': True},

    {'trigger': 'takeover_Y', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'release_Y', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST, 'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR},
]
