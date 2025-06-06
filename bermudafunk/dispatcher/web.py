import asyncio
import functools
import itertools
import logging
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import aiohttp_remotes
import prometheus_async
from aiohttp import web
from symnet_cp import SymNetSelectorController

from bermudafunk.base import json
from bermudafunk.dispatcher.data_types import BaseStudio, Button, ButtonEvent
from bermudafunk.dispatcher.dispatcher import Dispatcher
from bermudafunk.io.common import LampState, TriColorLampColor, TriColorLampState

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="GraphRenderer")
_websockets = weakref.WeakSet()


def redraw_complete_graph(dispatcher: Dispatcher):
    dispatcher.machine.get_graph(force_new=True).draw("static/full_state_machine.png", prog="dot")


def redraw_graph(dispatcher: Dispatcher):
    dispatcher.machine.get_graph(force_new=True, show_roi=True).draw("static/partial_state_machine.png", prog="dot")


async def cycle_all_leds(studios: list[BaseStudio], delay: float):
    for color in itertools.cycle(TriColorLampColor):
        lamp_state = TriColorLampState(color=color, state=LampState.ON)
        for studio in studios:
            studio.main_lamp.color_lamp_state = lamp_state
            studio.immediate_lamp.color_lamp_state = lamp_state
        await asyncio.sleep(delay)


