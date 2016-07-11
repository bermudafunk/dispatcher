import asyncio


# Val = (NumOfIn - 1) / (MaxOfIn-1) * 65535
def get_selector_number_by_value(value, selector_count):
    return int(round(value / 65535 * (selector_count - 1) + 1))


def get_value_by_selector_number(selector, selector_count):
    return int(round((selector - 1) / (selector_count - 1) * 65535))


class SymNetRawProtocol(asyncio.DatagramProtocol):
    transport = None

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

# connect = main.loop.create_datagram_endpoint(SymNetRawProtocol, local_addr=(config.myIp, config.myPort), remote_addr=(config.remoteIp, config.remotePort))
# symnet_transport, protocol = main.loop.run_until_complete(connect)
