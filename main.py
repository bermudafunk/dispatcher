import bermudafunk
from bermudafunk import base
from bermudafunk.SymNet import SymNetDevice
from bermudafunk.base import systemd

if __name__ == '__main__':
    base.logger.debug('Main Start')

    try:
        systemd.setup()
    except:
        pass

    device = SymNetDevice(local_address=(base.config.myIp, base.config.myPort),
                          remote_address=(base.config.remoteIp, base.config.remotePort))

    main_selector = device.define_selector(1, 8)

    af_1 = bermudafunk.DispatcherStudio('af_1')
    af_2 = bermudafunk.DispatcherStudio('af_2')

    dispatcher = bermudafunk.Dispatcher(
        symnet_controller=main_selector,
        automat_selector_value=1,
        studio_mapping=[
            bermudafunk.DispatcherStudioDefinition(studio=af_1, selector_value=2),
            bermudafunk.DispatcherStudioDefinition(studio=af_2, selector_value=3),
        ]
    )

    base.run_loop()
