import itertools
import logging
from typing import Dict, List, Tuple

import attr
import pandas
from transitions import State
from transitions.extensions.diagrams import GraphMachine

from bermudafunk.dispatcher import data_types
from bermudafunk.io import common

logger = logging.getLogger(__name__)

GraphMachine.style_attributes["node"]["default"]["shape"] = "octagon"
GraphMachine.style_attributes["node"]["active"]["shape"] = "doubleoctagon"


@attr.s(frozen=True, slots=True)
class LampStateTarget:
    automat: data_types.StudioLampState = attr.ib(validator=attr.validators.instance_of(data_types.StudioLampState))
    x: data_types.StudioLampState = attr.ib(validator=attr.validators.instance_of(data_types.StudioLampState))
    y: data_types.StudioLampState = attr.ib(validator=attr.validators.instance_of(data_types.StudioLampState))
    other: data_types.StudioLampState = attr.ib(validator=attr.validators.instance_of(data_types.StudioLampState))


class LampAwareState(State):
    def __init__(self, name, lamp_state_target: LampStateTarget, on_enter=None, on_exit=None, ignore_invalid_triggers=None):
        super().__init__(name=name, on_enter=on_enter, on_exit=on_exit, ignore_invalid_triggers=ignore_invalid_triggers)
        self._lamp_state_target = lamp_state_target

    @property
    def lamp_state_target(self) -> LampStateTarget:
        return self._lamp_state_target


class LampAwareMachine(GraphMachine):
    state_cls = LampAwareState


def load_timers_states_transitions() -> Tuple[Dict[str, float], Dict[str, LampAwareState], List[Dict]]:
    timers = load_timers()

    states = load_states()

    transitions = load_transitions(states, timers)

    return timers, states, transitions


def load_timers():
    timers_data = pandas.read_csv("transitions_data/timers.csv", converters={"name": str, "timeout_seconds": float})
    timers = {}
    for _, timer_data in timers_data.iterrows():
        timers[timer_data["name"]] = timer_data["timeout_seconds"]
    for timer1, timer2 in itertools.combinations(timers.keys(), 2):
        assert timer1 not in timer2, f"{timer1} is a substring of {timer2}"
        assert timer2 not in timer1, f"{timer2} is a substring of {timer1}"
    return timers


def load_states():
    states_data = pandas.read_csv("transitions_data/states.csv")
    states = {}
    for _, state_data in states_data.iterrows():
        name = state_data["name"]
        lamp_state_target = LampStateTarget(
            automat=data_types.StudioLampState(
                main=common.TriColorLampState(
                    state=common.LampState[state_data["automat_main_state"].upper()],
                    color=common.TriColorLampColor[state_data["automat_main_color"].upper()],
                ),
            ),
            x=data_types.StudioLampState(
                main=common.TriColorLampState(
                    state=common.LampState[state_data["x_main_state"].upper()],
                    color=common.TriColorLampColor[state_data["x_main_color"].upper()],
                ),
                immediate=common.TriColorLampState(
                    state=common.LampState[state_data["x_immediate_state"].upper()],
                    color=common.TriColorLampColor[state_data["x_immediate_color"].upper()],
                ),
            ),
            y=data_types.StudioLampState(
                main=common.TriColorLampState(
                    state=common.LampState[state_data["y_main_state"].upper()],
                    color=common.TriColorLampColor[state_data["y_main_color"].upper()],
                ),
                immediate=common.TriColorLampState(
                    state=common.LampState[state_data["y_immediate_state"].upper()],
                    color=common.TriColorLampColor[state_data["y_immediate_color"].upper()],
                ),
            ),
            other=data_types.StudioLampState(
                main=common.TriColorLampState(
                    state=common.LampState[state_data["other_main_state"].upper()],
                    color=common.TriColorLampColor[state_data["other_main_color"].upper()],
                ),
                immediate=common.TriColorLampState(
                    state=common.LampState[state_data["other_immediate_state"].upper()],
                    color=common.TriColorLampColor[state_data["other_immediate_color"].upper()],
                ),
            ),
        )
        if "X" not in name:
            lamp_state_target = attr.evolve(lamp_state_target, x=data_types.StudioLampState())
        if "Y" not in name:
            lamp_state_target = attr.evolve(lamp_state_target, y=data_types.StudioLampState())

        state = LampAwareState(name=name, lamp_state_target=lamp_state_target)
        if state.name in states:
            raise ValueError("Duplicate state name {}".format(state.name))
        states[state.name] = state
    assert len(states_data["name"]) == len(set(n.lower() for n in states_data["name"])), "duplicate state names"
    assert len(states) == len(set(s.lamp_state_target for s in states.values())), "duplicate lamp state targets"
    check_states_ignore_immediate_lamp(states)
    return states


def load_transitions(states, timers):
    transitions_data = pandas.read_csv("transitions_data/transitions.csv", converters={"switch_xy": bool})
    transitions = transitions_data.to_dict(orient="records")
    triggers = (
        {"next_hour"}
        | set(("{}_{}".format(button.value, studio) for button in data_types.Button for studio in ("X", "Y", "other")))
        | {f"{timer}_timeout" for timer in timers}
    )
    for transition in transitions:
        transition["source"] = states[transition["source"]]
        transition["dest"] = states[transition["dest"]]
    assert triggers >= set(transition["trigger"] for transition in transitions), "unknown trigger"
    assert len(transitions) == len(set((t["trigger"], t["source"]) for t in transitions)), "duplicate actions"
    return transitions


def check_states_ignore_immediate_lamp(states):
    modified_states = {}
    for state in states.values():
        lst = state.lamp_state_target
        modified_states[state.name] = attr.evolve(
            lst,
            x=attr.evolve(lst.x, immediate=common.TriColorLampState()),
            y=attr.evolve(lst.y, immediate=common.TriColorLampState()),
            other=attr.evolve(lst.other, immediate=common.TriColorLampState()),
        )
    for state1, state2 in itertools.combinations(modified_states.keys(), 2):
        if modified_states[state1] == modified_states[state2]:
            logger.warning("Duplicate lamp state ignoring immediate on states {} & {}".format(state1, state2))
