from bermudafunk import Base, GPIO, Symnet, Systemd


class ClassDict(type):
    def __iter__(self):
        for val in self.__dict__.values():
            yield val


class SwitchLogic:
    class Sources(metaclass=ClassDict):
        AUTO = 0x0
        STUDIO_1 = 0x1
        STUDIO_2 = 0x2
        EXTERN = 0x3

    on_air = Sources.AUTO
    instant = Sources.AUTO
    instant_next = Sources.AUTO
    instant_decontrol = False
    decontrol = True
    acquisition = None

    def change_state(self, studio, func):
        if func == 'decontrol':
            self.change_state_decontrol(studio)
        elif func == 'acquisition':
            self.change_state_acquisition(studio)
        elif func == 'instant':
            self.change_state_instant(studio)

    def change_state_decontrol(self, studio):
        if not self.on_air == studio:
            if self.acquisition == studio:
                self.acquisition = None
            return

        pass

    def change_state_acquisition(self, studio):
        pass

    def change_state_instant(self, studio):
        pass


if __name__ == '__main__':
    Base.logger.debug('Main Start')

    try:
        Systemd.setup()
    except:
        pass

    device = Symnet.SymNetDevice(local_addr=(Base.config.myIp, Base.config.myPort),
                                 remote_addr=(Base.config.remoteIp, Base.config.remotePort))
    onAirSwitch = device.define_selector(1, 8)
    monitorSelector = device.define_selector(2, 10)
    monitorButton1 = device.define_button(223)
    monitorButton2 = device.define_button(336)


    async def clb(controller: Symnet.SymNetSelectorController, *args, **kwargs):
        current_position = await controller.get_position()
        print('clb watch {} {}'.format(controller.cn, current_position))


    onAirSwitch.add_obs(clb)
    monitorSelector.add_obs(clb)


    async def test():
        import asyncio
        while not Base.cleanup.is_set():
            print("debugging o/")
            oav = Base.loop.create_task(onAirSwitch.get_position())
            msv = Base.loop.create_task(monitorSelector.get_position())
            mb1v = Base.loop.create_task(monitorButton1.pressed())
            mb2v = Base.loop.create_task(monitorButton2.pressed())
            print(await oav)
            print(await msv)
            print(await mb1v)
            print(await mb2v)

            await asyncio.sleep(15)


    async def test_cleanup():
        await Base.cleanup.wait()
        test_task.cancel()


    # test_task = Base.loop.create_task(test())
    # Base.cleanup_tasks.append(Base.loop.create_task(test_cleanup()))

    from aiohttp import web

    app = web.Application()


    async def onAirSwitchGetHandler(request: web.Request):
        return web.Response(text="curr pos {}".format(await onAirSwitch.get_position()))


    async def onAirSwitchSetHandler(request: web.Request):
        pos = int(request.match_info['pos'])
        print('handler oas {}'.format(pos))
        await onAirSwitch.set_position(pos)
        return web.Response(text="blub")


    app.router.add_get('/oas', onAirSwitchGetHandler)
    app.router.add_get('/oas/{pos}', onAirSwitchSetHandler)

    handler = app.make_handler()
    f = Base.loop.create_server(handler, '0.0.0.0', 8080)
    srv = Base.loop.run_until_complete(f)
    print('serving on', srv.sockets[0].getsockname())


    async def web_app_cleanup():
        await Base.cleanup.wait()
        srv.close()
        await srv.wait_closed()
        await app.shutdown()
        await handler.shutdown(1)
        await app.cleanup()


    async def test_clocks():
        import asyncio
        import time
        import logging

        logger = logging.getLogger('clock_test')
        logger.setLevel(logging.DEBUG)

        time_async_pre, time_time_pre = Base.loop.time(), time.time()

        while not Base.cleanup.is_set():
            time_async, time_time = Base.loop.time(), time.time()

            logger.debug('loop time diff: %s', time_async - time_async_pre)
            logger.debug('time time diff: %s', time_time - time_time_pre)
            logger.debug('diff of the diffs: %s', (time_async - time_async_pre) - (time_time - time_time_pre))

            time_async_pre, time_time_pre = time_async, time_time

            await asyncio.sleep(300)


    async def test_clock_cleanup():
        task = Base.loop.create_task(test_clocks())
        await Base.cleanup.wait()
        task.cancel()


    Base.loop.create_task(test_clock_cleanup())

    Base.cleanup_tasks.append(Base.loop.create_task(web_app_cleanup()))

    Base.run_loop()
