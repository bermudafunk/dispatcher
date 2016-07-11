import config

import asyncio


class SymNetRawProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        data_str = data.decode()
        lines = data_str.split('\r')
        lines = [lines[i] for i in range(len(lines)) if len(lines[i]) > 0]

        for line in lines:
            print(line)

    def error_received(self, exc):
        print('Error received:', exc)

    def write(self, data):
        print("Send some data:")
        print(data)
        self.transport.sendto(data.encode())


class EchoClientProtocol(asyncio.Protocol):
    def __init__(self, SymNetProto, loop):
        self.symnetproto = SymNetProto
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        print('Connection from {}'.format(transport.get_extra_info('peername')))
        self.transport = transport
        self.transport.write('Welcome to send debug commands to symnet device\n'.encode())

    def data_received(self, data):
        self.symnetproto.write(data.decode().replace('\n', '\r'))

    def connection_lost(self, exc):
        print('The debug server closed the connection')
        print('Stop the event loop')
        self.loop.stop()


loop = asyncio.get_event_loop()
connect = loop.create_datagram_endpoint(
    SymNetRawProtocol,
    local_addr=(config.myIp, config.myPort),
    remote_addr=(config.remoteIp, config.remotePort)
)
symnet_transport, protocol = loop.run_until_complete(connect)

debug_connect = loop.create_server(lambda: EchoClientProtocol(protocol, loop), '127.0.0.1', 8888)
loop.run_until_complete(debug_connect)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

symnet_transport.close()
loop.close()
