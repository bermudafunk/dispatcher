import struct


def _calc_crc16(data):
    crc = 0xFFFF

    for b in data:
        crc = crc ^ b

        for i in range(0, 8, 1):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1

    return crc


class Pixtend:
    IN_HEADER = struct.Struct('<5B 2x')
    IN_DATA = struct.Struct('<H 6H B 2H 2H 2H 2H 5x 64s')
    IN_FORMAT = struct.Struct('<7s H 100s H')

    OUT_HEADER = struct.Struct('<4B 3x')
    OUT_DATA = struct.Struct('<8B H B 4B B3H B3H B3H 64s')
    OUT_FORMAT = struct.Struct('<7s H 100s H')

    def __init__(self):
        self._model_out = ord('L')
        self._mode = 0
        self._uc_ctrl_0 = 0
        self._uc_ctrl_1 = 0

        self._digital_debounce = (0,) * 8

        self._digital_out = 0
        self._relay_out = 0

        self._gpio_ctrl = 0
        self._gpio_out = 0
        self._gpio_debounce = (0,) * 2

        self._pwm = (0,) * 4 * 3

        self._retain_data_out = bytes()

        self._firmware = -1
        self._hardware = -1
        self._model_in = -1
        self._uc_state = -1
        self._uc_warnings = -1

        self._digital_in = -1

        self._analog_in_voltage = (-1,) * 4
        self._analog_in_current = (-1,) * 2

        self._gpio_in = -1

        self._temp = (-1,) * 4
        self._humid = (-1,) * 4

        self._retain_data_in = bytes()

    def _pack_output(self):
        header_data = self.OUT_HEADER.pack(
            self._model_out,
            self._mode,
            self._uc_ctrl_0,
            self._uc_ctrl_1
        )
        header_crc = _calc_crc16(header_data)

        data = self.OUT_DATA.pack(
            *self._digital_debounce,
            self._digital_out,
            self._relay_out,
            self._gpio_ctrl,
            self._gpio_out,
            *self._gpio_debounce,
            *self._pwm,
            self._retain_data_out
        )
        data_crc = _calc_crc16(data)

        transfer = self.OUT_FORMAT.pack(header_data, header_crc, data, data_crc)

        return transfer

    def _unpack_input(self, transfer):
        (header_data, header_crc, data, data_crc) = self.IN_FORMAT.unpack(transfer)
        if header_crc != _calc_crc16(header_data):
            return

        (
            self._firmware,
            self._hardware,
            self._model_in,
            self._uc_state,
            self._uc_warnings,
        ) = self.IN_HEADER.unpack(header_data)

        if data_crc != _calc_crc16(data):
            return

        (
            self._digital_in,
            self._analog_in_voltage[0],
            self._analog_in_voltage[1],
            self._analog_in_voltage[2],
            self._analog_in_voltage[3],
            self._analog_in_current[0],
            self._analog_in_current[1],
            self._gpio_in,
            self._temp[0],
            self._humid[0],
            self._temp[1],
            self._humid[1],
            self._temp[2],
            self._humid[2],
            self._temp[3],
            self._humid[3],
            self._retain_data_in
        ) = self.IN_DATA.unpack(data)
