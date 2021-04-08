import functools
import logging
import typing

from bermudafunk.io import common

logger = logging.getLogger(__name__)


class DummyButton(common.BaseButton):
    def add_observer(self, handler: typing.Callable):
        super().add_observer(handler)
        logger.info("Added handler {} to button {}".format(handler, self.name))

    def remove_observer(self, handler: typing.Callable):
        super().remove_observer(handler)
        logger.info("Removed handler {} to button {}".format(handler, self.name))


class DummyLamp(common.BaseLamp):
    def __init__(self, name: str, state: common.LampState = common.LampState.OFF):
        super().__init__(
            name=name,
            on_callable=functools.partial(logger.debug, 'Dummy Lamp <{}> ON'.format(name)),
            off_callable=functools.partial(logger.debug, 'Dummy Lamp <{}> OFF'.format(name)),
            state=state,
        )


class DummyTriColorLamp(common.BaseTriColorLamp):
    def __init__(
        self,
        name: str,
        state: common.LampState = common.LampState.OFF,
        color: common.TriColorLampColor = common.TriColorLampColor.GREEN,
    ):
        super().__init__(
            name=name,
            on_callable=self._on_callable,
            off_callable=self._off_callable,
            state=state,
            color=color,
        )

    def _on_callable(self):
        logger.debug('Dummy Lamp <%s> with color <%s> ON', self.name, self.color)

    def _off_callable(self):
        logger.debug('Dummy Lamp <%s> with color <%s> OFF', self.name, self.color)
