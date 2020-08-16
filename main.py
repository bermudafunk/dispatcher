import bermudafunk.dispatcher
from bermudafunk import base
from bermudafunk.SymNet import SymNetDevice
from bermudafunk.dispatcher import web
from bermudafunk.io.pixtend import PixtendLamp, Pixtend

if __name__ == '__main__':
    base.logger.debug('Main Start')

    pixtend = Pixtend()

    device = SymNetDevice(local_address=(base.config.myIp, base.config.myPort),
                          remote_address=(base.config.remoteIp, base.config.remotePort))

    main_selector = device.define_selector(1, 8)

    af_1 = bermudafunk.dispatcher.Studio(
        name='AlteFeuerwache1',
        green_led=PixtendLamp(name="AF1 Green", channel=2, pixtend=pixtend),
        yellow_led=PixtendLamp(name="AF1 Yellow", channel=3, pixtend=pixtend),
        red_led=PixtendLamp(name="AF1 RED", channel=8, pixtend=pixtend),
    )
    af_2 = bermudafunk.dispatcher.Studio(
        name='AlteFeuerwache2',
        green_led=PixtendLamp(name="AF2 Green", channel=4, pixtend=pixtend),
        yellow_led=PixtendLamp(name="AF2 Yellow", channel=5, pixtend=pixtend),
        red_led=PixtendLamp(name="AF2 RED", channel=9, pixtend=pixtend),
    )
    af_3 = bermudafunk.dispatcher.Studio(
        name='Außenstelle',
        green_led=PixtendLamp(name="AF2 Green", channel=6, pixtend=pixtend),
        yellow_led=PixtendLamp(name="AF2 Yellow", channel=7, pixtend=pixtend),
    )

    dispatcher = bermudafunk.dispatcher.Dispatcher(
        symnet_controller=main_selector,
        automat_selector_value=1,
        studios=[
            bermudafunk.dispatcher.DispatcherStudioDefinition(studio=af_1, selector_value=2),
            bermudafunk.dispatcher.DispatcherStudioDefinition(studio=af_2, selector_value=3),
            bermudafunk.dispatcher.DispatcherStudioDefinition(studio=af_3, selector_value=4),
        ]
    )
    dispatcher.load()
    dispatcher.start()

    bermudafunk.base.cleanup_tasks.append(bermudafunk.base.loop.create_task(web.run(dispatcher)))
    bermudafunk.base.cleanup_tasks.append(bermudafunk.base.loop.create_task(pixtend.cleanup_aware_shutdown()))

    base.run_loop()
