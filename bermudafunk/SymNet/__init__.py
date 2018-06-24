import asyncio
import logging
import re

from bermudafunk import base
from bermudafunk.base import queues

logger = logging.getLogger(__name__)


class SymNetRawProtocolCallback:
    def __init__(self, callback, expected_lines, regex=None):
        self._callback = callback
        self.expected_lines = expected_lines
        self.regex = regex
        self.future = base.loop.create_future()

    def callback(self, *args, **kwargs):
        logger.debug("raw protocol callback called")
        try:
            result = self._callback(*args, **kwargs)
            self.future.set_result(result)
        except Exception as e:
            self.future.set_exception(e)


class SymNetRawProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        logger.debug("init a SymNetRawProtocol")
        self.transport = None
        self.callback_queue = []

    def connection_made(self, transport):
        logger.debug("connection established")
        self.transport = transport

    def datagram_received(self, data, addr):
        logger.debug("a datagram was received - %d bytes", len(data))
        data_str = data.decode()
        lines = data_str.split('\r')
        lines = [lines[i] for i in range(len(lines)) if len(lines[i]) > 0]

        logger.debug("%d non-empty lines received", len(lines))

        if len(self.callback_queue) > 0:
            logger.debug("iterate over callback queue")
            for callback_obj in self.callback_queue:
                if len(lines) == 1 and lines[0] == 'NAK':
                    logger.debug("got only a NAK - forwarding to the first callback")
                    callback_obj.callback(data_str)
                    self.callback_queue.remove(callback_obj)
                    return

                if callback_obj.regex is not None:
                    logger.debug("callback comes with a regex - try match on the whole received data string")
                    m = re.match(callback_obj.regex, data_str)
                    if m is not None:
                        logger.debug("regex worked - deliver to callback and remove it")
                        callback_obj.callback(data_str, m=m)
                        self.callback_queue.remove(callback_obj)
                        return
                elif len(lines) == callback_obj.expected_lines:
                    logger.debug("callback has no regex, but the expected line count equals to the received one")
                    callback_obj.callback(data_str)
                    self.callback_queue.remove(callback_obj)
                    return

        if len(lines) == 1:
            if lines[0] == 'NAK':
                logger.error('Uncaught NAK - this is probably a huge error')
                return
            if lines[0] == 'ACK':
                logger.debug('got an ACK, but no callbacks waiting for input - just ignore it')
                return

        logger.debug("no callbacks defined and not an ACK or NAK - must be pushed data")
        for line in lines:
            m = re.match('^#([0-9]{5})=(-?[0-9]{4,5})$', line)
            if m is None:
                logger.error("error in in the received line <%s>", line)
                continue

            asyncio.ensure_future(queues.put_in_queue({
                'cn': int(m.group(1)),
                'cv': int(m.group(2))
            }, 'symnet_controller_state'))

    def error_received(self, exc):
        logger.error('Error received %s', exc)
        pass

    def write(self, data):
        logger.debug('send data to symnet %s', data)
        self.transport.sendto(data.encode())


