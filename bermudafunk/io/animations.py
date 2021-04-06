import functools
import itertools
import operator
from typing import ClassVar, Dict, List, Optional, Tuple

import attr

from bermudafunk.io import common


@attr.s(frozen=True, slots=True)
class SingleTriColorLampKeyframe:
    duration: float = attr.ib(converter=float)
    state: common.LampState = attr.ib(
        default=common.LampState.OFF,
        validator=attr.validators.instance_of(common.LampState))
    color: common.TriColorLampColor = attr.ib(
        default=common.TriColorLampColor.NONE,
        validator=attr.validators.instance_of(common.TriColorLampColor))

    @state.validator
    def _validate_state(self, _, value: common.LampState):
        if value == common.LampState.ANIMATION:
            raise ValueError("The state must differ from ANIMATION")


class SingleTriColorLampAnimation:
    instances: ClassVar[Dict[str, 'SingleTriColorLampAnimation']] = {}

    def __init__(
        self,
        name: str,
        *args,
        keyframes=(),
        default_state: Optional[common.LampState] = None,
        default_color: Optional[common.TriColorLampColor] = None
    ):
        self._name = str(name)
        arg_keyframes = itertools.chain(args, keyframes)
        kfs: List[SingleTriColorLampKeyframe] = []
        for keyframe in arg_keyframes:
            if isinstance(keyframe, SingleTriColorLampKeyframe):
                kfs.append(keyframe)
            else:
                for inner_keyframe in keyframe:
                    if isinstance(inner_keyframe, SingleTriColorLampKeyframe):
                        kfs.append(inner_keyframe)
                    else:
                        raise ValueError(
                            'Keyframes must be instances of {}, supplied: {}'.format(
                                type(SingleTriColorLampKeyframe),
                                type(inner_keyframe)
                            )
                        )
        default_dict = {}
        if default_state is not None:
            default_dict['state'] = default_state
        if default_color is not None:
            default_dict['color'] = default_color
        self._keyframes = tuple(attr.evolve(kf, **default_dict) for kf in kfs)

        if self._name in self.instances and self != self.instances[self._name]:
            raise ValueError('Already a not equal instance created with name {!r}'.format(self._name))
        self.instances[self._name] = self

    @property
    def name(self) -> str:
        return self._name

    @property
    def keyframes(self) -> Tuple[SingleTriColorLampKeyframe]:
        return self._keyframes

    def __repr__(self) -> str:
        return '{}(name={!r}, keyframes={!r})'.format(self.__class__.__name__, self._name, self._keyframes)

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, self.__class__)
                and self._name == other._name
                and len(self._keyframes) == len(other._keyframes)
                and all(a == b for a, b in zip(self._keyframes, other._keyframes)))

    def __hash__(self) -> int:
        hashes = map(hash, itertools.chain([self._name], self._keyframes))
        return functools.reduce(operator.xor, hashes, 0)
