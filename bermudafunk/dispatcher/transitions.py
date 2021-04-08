import itertools
import logging
from typing import Dict, List, Tuple

import attr
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
    def __init__(self, name, lamp_state_target: LampStateTarget, on_enter=None, on_exit=None, ignore_invalid_triggers=False):
        super().__init__(name=name, on_enter=on_enter, on_exit=on_exit, ignore_invalid_triggers=ignore_invalid_triggers)
        self._lamp_state_target = lamp_state_target

    @property
    def lamp_state_target(self) -> LampStateTarget:
        return self._lamp_state_target


class LampAwareMachine(GraphMachine):
    state_cls = LampAwareState


def load_timers_states_transitions() -> Tuple[Dict[str, float], Dict[str, LampAwareState], List[Dict]]:
    import pandas

    timers_data = pandas.read_csv("transitions_data/timers.csv", converters={"name": str, "timeout_seconds": float})
    timers = {}
    for _, timer_data in timers_data.iterrows():
        timers[timer_data["name"]] = timer_data["timeout_seconds"]

    states_data = pandas.read_csv("transitions_data/states.csv")
    states = {}

    for _, state_data in states_data.iterrows():
        state = LampAwareState(
            name=state_data["state"],
            lamp_state_target=LampStateTarget(
                automat=data_types.StudioLampState(
                    main=common.TriColorLampState(
                        state=common.LampState[state_data["automat_main_state"].upper()],
                        color=common.TriColorLampColor[state_data["automat_main_color"].upper()],
                    ),
                    immediate=common.TriColorLampState(
                        state=common.LampState.OFF,
                        color=common.TriColorLampColor.NONE,
                    )
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
        )
        if state.name in states:
            raise ValueError("Duplicate state name {}".format(state.name))
        states[state.name] = state

    assert len(states_data["state"]) == len(set(n.lower() for n in states_data["state"])), "duplicate state names"
    assert len(states) == len(set(s.lamp_state_target for s in states.values())), "duplicate lamp state targets"

    check_states_ignore_immediate_lamp(states)

    transitions_data = pandas.read_csv("transitions_data/transitions.csv", converters={"y_to_x": bool})
    transitions = transitions_data.to_dict(orient="records")

    triggers = {"next_hour"} | set(
        ("{}_{}".format(button.value, studio) for button in data_types.Button for studio in ("X", "Y"))
    ) | {f"{timer}_timeout" for timer in timers}

    # Assure to ignore button presses which are not in any transition
    for trigger in triggers:
        if trigger not in [transition["trigger"] for transition in transitions]:
            transitions.append({
                "trigger": trigger,
                "source": "noop",
                "dest": "noop"})  # noop to complete all combinations of buttons presses

    for transition in transitions:
        transition["source"] = states[transition["source"]]
        transition["dest"] = states[transition["dest"]]

    assert triggers >= set(transition["trigger"] for transition in transitions), "unknown trigger"
    assert len(transitions) == len(set((t["trigger"], t["source"]) for t in transitions)), "duplicate actions"

    return timers, states, transitions


def check_states_ignore_immediate_lamp(states):
    modified_states = {}
    for state in states.values():
        lst = state.lamp_state_target
        modified_states[state.name] = attr.evolve(
            lst,
            automat=attr.evolve(
                lst.automat,
                immediate=common.TriColorLampState(
                    state=common.LampState.OFF,
                    color=common.TriColorLampColor.NONE,
                )
            ),
            x=attr.evolve(
                lst.x,
                immediate=common.TriColorLampState(
                    state=common.LampState.OFF,
                    color=common.TriColorLampColor.NONE,
                )
            ),
            y=attr.evolve(
                lst.y,
                immediate=common.TriColorLampState(
                    state=common.LampState.OFF,
                    color=common.TriColorLampColor.NONE,
                )
            ),
            other=attr.evolve(
                lst.other,
                immediate=common.TriColorLampState(
                    state=common.LampState.OFF,
                    color=common.TriColorLampColor.NONE,
                )
            )
        )
    for state1, state2 in itertools.combinations(modified_states.keys(), 2):
        if modified_states[state1] == modified_states[state2]:
            logger.warning("Duplicate lamp state ignoring immediate on states {} & {}".format(state1, state2))