class SymNetController:
    value_timeout = 10  # in seconds

    def __init__(self, controller_number, protocol: SymNetRawProtocol):
        logger.debug('create new SymNetController with %d', controller_number)
        self.controller_number = int(controller_number)
        self.proto = protocol

        self.raw_value = 0
        self.raw_value_time = 0

        self.observer = []

        base.loop.run_until_complete(self._retrieve_current_state().future)

    def add_observer(self, callback):
        logger.debug("add a observer (%s) to controller %d", callback, self.controller_number)
        return self.observer.append(callback)

    def remove_observer(self, callback):
        logger.debug("remove a observer (%s) to controller %d", callback, self.controller_number)
        return self.observer.remove(callback)

    async def _get_raw_value(self):
        logger.debug('retrieve current value for controller %d', self.controller_number)
        if base.loop.time() - self.raw_value_time > self.value_timeout:
            logger.debug('value timeout - refresh')
            await self._retrieve_current_state().future
        return self.raw_value

    def _set_raw_value(self, value):
        logger.debug('set_raw_value called on %d with %d', self.controller_number, value)
        old_value = self.raw_value
        self.raw_value = value
        self.raw_value_time = base.loop.time()
        if old_value != value:
            logger.debug("value has changed - notify observers")
            for clb in self.observer:
                asyncio.ensure_future(clb(self, old_value=old_value, new_value=value))

    def _assure_current_state(self):
        logger.debug("assure current controller %d state to set on the symnet device", self.controller_number)
        callback_obj = SymNetRawProtocolCallback(
            callback=self._assure_callback,
            expected_lines=1,
            regex='^(ACK)|(NAK)\r$'
        )
        self.proto.callback_queue.append(callback_obj)
        self.proto.write('CS {cn:d} {cv:d}\r'.format(cn=self.controller_number, cv=self.raw_value))
        return callback_obj

    def _assure_callback(self, data_str, m=None):
        if m is None or m.group(1) == 'NAK':
            raise Exception(
                'Unknown error occurred awaiting the acknowledge of setting controller number {:d}'.format(
                    self.controller_number))

    def _retrieve_current_state(self):
        logger.debug("request current value from the symnet device for controller %d", self.controller_number)
        callback_obj = SymNetRawProtocolCallback(
            callback=self._retrieve_callback,
            expected_lines=1,
            regex='^' + str(self.controller_number) + ' ([0-9]{1,5})\r$'
        )
        self.proto.callback_queue.append(callback_obj)
        self.proto.write('GS2 {:d}\r'.format(self.controller_number))
        return callback_obj

    def _retrieve_callback(self, data_str, m=None):
        if m is None:
            raise Exception('Error executing GS2 command, controller {}'.format(self.controller_number))
        self._set_raw_value(int(m.group(1)))


class SymNetSelectorController(SymNetController):
    def __init__(self, controller_number, selector_count, protocol):
        super().__init__(controller_number, protocol)

        self.sc = int(selector_count)

    async def get_position(self):
        return int(round(await self._get_raw_value() / 65535 * (self.sc - 1) + 1))

    async def set_position(self, position):
        self._set_raw_value(int(round((position - 1) / (self.sc - 1) * 65535)))
        await self._assure_current_state().future


class SymNetButtonController(SymNetController):
    async def on(self):
        self._set_raw_value(65535)
        await self._assure_current_state().future

    async def off(self):
        self._set_raw_value(0)
        await self._assure_current_state().future

    async def pressed(self):
        return await self._get_raw_value() > 0

    def set(self, state):
        if state:
            return self.on()
        else:
            return self.off()


class SymNetDevice:
    def __init__(self, local_addr, remote_addr):
        logger.debug('setup new symnet device')
        self.controllers = {}
        connect = base.loop.create_datagram_endpoint(
            SymNetRawProtocol,
            local_addr=local_addr,
            remote_addr=remote_addr
        )
        self.transport, self.protocol = base.loop.run_until_complete(connect)

        self._process_task = base.loop.create_task(self._process_push_messages())
        base.cleanup_tasks.append(base.loop.create_task(self._cleanup()))

    async def _process_push_messages(self):
        while True:
            cs = await queues.get_from_queue('symnet_controller_state')
            logger.debug("received some pushed data - handover to the controller object")
            if cs['cn'] in self.controllers:
                self.controllers[cs['cn']]._set_raw_value(cs['cv'])

    def define_controller(self, controller_number) -> SymNetController:
        logger.debug('create new controller %d on symnet device', controller_number)
        controller_number = int(controller_number)
        controller = SymNetController(controller_number, self.protocol)
        self.controllers[controller_number] = controller

        return controller

    def define_selector(self, controller_number: int, selector_count: int) -> SymNetSelectorController:
        logger.debug('create new selector %d on symnet device', controller_number)
        controller_number = int(controller_number)
        controller = SymNetSelectorController(controller_number, selector_count, self.protocol)
        self.controllers[controller_number] = controller

        return controller

    def define_button(self, controller_number) -> SymNetButtonController:
        logger.debug('create new button %d on symnet device', controller_number)
        controller_number = int(controller_number)
        controller = SymNetButtonController(controller_number, self.protocol)
        self.controllers[controller_number] = controller

        return controller

    async def _cleanup(self):
        logger.debug('SymNetDevice awaiting cleanup')
        await base.cleanup_event.wait()
        logger.debug('SymNetDevice cancel process_task')
        self._process_task.cancel()
        logger.debug('SymNetDevice close transport')
        self.transport.close()
