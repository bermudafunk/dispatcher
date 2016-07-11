from bermudafunk import Base, GPIO, Symnet, Systemd

if __name__ == '__main__':
    Base.logger.debug('Main Start')
    try:
        Systemd.setup()
    finally:
        pass

    device = Symnet.SymNetDevice(local_addr=(Base.config.myIp, Base.config.myPort), remote_addr=(Base.config.remoteIp, Base.config.remotePort))
    onAirSwitch = device.define_selector(10, 4)
    monitorSelector = device.define_selector(12, 8)

    async def clb(controller: Symnet.SymNetSelectorController):
        current_position = await controller.get_position()
        if current_position == 1:
            test_led.set_state(test_led.STATE_BLINK)
        elif current_position == 2:
            test_led.set_state(test_led.STATE_ON)
        elif current_position == 3:
            test_led.set_state(test_led.STATE_OFF)
        print(current_position)


    onAirSwitch.add_obs(clb)
    monitorSelector.add_obs(clb)


    async def button_clb(pin):
        if pin is 33:
            await onAirSwitch.set_position(1)
        elif pin is 35:
            await onAirSwitch.set_position(2)
        elif pin is 37:
            await onAirSwitch.set_position(3)


    GPIO.register_button(33, coroutine=button_clb)
    GPIO.register_button(35, coroutine=button_clb)
    GPIO.register_button(37, coroutine=button_clb)

    test_led = GPIO.Led(7)
    test_led.set_state(GPIO.Led.STATE_ON)

    test_led2 = GPIO.Led(13)
    test_led2.set_state(GPIO.Led.STATE_BLINK)

    Base.run_loop()
