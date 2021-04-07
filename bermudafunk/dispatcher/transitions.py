import itertools
import logging

import attr
import pandas
from transitions import State
from transitions.extensions.diagrams import GraphMachine

from bermudafunk.dispatcher.data_types import StudioLampState, triggers
from bermudafunk.io.common import LampState, TriColorLampColor, TriColorLampState

logger = logging.getLogger(__name__)

GraphMachine.style_attributes['node']['default']['shape'] = 'octagon'
GraphMachine.style_attributes['node']['active']['shape'] = 'doubleoctagon'


@attr.s(frozen=True, slots=True)
class LampStateTarget:
    automat: StudioLampState = attr.ib(validator=attr.validators.instance_of(StudioLampState))
    x: StudioLampState = attr.ib(validator=attr.validators.instance_of(StudioLampState))
    y: StudioLampState = attr.ib(validator=attr.validators.instance_of(StudioLampState))
    other: StudioLampState = attr.ib(validator=attr.validators.instance_of(StudioLampState))


class LampAwareState(State):
    def __init__(self, name, lamp_state_target: LampStateTarget, on_enter=None, on_exit=None, ignore_invalid_triggers=False):
        super().__init__(name=name, on_enter=on_enter, on_exit=on_exit, ignore_invalid_triggers=ignore_invalid_triggers)
        self._lamp_state_target = lamp_state_target

    @property
    def lamp_state_target(self) -> LampStateTarget:
        return self._lamp_state_target


class LampAwareMachine(GraphMachine):
    state_cls = LampAwareState


def load_states_transitions():
    states_data = pandas.read_excel("dispatcher.ods", sheet_name="states")
    states = {}

    for _, state_data in states_data.iterrows():
        state = LampAwareState(
            name=state_data["state"],
            lamp_state_target=LampStateTarget(
                automat=StudioLampState(
                    main=TriColorLampState(
                        state=LampState[state_data["automat_main_state"].upper()],
                        color=TriColorLampColor[state_data["automat_main_color"].upper()],
                    ),
                    immediate=TriColorLampState(
                        state=LampState.OFF,
                        color=TriColorLampColor.NONE,
                    )
                ),
                x=StudioLampState(
                    main=TriColorLampState(
                        state=LampState[state_data["x_main_state"].upper()],
                        color=TriColorLampColor[state_data["x_main_color"].upper()],
                    ),
                    immediate=TriColorLampState(
                        state=LampState[state_data["x_immediate_state"].upper()],
                        color=TriColorLampColor[state_data["x_immediate_color"].upper()],
                    ),
                ),
                y=StudioLampState(
                    main=TriColorLampState(
                        state=LampState[state_data["y_main_state"].upper()],
                        color=TriColorLampColor[state_data["y_main_color"].upper()],
                    ),
                    immediate=TriColorLampState(
                        state=LampState[state_data["y_immediate_state"].upper()],
                        color=TriColorLampColor[state_data["y_immediate_color"].upper()],
                    ),
                ),
                other=StudioLampState(
                    main=TriColorLampState(
                        state=LampState[state_data["other_main_state"].upper()],
                        color=TriColorLampColor[state_data["other_main_color"].upper()],
                    ),
                    immediate=TriColorLampState(
                        state=LampState[state_data["other_immediate_state"].upper()],
                        color=TriColorLampColor[state_data["other_immediate_color"].upper()],
                    ),
                ),
            )
        )
        if state.name in states:
            raise ValueError("Duplicate state name {}".format(state.name))
        states[state.name] = state

    assert len(states_data["state"]) == len(set(n.lower() for n in states_data["state"])), "duplicate state names"
    assert len(states) == len(set(s.lamp_state_target for s in states.values())), "duplicate lamp state targets"

    check_states_ignore_immediate_lamp(states)

    transitions_data = pandas.read_excel("dispatcher.ods", sheet_name="transitions", converters={"y_to_x": bool})
    transitions = transitions_data.to_dict(orient="records")
    for transition in transitions:
        transition['source'] = states[transition['source']]
        transition['dest'] = states[transition['dest']]
    assert triggers >= set(transition["trigger"] for transition in transitions), "unknown trigger"
    assert len(transitions) == len(set((t["trigger"], t["source"]) for t in transitions)), "duplicate actions"

    return states, transitions


def check_states_ignore_immediate_lamp(states):
    modified_states = {}
    for state in states.values():
        lst = state.lamp_state_target
        modified_states[state.name] = attr.evolve(
            lst,
            automat=attr.evolve(
                lst.automat,
                immediate=TriColorLampState(
                    state=LampState.OFF,
                    color=TriColorLampColor.NONE,
                )
            ),
            x=attr.evolve(
                lst.x,
                immediate=TriColorLampState(
                    state=LampState.OFF,
                    color=TriColorLampColor.NONE,
                )
            ),
            y=attr.evolve(
                lst.y,
                immediate=TriColorLampState(
                    state=LampState.OFF,
                    color=TriColorLampColor.NONE,
                )
            ),
            other=attr.evolve(
                lst.other,
                immediate=TriColorLampState(
                    state=LampState.OFF,
                    color=TriColorLampColor.NONE,
                )
            )
        )
    for state1, state2 in itertools.combinations(modified_states.keys(), 2):
        if modified_states[state1] == modified_states[state2]:
            logger.warning("Duplicate lamp state ignoring immediate on states {} & {}".format(state1, state2))
