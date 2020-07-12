import enum
import struct
import typing


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


def _bit_getter(field_name, bit, doc=None):
    def getter(instance) -> bool:
        return instance.__dict__[field_name] & (1 << bit) > 0

    return property(fget=getter, doc=doc)


def _bit_getter_setter(field_name, bit, doc=None):
    def getter(instance) -> bool:
        return instance.__dict__[field_name] & (1 << bit) > 0

    def setter(instance, val: bool):
        if bool:
            instance.__dict__[field_name] |= (1 << bit)
        else:
            instance.__dict__[field_name] &= ~(1 << bit)

    return property(fget=getter, fset=setter, doc=doc)


@enum.unique
class PixtendWatchDog(enum.IntEnum):
    OFF = 0
    ON_16MS = 0b0001
    ON_32MS = 0b0010
    ON_64MS = 0b0011
    ON_125MS = 0b0100
    ON_250MS = 0b0101
    ON_500MS = 0b0110
    ON_1S = 0b0111
    ON_2S = 0b1000
    ON_4S = 0b1001
    ON_8S = 0b1010


@enum.unique
class PixtendGPIOSetting(enum.Enum):
    INPUT = enum.auto()
    OUTPUT = enum.auto()
    SENSOR = enum.auto()


@enum.unique
class PixtendError(enum.Enum):
    NONE = 0b0000
    CRC_DATA = 0b0010
    DATA_SHORT = 0b0011
    MODEL = 0b0100
    CRC_HEADER = 0b0101
    SPI_FREQUENCY_TOO_HIGH = 0b0110


