import enum
import typing

from transitions import State
from transitions.extensions import LockedGraphMachine as Machine
from transitions.extensions.diagrams import Graph

from bermudafunk.dispatcher.data_types import StudioLedStatus, LedStatus, LedState

Graph.style_attributes['node']['default']['shape'] = 'octagon'
Graph.style_attributes['node']['active']['shape'] = 'doubleoctagon'

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


class LedStatuses(enum.Enum):
    OFF = LedStatus(state=LedState.OFF, blink_freq=2)
    ON = LedStatus(state=LedState.ON, blink_freq=2)
    BLINK = LedStatus(state=LedState.BLINK, blink_freq=2)
    BLINK_FAST = LedStatus(state=LedState.BLINK, blink_freq=4)


@enum.unique
class States(enum.Enum):
    AUTOMAT_ON_AIR = LedAwareState('automat_on_air', LedStateTarget(
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
    AUTOMAT_ON_AIR_IMMEDIATE_STATE_X = LedAwareState('automat_on_air_immediate_state_X', LedStateTarget(
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
            red=LedStatuses.BLINK.value,
        )
    ))
    FROM_AUTOMAT_ON_AIR_CHANGE_TO_STUDIO_X_ON_NEXT_HOUR = LedAwareState('from_automat_on_air_change_to_studio_X_on_next_hour', LedStateTarget(
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
            yellow=LedStatuses.BLINK.value,
            red=LedStatuses.OFF.value,
        )
    ))
    STUDIO_X_ON_AIR = LedAwareState('studio_X_on_air', LedStateTarget(
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
            yellow=LedStatuses.ON.value,
            red=LedStatuses.ON.value,
        )
    ))
    FROM_STUDIO_X_ON_AIR_CHANGE_TO_AUTOMAT_ON_NEXT_HOUR = LedAwareState('from_studio_X_on_air_change_to_automat_on_next_hour', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.OFF.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.OFF.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.BLINK.value,
            red=LedStatuses.ON.value,
        )
    ))
    STUDIO_X_ON_AIR_IMMEDIATE_STATE = LedAwareState('studio_X_on_air_immediate_state', LedStateTarget(
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
            green=LedStatuses.BLINK.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.ON.value,
        )
    ))
    STUDIO_X_ON_AIR_IMMEDIATE_RELEASE = LedAwareState('studio_X_on_air_immediate_release', LedStateTarget(
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
    FROM_STUDIO_X_ON_AIR_CHANGE_TO_STUDIO_Y_ON_NEXT_HOUR = LedAwareState('from_studio_X_on_air_change_to_studio_Y_on_next_hour', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.ON.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.BLINK.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.BLINK.value,
        )
    ))
    STUDIO_X_ON_AIR_STUDIO_Y_TAKEOVER_REQUEST = LedAwareState('studio_X_on_air_studio_Y_takeover_request', LedStateTarget(
        x=StudioLedStatus(
            green=LedStatuses.ON.value,
            yellow=LedStatuses.BLINK.value,
            red=LedStatuses.BLINK.value,
        ),
        y=StudioLedStatus(
            green=LedStatuses.OFF.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.OFF.value,
        ),
        other=StudioLedStatus(
            green=LedStatuses.BLINK.value,
            yellow=LedStatuses.ON.value,
            red=LedStatuses.BLINK.value,
        )
    ))
    NOOP = LedAwareState('noop', LedStateTarget(
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
