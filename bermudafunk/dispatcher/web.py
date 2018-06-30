from aiohttp import web

import bermudafunk.base
from bermudafunk.dispatcher import Studio, ButtonEvent, Button

routes = web.RouteTableDef()

routes.static('/static', 'static/')


@routes.get('/')
async def redirect_to_static_html(request: web.Request) -> web.StreamResponse:
    return web.HTTPFound('/static/index.html')


@routes.get('/api/v1/studios')
async def list_studios(request: web.Request) -> web.StreamResponse:
    return web.json_response(list(Studio.names.keys()))


@routes.get('/api/v1/press/{studio_name}/{button}')
async def button_press(request: web.Request) -> web.StreamResponse:
    event = ButtonEvent(
        studio=Studio.names[request.match_info['studio_name']],
        button=Button(request.match_info['button'])
    )

    await event.studio.dispatcher_button_event_queue.put(event)

    return web.json_response({})


@routes.get('/api/v1/leds/{studio_name}')
async def led_status(request: web.Request) -> web.StreamResponse:
    studio = Studio.names[request.match_info['studio_name']]

    return web.json_response({
        'immediate':
            {
                'state': studio.immediate_led.state.name,
                'blink_freq': studio.immediate_led.blink_freq
            },
        'takeover':
            {
                'state': studio.takeover_led.state.name,
                'blink_freq': studio.takeover_led.blink_freq
            },
        'release':
            {
                'state': studio.release_led.state.name,
                'blink_freq': studio.release_led.blink_freq
            },
    })


app = web.Application()
app.add_routes(routes)


async def run():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '192.168.0.133', 8080)
    await site.start()
    await bermudafunk.base.cleanup_event.wait()
    await runner.cleanup()