class Pixtend:
    IN_HEADER = struct.Struct('<5B 2x')
    IN_DATA = struct.Struct('<H 6H B 2H 2H 2H 2H 5x 64s')
    IN_FORMAT = struct.Struct('<7s H 100s H')

    OUT_HEADER = struct.Struct('<4B 3x')
    OUT_DATA = struct.Struct('<8B H B 4B B3H B3H B3H 64s')
    OUT_FORMAT = struct.Struct('<7s H 100s H')

    def __init__(self):
        self._communication_interval_ms = 30

        self._model_out = ord('L')
        self._mode = 0
        self._uc_ctrl_0 = 0
        self._uc_ctrl_1 = 0

        self._digital_debounce = [0] * 8

        self._digital_out = 0
        self._relay_out = 0

        self._gpio_ctrl = 0
        self._gpio_out = 0
        self._gpio_debounce = [0] * 2

        self._pwm = [0] * 4 * 3

        self._retain_data_out = bytes()

        self._firmware = -1
        self._hardware = -1
        self._model_in = -1
        self._uc_state = -1
        self._uc_warnings = -1

        self._digital_in = -1

        self._analog_in_voltage = [-1] * 4
        self._analog_in_current = [-1] * 2

        self._gpio_in = -1

        self._temp = [-1] * 4
        self._humid = [-1] * 4

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

    safe = _bit_getter_setter('_uc_ctrl_1', 0)
    retain_copy = _bit_getter_setter('_uc_ctrl_1', 1)
    retain_enable = _bit_getter_setter('_uc_ctrl_1', 2)
    status_led = _bit_getter_setter('_uc_ctrl_1', 3)
    gpio_pullup_enable = _bit_getter_setter('_uc_ctrl_1', 4)

    run = _bit_getter('_uc_state', 0)

    @property
    def error(self) -> PixtendError:
        return PixtendError(self._uc_state >> 4)

    retain_crc_error = _bit_getter('_uc_warnings', 1)
    retain_voltage_error = _bit_getter('_uc_warnings', 2)
    pwm_i2c_error = _bit_getter('_uc_warnings', 3)

    def digital_out(self, channel: int, val: typing.Optional[bool] = None) -> bool:
        if not (0 <= channel <= 11):
            raise ValueError('Digital output channel must be between 0 and 11')
        if val is not None:
            if val:
                self._digital_out |= (1 << channel)
            else:
                self._digital_out &= ~(1 << channel)
        return self._digital_out & (1 << channel) > 0

    def digital_in(self, channel: int) -> bool:
        if not (0 <= channel <= 15):
            raise ValueError('Digital input channel must be between 0 and 15')
        if self._digital_in < 0:
            raise RuntimeError('No successful transfer between Pixtend and Pi yet')
        return self._digital_in & (1 << channel) > 0

    def digital_in_debounce_cycles(self, channel_duo: int, val: typing.Optional[int] = None) -> int:
        if not (0 <= channel_duo <= 7):
            raise ValueError('Digital debounce channel_duo must be between 0 and 7')
        if val is not None:
            val = int(val)
            if not (0 <= val <= 255):
                raise ValueError('Digital debounce cycles must be between 0 and 255')
            self._digital_debounce[channel_duo] = val
        return self._digital_debounce[channel_duo]

    def digital_in_debounce_seconds(self, channel_duo: int) -> float:
        return self.digital_in_debounce_cycles(channel_duo) * self._communication_interval_ms / 1000

    def relay_out(self, channel: int, val: typing.Optional[bool] = None) -> bool:
        if not (0 <= channel <= 3):
            raise ValueError('Relay output channel must be between 0 and 3')
        if val is not None:
            if val:
                self._relay_out |= (1 << channel)
            else:
                self._relay_out &= ~(1 << channel)
        return self._relay_out & (1 << channel) > 0

    def gpio_ctrl(self, channel: int, setting: PixtendGPIOSetting = None):
        if not (0 <= channel <= 3):
            raise ValueError('GPIO channel must be between 0 and 3')
        if setting is not None:
            if not isinstance(setting, PixtendGPIOSetting):
                raise ValueError('GPIO channel settings must be a value of PixtendGPIOSetting')
            # Clear channel setting, default is INPUT
            self._gpio_ctrl &= ~(1 << channel | 1 << (channel + 4))
            if setting is PixtendGPIOSetting.OUTPUT:
                self._gpio_ctrl |= (1 << channel)
            elif setting is PixtendGPIOSetting.SENSOR:
                self._gpio_ctrl |= (1 << (channel + 4))
        channel_val = (self._gpio_ctrl >> channel) & 0b10001
        if channel_val == 0:
            return PixtendGPIOSetting.INPUT
        elif channel_val == 1:
            return PixtendGPIOSetting.OUTPUT
        elif channel_val == 16:
            return PixtendGPIOSetting.SENSOR
        raise RuntimeError('Invalid value detected in gpio_ctrl byte')

    def gpio_out(self, channel: int, val: typing.Optional[bool] = None) -> bool:
        if not (0 <= channel <= 3):
            raise ValueError('GPIO output channel must be between 0 and 3')
        if self.gpio_ctrl(channel) is not PixtendGPIOSetting.OUTPUT:
            raise RuntimeError('GPIO channel must be configured as OUTPUT')
        if val is not None:
            if val:
                self._gpio_out |= (1 << channel)
            else:
                self._gpio_out &= ~(1 << channel)
        return self._gpio_out & (1 << channel) > 0

    def gpio_in(self, channel: int) -> bool:
        if not (0 <= channel <= 3):
            raise ValueError('GPIO input channel must be between 0 and 3')
        if self.gpio_ctrl(channel) is not PixtendGPIOSetting.INPUT:
            raise RuntimeError('GPIO channel must be configured as INPUT')
        if self._gpio_in < 0:
            raise RuntimeError('No successful transfer between Pixtend and Pi yet')
        return self._gpio_in & (1 << channel) > 0

    def gpio_pullup(self, channel: int, val: typing.Optional[bool] = None) -> bool:
        if not (0 <= channel <= 3):
            raise ValueError('GPIO input channel must be between 0 and 3')
        if self.gpio_ctrl(channel) is not PixtendGPIOSetting.INPUT:
            raise RuntimeError('GPIO channel must be configured as INPUT')
        if val is not None:
            if val:
                self._gpio_out |= (1 << channel)
            else:
                self._gpio_out &= ~(1 << channel)
        return self._gpio_out & (1 << channel) > 0

    def gpio_in_debounce_cycles(self, channel_duo: int, val: typing.Optional[int] = None):
        if not (0 <= channel_duo <= 1):
            raise ValueError('GPIO debounce channel_duo must be 0 and 1')
        if val is not None:
            val = int(val)
            if not (0 <= val <= 255):
                raise ValueError('GPIO debounce cycles must be between 0 and 255')
            self._gpio_debounce[channel_duo] = val
        return self._digital_debounce[channel_duo]

    def gpio_in_debounce_seconds(self, channel_duo: int) -> float:
        return self.gpio_in_debounce_cycles(channel_duo) * self._communication_interval_ms / 1000

    @property
    def retain_data_out(self) -> bytes:
        return self._retain_data_out

    @retain_data_out.setter
    def retain_data_out(self, val: bytes):
        val = bytes(val)
        if len(val) > 64:
            raise ValueError('Retain data are allowed to be 64 bytes')
        self._retain_data_out = val

    @property
    def retain_data_in(self) -> bytes:
        return self._retain_data_in

    def analog_in_voltage(self, channel) -> float:
        if not (0 <= channel <= 3):
            raise ValueError('Analog input voltage channel must be between 0 and 3')
        if self._analog_in_voltage[channel] < 0:
            raise RuntimeError('No successful transfer between Pixtend and Pi yet')
        return self._analog_in_voltage[channel] * 10 / 1024

    def analog_in_current(self, channel) -> float:
        if not (4 <= channel <= 5):
            raise ValueError('Analog input current channel must be between 4 and 5')
        if self._analog_in_current[channel - 4] < 0:
            raise RuntimeError('No successful transfer between Pixtend and Pi yet')
        return self._analog_in_current[channel - 4] * 0.020158400229358

    @property
    def watchdog(self) -> PixtendWatchDog:
        return PixtendWatchDog(self._uc_ctrl_0)

    @watchdog.setter
    def watchdog(self, val: PixtendWatchDog):
        val = int(val)
        if not (0 <= val <= 10):
            raise ValueError('UCCtrl0 / Watchdog has to be between 0 and 10')
        self._uc_ctrl_0 = val
