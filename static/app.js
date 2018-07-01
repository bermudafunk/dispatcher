const dispatcher_status_elements = {
    on_air_studio: $('#status_on_air_studio'),
    state: $('#status_state'),
    x: $('#status_x'),
    y: $('#status_y'),
};

const leds = {
    green: document.getElementById('green_led'),
    yellow: document.getElementById('yellow_led'),
    red: document.getElementById('red_led')
};

const status_ws_url = 'ws://' + location.host + '/api/v1/ws';

const connection = new WebSocket(status_ws_url);

let selected_studio = '';

const update_selected_studio = function (new_value) {
    if (new_value === '') {
        selected_studio = null;
    } else {
        selected_studio = new_value;
        connection.send(JSON.stringify({type: 'studio.led.status', studio: selected_studio}));
    }
    console.log(selected_studio);
};

const update_led_status = function (led_status) {
    console.log(led_status);
    for (let key in leds) {
        console.log(key);
        leds[key].dataset.state = led_status[key].state.toLowerCase();
        leds[key].style.animationDuration = (1 / led_status[key].blink_freq) + 's';
    }
};

$('.studio-button').click(function (event) {
    if (selected_studio) {
        let url = location.protocol + '//' + location.host + '/api/v1/' + selected_studio + '/press/' + event.target.dataset.kind;
        $.get(url);
    }
});

$('#studio_selector').change(function (event) {
    update_selected_studio(event.target.value);
});

// When the connection is open, send some data to the server
connection.onopen = function () {
    update_selected_studio($('#studio_selector').val());
};

// Log errors
connection.onerror = function (error) {
    console.log('WebSocket Error ' + error);
};

connection.onclose = function (arg) {
    console.log('WebSocket Close ' + arg);
};

// Log messages from the server
connection.onmessage = function (e) {
    const data = JSON.parse(e.data);

    switch (data.kind) {
        case 'dispatcher.status':
            dispatcher_status_elements.on_air_studio.text(data.payload.on_air_studio);
            dispatcher_status_elements.state.text(data.payload.state);
            dispatcher_status_elements.x.text(data.payload.x);
            dispatcher_status_elements.y.text(data.payload.y);
            break;
        case 'studio.led.status':
            const payload = data.payload;
            if (payload.studio === selected_studio) {
                update_led_status(payload.status);
            }
            break;
        default:
            console.log(data);
    }
};
