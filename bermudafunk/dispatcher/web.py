import functools
from concurrent.futures import ThreadPoolExecutor

from aiohttp import web

import bermudafunk.base
from bermudafunk.dispatcher import Studio, ButtonEvent, Button, Dispatcher

_executor = ThreadPoolExecutor(max_workers=2)


def redraw_complete_graph(dispatcher: Dispatcher):
    dispatcher.machine.get_graph().draw('static/my_state_diagram.png', prog='dot')


def redraw_graph(dispatcher: Dispatcher):
    dispatcher.machine.get_graph(show_roi=True).draw('static/my_state_diagram.png', prog='dot')


async def run(dispatcher: Dispatcher):
    routes = web.RouteTableDef()

    routes.static('/static', 'static/')

    @routes.get('/')
    async def redirect_to_static_html(_: web.Request) -> web.StreamResponse:
        return web.HTTPFound('/static/index.html')

    @routes.get('/api/v1/generate_state_machine_image')
    async def generate_machine_image(_: web.Request) -> web.StreamResponse:
        await bermudafunk.base.loop.run_in_executor(_executor, functools.partial(redraw_complete_graph, dispatcher))
        return web.HTTPFound('/static/my_state_diagram.png')

    @routes.get('/api/v1/status')
    async def list_studios(_: web.Request) -> web.StreamResponse:
        return web.json_response(
            {
                'state': dispatcher.machine.state,
                'on_air_studio': dispatcher.on_air_studio_name,
                'x': dispatcher.x.name if dispatcher.x else None,
                'y': dispatcher.y.name if dispatcher.y else None,
            }
        )

    @routes.get('/api/v1/studios')
    async def list_studios(_: web.Request) -> web.StreamResponse:
        return web.json_response([studio.name for studio in dispatcher.studios])

    @routes.get('/api/v1/press/{studio_name}/{button}')
    async def button_press(request: web.Request) -> web.StreamResponse:
        event = ButtonEvent(
            studio=Studio.names[request.match_info['studio_name']],
            button=Button(request.match_info['button'])
        )

        await event.studio.dispatcher_button_event_queue.put(event)

        return web.json_response({'status': 'emitted_button_event'})

    @routes.get('/api/v1/leds/{studio_name}')
    async def led_status(request: web.Request) -> web.StreamResponse:
        studio = Studio.names[request.match_info['studio_name']]

        return web.json_response(studio.led_status)

    app = web.Application()
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '192.168.0.133', 8080)
    await site.start()
    await bermudafunk.base.cleanup_event.wait()
    await runner.cleanup()