async def run(dispatcher: Dispatcher, ukw_selector: SymNetSelectorController):
    dispatcher_observer_event = asyncio.Event()
    lamp_observer_event = asyncio.Event()

    app = web.Application()
    await aiohttp_remotes.XForwardedRelaxed().setup(app)

    debug_task_key = web.AppKey("debug_task_key", asyncio.Task | None)
    app[debug_task_key] = None

    routes = web.RouteTableDef()

    routes.static("/static", "static/")

    @routes.get("/")
    async def redirect_to_static_html(_: web.Request) -> web.StreamResponse:
        return web.HTTPFound("/static/index.html")

    @routes.get("/ip")
    async def ip(req: web.Request) -> web.Response:
        return web.Response(body=req.remote)


    @routes.get("/threads")
    async def thread_names(_: web.Request) -> web.StreamResponse:
        return web.json_response([thread.name for thread in threading.enumerate()])

    @routes.get("/live")
    async def live(_: web.Request) -> web.Response:
        body = "1" if dispatcher.studio_on_air else "0"
        return web.Response(body=body)

    @routes.get("/ukw_selector")
    async def get_ukw_selector(_: web.Request) -> web.Response:
        position = await ukw_selector.get_position()
        return web.Response(body=str(position))

    @routes.post("/ukw_selector")
    async def set_ukw_selector(request: web.Request) -> web.Response:
        data = await request.json()
        try:
            await ukw_selector.set_position(int(data["position"]))
            return web.Response()
        except Exception as e:
            return web.Response(status=500, body=f"Error occurred: {e!r}")

    @routes.get("/debug/start")
    async def debug_start(_: web.Request) -> web.Response:
        if app[debug_task_key] is None:
            app[debug_task_key] = asyncio.create_task(cycle_all_leds(dispatcher.studios_with_automat, 2))
        return web.Response(status=200, body="Debug mode started")

    @routes.get("/debug/stop")
    async def debug_stop(_: web.Request) -> web.Response:
        if app[debug_task_key] is not None:
            app[debug_task_key].cancel()
            app[debug_task_key] = None
        dispatcher._assure_lamp_state()
        return web.Response(status=200, body="Debug mode stopped")

    @routes.get("/api/v1/full_state_machine")
    async def generate_full_machine_image(_: web.Request) -> web.StreamResponse:
        await asyncio.get_running_loop().run_in_executor(None, functools.partial(redraw_complete_graph, dispatcher))
        return web.HTTPFound("/static/full_state_machine.png")

    @routes.get("/api/v1/partial_state_machine")
    async def generate_partial_machine_image(_: web.Request) -> web.StreamResponse:
        await asyncio.get_running_loop().run_in_executor(None, functools.partial(redraw_graph, dispatcher))
        return web.HTTPFound("/static/partial_state_machine.png")

    @routes.get("/api/v1/status")
    async def dispatcher_status(_: web.Request) -> web.StreamResponse:
        return web.json_response(dispatcher.status, dumps=json.dumps)

    @routes.get("/api/v1/studio_lamp_names")
    async def studio_lamp_names(_: web.Request) -> web.StreamResponse:
        return web.json_response([studio.name for studio in dispatcher.studios_with_automat], dumps=json.dumps)

    @routes.get("/api/v1/studio_names")
    async def studio_names(request: web.Request) -> web.StreamResponse:
        names = [studio.name for studio in dispatcher.studios]
        if "x-studio" in request.headers:
            names = [request.headers["x-studio"]]

        return web.json_response(names, dumps=json.dumps)

    @routes.get("/api/v1/{studio_name}/press/{button}")
    async def button_press(request: web.Request) -> web.StreamResponse:
        studio = request.match_info["studio_name"]
        button = request.match_info["button"]

        if "x-studio" in request.headers:
            expected_studio = request.headers["x-studio"]
            if expected_studio != studio:
                raise web.HTTPForbidden(reason=f"Wrong studio, got {studio} instead of {expected_studio}")

        event = ButtonEvent(studio=BaseStudio.names[studio], button=Button(button))

        await event.studio.dispatcher_button_event_queue.put(event)

        return web.json_response({"status": "emitted_button_event"}, dumps=json.dumps)

    @routes.get("/api/v1/{studio_name}/lamps")
    async def lamp_state(request: web.Request) -> web.StreamResponse:
        studio = BaseStudio.names[request.match_info["studio_name"]]

        return web.json_response(studio.lamp_state, dumps=json.dumps)

    @routes.get("/api/v1/ws")
    async def websocket_status(request: web.Request) -> web.StreamResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        _websockets.add(ws)
        await ws.send_str(dispatcher_status_msg())
        for studio in dispatcher.studios_with_automat:
            await ws.send_str(lamp_state_msg(studio))

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    logger.debug(msg.data)
                    if msg.data == "close":
                        logger.debug("received close message")
                        await ws.close()
                    else:
                        try:
                            req = json.loads(msg.data)
                            logger.debug(req)
                            if req["type"] == "dispatcher.status":
                                await ws.send_str(dispatcher_status_msg())
                            elif req["type"] == "studio.lamp.status":
                                await ws.send_str(lamp_state_msg(BaseStudio.names[req["studio"]]))
                        except json.JSONDecodeError as e:
                            await ws.send_str(json.dumps({"kind": "error", "exception": str(e)}))
                        except TypeError as e:
                            await ws.send_str(json.dumps({"kind": "error", "exception": str(e)}))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.debug("ws connection closed with exception %s", ws.exception())

            logger.debug("websocket connection closed")
            await ws.close()
        finally:
            _websockets.discard(ws)

        return ws

    async def close_remaining_websockets():
        logger.debug("closing remaining websockets")
        for ws in set(_websockets):
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message="Server shutdown")

    def dispatcher_observer(*_, **__):
        dispatcher_observer_event.set()

    async def dispatcher_observer_push():
        while True:
            await dispatcher_observer_event.wait()
            for ws in _websockets:
                await ws.send_str(dispatcher_status_msg())
                for studio in dispatcher.studios_with_automat:
                    await ws.send_str(lamp_state_msg(studio))
            dispatcher_observer_event.clear()

    def lamp_observer(*_, **__):
        lamp_observer_event.set()

    async def lamp_observer_push():
        while True:
            await lamp_observer_event.wait()
            for ws in _websockets:
                for studio in dispatcher.studios_with_automat:
                    await ws.send_str(lamp_state_msg(studio))
            lamp_observer_event.clear()

    def dispatcher_status_msg():
        return json.dumps({"kind": "dispatcher.status", "payload": dispatcher.status})

    def lamp_state_msg(studio: BaseStudio):
        return json.dumps({"kind": "studio.lamp.status", "payload": {"studio": studio.name, "status": studio.lamp_state}})

    app.add_routes(routes)
    app.router.add_get("/metrics", prometheus_async.aio.web.server_stats)

    runner = web.AppRunner(app, handle_signals=False)
    await runner.setup()
    site = web.TCPSite(runner, None, 8080)
    await site.start()
    dispatcher.machine_observers.add(dispatcher_observer)
    dispatcher_observer_push_task = asyncio.create_task(dispatcher_observer_push())
    for studio_ in dispatcher.studios:
        studio_.immediate_lamp.add_observer(lamp_observer)
    lamp_observer_push_task = asyncio.create_task(lamp_observer_push())
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    dispatcher_observer_push_task.cancel()
    lamp_observer_push_task.cancel()
    await close_remaining_websockets()
    logger.debug("closed remaining websockets")
    await runner.cleanup()
    logger.debug("runner cleanup ran")
