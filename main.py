import asyncio
import functools
import signal

import symnet_cp

from bermudafunk import base
from bermudafunk.dispatcher import web
from bermudafunk.dispatcher.data_types import Automat, DispatcherStudioDefinition, Studio
from bermudafunk.dispatcher.dispatcher import Dispatcher
from bermudafunk.io.common import Observable
from bermudafunk.io.pixtend import Pixtend, PixtendButton, PixtendTriColorLamp


async def main():
    def ask_exit(signame):
        base.logger.error("got signal %s: exit" % signame)
        for task in asyncio.all_tasks():
            task.cancel()

    loop = asyncio.get_running_loop()

    for signame in {"SIGINT", "SIGTERM"}:
        loop.add_signal_handler(
            getattr(signal, signame), functools.partial(ask_exit, signame)
        )

    base.logger.debug("Main Start")
    Observable.loop = asyncio.get_running_loop()

    pixtend = Pixtend(autostart=False)

    device = await symnet_cp.SymNetDevice.create(
        local_address=(base.config.myIp, base.config.myPort), remote_address=(base.config.remoteIp, base.config.remotePort)
    )

    main_selector = await device.define_selector(1, 8)

    automat = Automat(
        main_lamp=PixtendTriColorLamp(
            name="Automat Main Lamp",
            pixtend=pixtend,
            channel_1=0,
            channel_2=1,
        ),
    )

    af_1 = Studio(
        name="AlteFeuerwache1",
        main_lamp=PixtendTriColorLamp(
            name="Alte Feuerwache 1 Main Lamp",
            pixtend=pixtend,
            channel_1=2,
            channel_2=3,
        ),
        immediate_lamp=PixtendTriColorLamp(
            name="Alte Feuerwache 1 Immediate Lamp",
            pixtend=pixtend,
            channel_1=8,
            channel_2=9,
        ),
        release_button=PixtendButton(
            name="Alte Feuerwache 1 Freigeben",
            pixtend=pixtend,
            channel=0,
        ),
        takeover_button=PixtendButton(
            name="Alte Feuerwache 1 Übernahme",
            pixtend=pixtend,
            channel=1,
        ),
        immediate_button=PixtendButton(
            name="Alte Feuerwache 1 Sofort",
            pixtend=pixtend,
            channel=2,
        ),
    )
    af_2 = Studio(
        name="AlteFeuerwache2",
        main_lamp=PixtendTriColorLamp(
            name="Alte Feuerwache 2 Main Lamp",
            pixtend=pixtend,
            channel_1=4,
            channel_2=5,
        ),
        immediate_lamp=PixtendTriColorLamp(
            name="Alte Feuerwache 2 Immediate Lamp",
            pixtend=pixtend,
            channel_1=10,
            channel_2=11,
        ),
        release_button=PixtendButton(
            name="Alte Feuerwache 2 Freigeben",
            pixtend=pixtend,
            channel=4,
        ),
        takeover_button=PixtendButton(
            name="Alte Feuerwache 2 Übernahme",
            pixtend=pixtend,
            channel=5,
        ),
        immediate_button=PixtendButton(
            name="Alte Feuerwache 2 Sofort",
            pixtend=pixtend,
            channel=6,
        ),
    )
    af_3 = Studio(
        name="Aussenstelle",
        main_lamp=PixtendTriColorLamp(
            name="Außenstelle Main Lamp",
            pixtend=pixtend,
            channel_1=6,
            channel_2=7,
        ),
    )

    dispatcher = Dispatcher(
        symnet_controller=main_selector,
        automat=DispatcherStudioDefinition(studio=automat, selector_value=1),
        dispatcher_studios=[
            DispatcherStudioDefinition(studio=af_1, selector_value=2),
            DispatcherStudioDefinition(studio=af_2, selector_value=3),
            DispatcherStudioDefinition(studio=af_3, selector_value=4),
        ],
    )
    dispatcher.load()
    dispatcher.start()
    pixtend.start_communication_thread()

    ukw_selector = await device.define_selector(2, 2)

    web_run_task = asyncio.create_task(web.run(dispatcher, ukw_selector))
    base.cleanup_tasks.append(web_run_task)

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await device.cleanup()
        await asyncio.wait(base.cleanup_tasks)


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
