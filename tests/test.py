import config

import socket


# Val = (NumOfIn - 1) / (MaxOfIn-1) * 65535
def get_selector_number_by_value(value, selector_count):
    return int(round(value / 65535 * (selector_count - 1) + 1))


def get_value_by_selector_number(selector, selector_count):
    return int(round((selector - 1) / (selector_count - 1) * 65535))


sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM,
)
sock.bind((config.myIp, config.myPort))
'CS {controller} {value}\r'.format(controller=11, value=get_value_by_selector_number(1, 8))
sock.sendto('PUE\r'.encode(), (config.remoteIp, config.remotePort))
raw_answer = sock.recv(1024)
print(raw_answer)
answers_string = raw_answer.decode()

answers = answers_string.split("\r")

# for answer in answers:
#    if len(answer) > 0:
#        print(answer)
#        m = re.match('(\d+) (\d+)', answer)
#
#        controller = int(m.group(1))
#        value = int(m.group(2))
#        print(get_selector_number_by_value(value, 8))
