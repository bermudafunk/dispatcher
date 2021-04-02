import functools
import logging
import typing

from . import common

logger = logging.getLogger(__name__)


class DummyButton(common.BaseButton):
    def add_handler(self, handler: typing.Callable):
        super().add_handler(handler)
        logger.info("Added handler {} to button {}".format(handler, self.name))

    def remove_handler(self, handler: typing.Callable):
        super().remove_handler(handler)
        logger.info("Removed handler {} to button {}".format(handler, self.name))


class DummyLamp(common.BaseLamp):
    def __init__(self, name: str):
        common.BaseLamp.__init__(
            self,
            name,
            on_callable=functools.partial(logger.debug, 'Dummy Lamp %s ON'.format(name)),
            off_callable=functools.partial(logger.debug, 'Dummy Lamp %s OFF'.format(name))
        )


class DummyTriStateLamp(common.BaseTriColorLamp):
    def __init__(self, name: str, initial_color: common.TriColorLampColors = common.TriColorLampColors.GREEN):
        super().__init__(name, self._on_callable, self._off_callable, initial_color)

    def _on_callable(self):
        logger.debug('Dummy Lamp %s with color %s ON', self.name, self.color)

    def _off_callable(self):
        logger.debug('Dummy Lamp %s with color %s OFF', self.name, self.color)
