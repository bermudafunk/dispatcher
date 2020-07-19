import logging
import typing

from . import common
from .common import OutputState, ButtonEvent

logger = logging.getLogger(__name__)


class DummyInput(common.BaseInput):
    def add_handler(self, handler: typing.Callable[[ButtonEvent], None]):
        super().add_handler(handler)
        logger.info("Added handler {} to button {}".format(handler, self.name))

    def remove_handler(self, handler: typing.Callable[[ButtonEvent], None]):
        super().remove_handler(handler)
        logger.info("Removed handler {} to button {}".format(handler, self.name))


class DummyOutput(common.BaseOutput):
    def __init__(self, name: str):
        super().__init__(name)
        self._state = common.OutputState.OFF

    @property
    def state(self) -> OutputState:
        return self._state

    @state.setter
    def state(self, state: OutputState):
        logger.info("Setting state of lamp {} to {}".format(self.name, state))
        if not isinstance(state, OutputState):
            raise TypeError("Supplied state {} is not a instance of LampState".format(state))
        self._state = state
