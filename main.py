import bermudafunk.dispatcher
from bermudafunk import base
from bermudafunk.SymNet import SymNetDevice
from bermudafunk.dispatcher import web

if __name__ == '__main__':
    base.logger.debug('Main Start')

    device = SymNetDevice(local_address=(base.config.myIp, base.config.myPort),
                          remote_address=(base.config.remoteIp, base.config.remotePort))

    main_selector = device.define_selector(1, 8)

    af_1 = bermudafunk.dispatcher.Studio('af_1')
    af_2 = bermudafunk.dispatcher.Studio('af_2')
    af_3 = bermudafunk.dispatcher.Studio('af_3')

    dispatcher = bermudafunk.dispatcher.Dispatcher(
        symnet_controller=main_selector,
        automat_selector_value=1,
        studio_mapping=[
            bermudafunk.dispatcher.DispatcherStudioDefinition(studio=af_1, selector_value=2),
            bermudafunk.dispatcher.DispatcherStudioDefinition(studio=af_2, selector_value=3),
            bermudafunk.dispatcher.DispatcherStudioDefinition(studio=af_3, selector_value=4),
        ]
    )
    dispatcher.load()

    bermudafunk.base.loop.create_task(web.run(dispatcher))

    base.run_loop()
