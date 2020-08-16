import enum
import typing

from transitions import State
from transitions.extensions import GraphMachine as Machine
from transitions.extensions.diagrams import GraphMachine

from bermudafunk.dispatcher.data_types import StudioLampStatus, LampState

GraphMachine.style_attributes['node']['default']['shape'] = 'octagon'
GraphMachine.style_attributes['node']['active']['shape'] = 'doubleoctagon'

LampStateTarget = typing.NamedTuple(
    'LampStateTarget',
    [
        ('automat', StudioLampStatus),
        ('x', StudioLampStatus),
        ('y', StudioLampStatus),
        ('other', StudioLampStatus)
    ]
)


class LampAwareState(State):
    def __init__(self, name, lamp_state_target: LampStateTarget, on_enter=None, on_exit=None, ignore_invalid_triggers=False):
        super().__init__(name, on_enter, on_exit, ignore_invalid_triggers)
        self._lamp_state_target = lamp_state_target

    @property
    def lamp_state_target(self) -> LampStateTarget:
        return self._lamp_state_target


class LampAwareMachine(Machine):
    state_cls = LampAwareState

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


# @enum.unique
class States(LampAwareState, enum.Enum):
    AUTOMAT_ON_AIR = ('automat_on_air', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        )
    ))
    AUTOMAT_ON_AIR_IMMEDIATE_STATE_X = ('automat_on_air_immediate_state_X', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.ON,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        )
    ))
    FROM_AUTOMAT_ON_AIR_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR = ('from_automat_on_air_change_to_studio_X_on_next_hour', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.BLINK,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        )
    ))
    STUDIO_X_ON_AIR = ('studio_X_on_air', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        )
    ))
    FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR = ('from_studio_X_on_air_change_to_automat_on_next_hour', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.BLINK,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.BLINK,
            red=LampState.OFF,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        )
    ))
    STUDIO_X_ON_AIR_IMMEDIATE_STATE = ('studio_X_on_air_immediate_state', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.OFF,
            red=LampState.ON,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        )
    ))
    STUDIO_X_ON_AIR_IMMEDIATE_RELEASE = ('studio_X_on_air_immediate_release', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.BLINK_FAST,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.BLINK,
            red=LampState.ON,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.BLINK,
            red=LampState.BLINK,
        )
    ))
    FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR = ('from_studio_X_on_air_change_to_studio_Y_on_next_hour', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.ON,
            red=LampState.OFF,
        ),
        y=StudioLampStatus(
            green=LampState.BLINK,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        )
    ))
    STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST = ('studio_X_on_air_studio_Y_takeover_request', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.ON,
            yellow=LampState.BLINK,
            red=LampState.OFF,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.ON,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        )
    ))
    NOOP = ('noop', LampStateTarget(
        automat=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        x=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        y=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
        ),
        other=StudioLampStatus(
            green=LampState.OFF,
            yellow=LampState.OFF,
            red=LampState.OFF,
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
    {'trigger': 'takeover_Y', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR,
     'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR},
    {'trigger': 'next_hour', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR, 'dest': States.AUTOMAT_ON_AIR},

    {'trigger': 'immediate_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'immediate_state_timeout', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE},

    {'trigger': 'takeover_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE},
    {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR_IMMEDIATE_STATE},
    {'trigger': 'takeover_Y', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.STUDIO_X_ON_AIR, 'switch_to_y': True},
    {'trigger': 'immediate_release_timeout', 'source': States.STUDIO_X_ON_AIR_IMMEDIATE_RELEASE, 'dest': States.AUTOMAT_ON_AIR},

    {'trigger': 'takeover_Y', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR,
     'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR},
    {'trigger': 'release_Y', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR,
     'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR},
    {'trigger': 'next_hour', 'source': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR, 'dest': States.STUDIO_X_ON_AIR,
     'switch_to_y': True},

    {'trigger': 'takeover_Y', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'release_Y', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST, 'dest': States.STUDIO_X_ON_AIR},
    {'trigger': 'release_X', 'source': States.STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST,
     'dest': States.FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR},
]
