import asyncio
import functools
import json
import logging
import weakref
from concurrent.futures import ThreadPoolExecutor

import aiohttp
from aiohttp import web

import bermudafunk.base
from bermudafunk.dispatcher import BaseStudio, ButtonEvent, Button, Dispatcher

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
_websockets = weakref.WeakSet()


def redraw_complete_graph(dispatcher: Dispatcher):
    dispatcher.machine.get_graph().draw('static/full_state_machine.png', prog='dot')


def redraw_graph(dispatcher: Dispatcher):
    dispatcher.machine.get_graph(show_roi=True).draw('static/partial_state_machine.png', prog='dot')


async def run(dispatcher: Dispatcher):
    observer_event = asyncio.Event()

    app = web.Application()

    routes = web.RouteTableDef()

    routes.static('/static', 'static/')

    @routes.get('/')
    async def redirect_to_static_html(_: web.Request) -> web.StreamResponse:
        return web.HTTPFound('/static/index.html')

    @routes.get('/api/v1/full_state_machine')
    async def generate_machine_image(_: web.Request) -> web.StreamResponse:
        await bermudafunk.base.loop.run_in_executor(_executor, functools.partial(redraw_complete_graph, dispatcher))
        return web.HTTPFound('/static/full_state_machine.png')

    @routes.get('/api/v1/partial_state_machine')
    async def generate_machine_image(_: web.Request) -> web.StreamResponse:
        await bermudafunk.base.loop.run_in_executor(_executor, functools.partial(redraw_graph, dispatcher))
        return web.HTTPFound('/static/partial_state_machine.png')

    @routes.get('/api/v1/status')
    async def list_studios(_: web.Request) -> web.StreamResponse:
        return web.json_response(dispatcher.status)

    @routes.get('/api/v1/studio_lamp_names')
    async def list_studios(_: web.Request) -> web.StreamResponse:
        return web.json_response([studio.name for studio in dispatcher.studios_with_automat])

    @routes.get('/api/v1/studio_names')
    async def list_studios(_: web.Request) -> web.StreamResponse:
        return web.json_response([studio.name for studio in dispatcher.studios])

    @routes.get('/api/v1/{studio_name}/press/{button}')
    async def button_press(request: web.Request) -> web.StreamResponse:
        event = ButtonEvent(
            studio=BaseStudio.names[request.match_info['studio_name']],
            button=Button(request.match_info['button'])
        )

        await event.studio.dispatcher_button_event_queue.put(event)

        return web.json_response({'status': 'emitted_button_event'})

    @routes.get('/api/v1/{studio_name}/leds')
    async def led_status(request: web.Request) -> web.StreamResponse:
        studio = BaseStudio.names[request.match_info['studio_name']]

        return web.json_response(studio.led_status)

    @routes.get('/api/v1/ws')
    async def websocket_status(request: web.Request) -> web.StreamResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        _websockets.add(ws)
        await ws.send_str(dispatcher_status_msg())
        for studio in dispatcher.studios_with_automat:
            await ws.send_str(led_status_msg(studio))

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    logger.debug(msg.data)
                    if msg.data == 'close':
                        logger.debug('received close message')
                        await ws.close()
                    else:
                        try:
                            req = json.loads(msg.data)
                            logger.debug(req)
                            if req['type'] == 'dispatcher.status':
                                await ws.send_str(dispatcher_status_msg())
                            elif req['type'] == 'studio.led.status':
                                await ws.send_str(led_status_msg(BaseStudio.names[req['studio']]))
                        except json.JSONDecodeError as e:
                            await ws.send_str(json.dumps({'kind': 'error', 'exception': str(e)}))
                        except TypeError as e:
                            await ws.send_str(json.dumps({'kind': 'error', 'exception': str(e)}))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.debug('ws connection closed with exception %s', ws.exception())

            logger.debug('websocket connection closed')
            await ws.close()
        finally:
            _websockets.discard(ws)

        return ws

    async def close_remaining_websockets():
        logger.debug('closing remaining websockets')
        for ws in set(_websockets):
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message='Server shutdown')

    def observer(*_, **__):
        observer_event.set()

    async def observer_push():
        while True:
            await observer_event.wait()
            for ws in _websockets:
                await ws.send_str(dispatcher_status_msg())
                for studio in dispatcher.studios_with_automat:
                    await ws.send_str(led_status_msg(studio))

            observer_event.clear()

    def dispatcher_status_msg():
        return json.dumps({'kind': 'dispatcher.status', 'payload': dispatcher.status})

    def led_status_msg(studio: BaseStudio):
        return json.dumps({'kind': 'studio.led.status', 'payload': {'studio': studio.name, 'status': studio.led_status}})

    app.add_routes(routes)

    runner = web.AppRunner(app, handle_signals=False)
    await runner.setup()
    site = web.TCPSite(runner, '192.168.96.42', 8080)
    await site.start()
    dispatcher.machine_observers.add(observer)
    observer_push_task = bermudafunk.base.loop.create_task(observer_push())
    await bermudafunk.base.cleanup_event.wait()
    observer_push_task.cancel()
    await close_remaining_websockets()
    logger.debug('closed remaining websockets')
    await runner.cleanup()
    logger.debug('runner cleanup ran')
