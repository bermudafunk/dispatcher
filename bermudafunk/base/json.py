import enum
import functools
from json import *

import attr

from bermudafunk.io.common import TriColorLampState


class AttrEnumJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, TriColorLampState):
            return {
                "state": o.state.name,
                "frequency": o.state.value,
                "color": o.color,
            }
        if attr.has(type(o)):
            return attr.asdict(o, recurse=False)
        if isinstance(o, enum.Enum):
            return o.name
        return super().default(o)


dump = functools.partial(dump, cls=AttrEnumJSONEncoder)
dumps = functools.partial(dumps, cls=AttrEnumJSONEncoder)
