from bermudafunk import base
from bermudafunk.SymNet import SymNetDevice
from bermudafunk.dispatcher import web
from bermudafunk.dispatcher.data_types import DispatcherStudioDefinition, Studio, Automat
from bermudafunk.dispatcher.dispatcher import Dispatcher
from bermudafunk.io.pixtend import PixtendLamp, Pixtend

if __name__ == '__main__':
    base.logger.debug('Main Start')

    pixtend = Pixtend()
    base.cleanup_tasks.append(base.loop.create_task(pixtend.cleanup_aware_shutdown()))

    device = SymNetDevice(local_address=(base.config.myIp, base.config.myPort),
                          remote_address=(base.config.remoteIp, base.config.remotePort))

    main_selector = device.define_selector(1, 8)

    automat = Automat(
        green_lamp=PixtendLamp(name='Automat Green', channel=0, pixtend=pixtend),
        yellow_lamp=PixtendLamp(name='Automat Yellow', channel=1, pixtend=pixtend),
    )

    af_1 = Studio(
        name='AlteFeuerwache1',
        green_lamp=PixtendLamp(name='AF1 Green', channel=2, pixtend=pixtend),
        yellow_lamp=PixtendLamp(name='AF1 Yellow', channel=3, pixtend=pixtend),
        red_lamp=PixtendLamp(name='AF1 RED', channel=8, pixtend=pixtend),
    )
    af_2 = Studio(
        name='AlteFeuerwache2',
        green_lamp=PixtendLamp(name='AF2 Green', channel=4, pixtend=pixtend),
        yellow_lamp=PixtendLamp(name='AF2 Yellow', channel=5, pixtend=pixtend),
        red_lamp=PixtendLamp(name='AF2 RED', channel=9, pixtend=pixtend),
    )
    af_3 = Studio(
        name='Aussenstelle',
        green_lamp=PixtendLamp(name='AF2 Green', channel=6, pixtend=pixtend),
        yellow_lamp=PixtendLamp(name='AF2 Yellow', channel=7, pixtend=pixtend),
    )

    dispatcher = Dispatcher(
        symnet_controller=main_selector,
        automat=DispatcherStudioDefinition(
            studio=automat,
            selector_value=1
        ),
        dispatcher_studios=[
            DispatcherStudioDefinition(studio=af_1, selector_value=2),
            DispatcherStudioDefinition(studio=af_2, selector_value=3),
            DispatcherStudioDefinition(studio=af_3, selector_value=4),
        ],
    )
    dispatcher.load()
    dispatcher.start()

    base.cleanup_tasks.append(base.loop.create_task(web.run(dispatcher)))

    base.run_loop()
