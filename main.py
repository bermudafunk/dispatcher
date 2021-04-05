from bermudafunk import base
from bermudafunk.dispatcher import web
from bermudafunk.dispatcher.data_types import Automat, DispatcherStudioDefinition, Studio
from bermudafunk.dispatcher.dispatcher import Dispatcher
from bermudafunk.io.pixtend import Pixtend, PixtendTriColorLamp
from bermudafunk.symnet import SymNetDevice

if __name__ == '__main__':
    base.logger.debug('Main Start')

    pixtend = Pixtend()
    base.cleanup_tasks.append(base.loop.create_task(pixtend.cleanup_aware_shutdown()))

    device = SymNetDevice(local_address=(base.config.myIp, base.config.myPort),
                          remote_address=(base.config.remoteIp, base.config.remotePort))

    main_selector = device.define_selector(1, 8)

    automat = Automat(
        main_lamp=PixtendTriColorLamp(
            name='Automat Main Lamp',
            pixtend=pixtend,
            channel_1=0,
            channel_2=1,
        ),
    )

    af_1 = Studio(
        name='AlteFeuerwache1',
        main_lamp=PixtendTriColorLamp(
            name='Alte Feuerwache 1 Main Lamp',
            pixtend=pixtend,
            channel_1=2,
            channel_2=3,
        ),
        immediate_lamp=PixtendTriColorLamp(
            name='Alte Feuerwache 1 Immediate Lamp',
            pixtend=pixtend,
            channel_1=8,
            channel_2=9,
        ),
    )
    af_2 = Studio(
        name='AlteFeuerwache2',
        main_lamp=PixtendTriColorLamp(
            name='Alte Feuerwache 2 Main Lamp',
            pixtend=pixtend,
            channel_1=4,
            channel_2=5,
        ),
        immediate_lamp=PixtendTriColorLamp(
            name='Alte Feuerwache 2 Immediate Lamp',
            pixtend=pixtend,
            channel_1=10,
            channel_2=11,
        ),
    )
    af_3 = Studio(
        name='Aussenstelle',
        main_lamp=PixtendTriColorLamp(
            name='Außenstelle Main Lamp',
            pixtend=pixtend,
            channel_1=6,
            channel_2=7,
        ),
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
