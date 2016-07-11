import bermudafunk.Base
import bermudafunk.GPIO


if __name__ == '__main__':
    bermudafunk.Base.logger.debug('Main Start')

    test_led = bermudafunk.GPIO.Led(7)
    test_led.set_state(test_led.STATE_ON)


    def test(pin):
        global test_led
        if pin is 33:
            test_led.set_state(test_led.STATE_ON)
        elif pin is 35:
            test_led.set_state(test_led.STATE_OFF)
        else:
            test_led.set_state(test_led.STATE_BLINK)


    bermudafunk.GPIO.register_button(33, callback=test)
    bermudafunk.GPIO.register_button(35, callback=test)
    bermudafunk.GPIO.register_button(37, callback=test)

    bermudafunk.Base.run_loop()
