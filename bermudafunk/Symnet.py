import asyncio
import re
from bermudafunk import Base, Queues


class SymNetRawProtocolCallback:
    def __init__(self, callback, expected_lines, regex=None):
        self._callback = callback
        self.expected_lines = expected_lines
        self.regex = regex
        self.future = Base.loop.create_future()

    def callback(self, *args, **kwargs):
        try:
            result = self._callback(*args, **kwargs)
            self.future.set_result(result)
        except Exception as e:
            self.future.set_exception(e)


class SymNetRawProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None
        self.callback_queue = []

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        data_str = data.decode()
        lines = data_str.split('\r')
        lines = [lines[i] for i in range(len(lines)) if len(lines[i]) > 0]

        if len(self.callback_queue) > 0:
            for callback_obj in self.callback_queue:
                if len(lines) == 1 and lines[0] == 'NAK':
                    callback_obj.callback(data_str)
                    self.callback_queue.remove(callback_obj)
                    return

                if callback_obj.regex is not None:
                    m = re.match(callback_obj.regex, data_str)
                    if m is not None:
                        callback_obj.callback(data_str, m=m)
                        self.callback_queue.remove(callback_obj)
                        return
                elif len(lines) == callback_obj.expected_lines:
                    callback_obj.callback(data_str)
                    self.callback_queue.remove(callback_obj)
                    return

        if len(lines) == 1:
            if lines[0] == 'NAK':
                print('Uncaught NAK, please define a callback')
            if lines[0] == 'ACK':
                return

        for line in lines:
            m = re.match('^#([0-9]{5})=(\-?[0-9]{4,5})$', line)
            if m is None:
                print('unkown', line)
                continue

            asyncio.ensure_future(Queues.put_in_queue({
                'cn': int(m.group(1)),
                'cv': int(m.group(2))
            }, 'symnet_controller_state'))

    def error_received(self, exc):
        print('Error received:', exc)

    def write(self, data):
        self.transport.sendto(data.encode())


class SymNetController:
    value_timeout = 10  # in seconds

    def __init__(self, controller_number, protocol: SymNetRawProtocol):
        self.cn = int(controller_number)
        self.proto = protocol

        self.raw_value = 0
        self.raw_value_time = 0

        self.obs = []

        Base.loop.run_until_complete(self._retrieve_current_state().future)

    def add_obs(self, clb):
        return self.obs.append(clb)

    def rem_obs(self, clb):
        return self.obs.remove(clb)

    async def _get_raw_value(self):
        if Base.loop.time() - self.raw_value_time > self.value_timeout:
            print('Value timeout')
            await self._retrieve_current_state().future
        return self.raw_value

    def _set_raw_value(self, value, updateTime=False):
        Base.logger.debug('set_raw_value called on {cn} with {cv}'.format(cn=self.cn, cv=value))
        old_value = self.raw_value
        self.raw_value = value
        if updateTime:
            self.raw_value_time = Base.loop.time()
        if old_value != value:
            for clb in self.obs:
                asyncio.ensure_future(clb(self))

    def _assure_current_state(self):
        callback_obj = SymNetRawProtocolCallback(
            callback=self._assure_callback,
            expected_lines=1,
            regex='^(ACK)|(NAK)\r$'
        )
        self.proto.callback_queue.append(callback_obj)
        self.proto.write('CS {cn:d} {cv:d}\r'.format(cn=self.cn, cv=self.raw_value))
        return callback_obj

    def _assure_callback(self, data_str, m=None):
        if m is not None and m.group(1) == 'NAK':
            raise Exception('Unknown error occurred awaiting the acknowledge of setting controller number {:d}'.format(self.cn))

    def _retrieve_current_state(self):
        callback_obj = SymNetRawProtocolCallback(
            callback=self._retrieve_callback,
            expected_lines=1,
            regex='^' + str(self.cn) + ' ([0-9]{1,5})\r$'
        )
        self.proto.callback_queue.append(callback_obj)
        self.proto.write('GS2 {:d}\r'.format(self.cn))
        return callback_obj

    def _retrieve_callback(self, data_str, m=None):
        if m is None:
            raise Exception('Error executing GS2 command, controller {}'.format(self.cn))
        self._set_raw_value(int(m.group(1)), updateTime=True)


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

    async def get(self):
        return await self._get_raw_value() > 0

    def set(self, state):
        if state:
            return self.on()
        else:
            return self.off()


class SymNetDevice:
    def __init__(self, local_addr, remote_addr):
        self.controllers = {}
        connect = Base.loop.create_datagram_endpoint(
            SymNetRawProtocol,
            local_addr=local_addr,
            remote_addr=remote_addr
        )
        self.transport, self.protocol = Base.loop.run_until_complete(connect)

        self._process_task = Base.loop.create_task(self._process_push_messages())
        Base.cleanup_tasks.append(Base.loop.create_task(self._cleanup()))

    async def _process_push_messages(self):
        while True:
            cs = await Queues.get_from_queue('symnet_controller_state')
            if cs['cn'] in self.controllers:
                self.controllers[cs['cn']]._set_raw_value(cs['cv'], updateTime=True)

    def define_controller(self, controller_number) -> SymNetController:
        controller_number = int(controller_number)
        controller = SymNetController(controller_number, self.protocol)
        self.controllers[controller_number] = controller

        return controller

    def define_selector(self, controller_number: int, selector_count: int) -> SymNetSelectorController:
        controller_number = int(controller_number)
        controller = SymNetSelectorController(controller_number, selector_count, self.protocol)
        self.controllers[controller_number] = controller

        return controller

    def define_button(self, controller_number) -> SymNetButtonController:
        controller_number = int(controller_number)
        controller = SymNetButtonController(controller_number, self.protocol)
        self.controllers[controller_number] = controller

        return controller

    async def _cleanup(self):
        Base.logger.debug('SymNetDevice awaiting cleanup')
        await Base.cleanup.wait()
        Base.logger.debug('SymNetDevice cancel process_task')
        self._process_task.cancel()
        Base.logger.debug('SymNetDevice close transport')
        self.transport.close()
