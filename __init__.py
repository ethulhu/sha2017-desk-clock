"""Displays the time and also alerts."""

# pylint: disable=bare-except
# pylint: disable=import-error
# pylint: disable=no-self-use
# pylint: disable=too-few-public-methods

import display
import easydraw
import machine
import neopixel
import umqtt.simple as umqtt
import utime
import wifi

EUROPE_LONDON = 'GMT+0BST-1,M3.5.0/01:00:00,M10.5.0/02:00:00'

WHITE = 0xFFFFFF
BLACK = 0x000000

FONTS = {
    '7x5': '7x5',
    'Dejavu Sans': {
        20: 'dejavusans20',
    },
    'Ocra': {
        16: 'ocra16',
        22: 'ocra22',
    },
    'Permanent Marker': {
        22: 'permanentmarker22',
        36: 'permanentmarker36',
    },
    'Roboto Regular': {
        12: 'roboto_regular12',
        18: 'roboto_regular18',
        22: 'roboto_regular22',
    },
    'Roboto Black': {
        22: 'roboto_black22',
    },
    'Roboto Black Italic': {
        24: 'roboto_blackitalic24',
    },
}

WEEKDAYS = {
    1: 'Sunday',
    2: 'Monday',
    3: 'Tuesday',
    4: 'Wednesday',
    5: 'Thursday',
    6: 'Friday',
    7: 'Saturday',
}

TOPIC_INFO = b'home/house/alert/info_string'

NUM_NEOPIXELS = 6


def main():
    """Main loop, should never exit."""

    easydraw.msg('setting up WiFi...')
    if not init_wifi():
        easydraw.msg('could not set up WiFi')
        return

    easydraw.msg('setting up RTC...')
    clock = Clock()

    easydraw.msg('setting up MQTT...')
    alerts = Alerts(topic_info=TOPIC_INFO)

    utime.sleep(1)

    output = Output()

    while True:
        output.draw(alerts.get(), clock.get())
        utime.sleep(1)


def init_wifi():
    """Set up the WiFi."""
    if wifi.status():
        return True
    wifi.connect()
    return wifi.wait()


class Clock:
    """Manages the Real Time Clock and NTP."""

    def __init__(self, default_timezone=EUROPE_LONDON):
        if utime.time() < 1585235437:
            # RTC is unset.
            wifi.ntp()

        self._rtc = machine.RTC()
        timezone = machine.nvs_getstr('system', 'timezone')
        if not timezone:
            timezone = default_timezone
        self._rtc.timezone(timezone)

    def get(self):
        """Returns a datetime tuple of (y, m, d, h, m, s, wd, yd)."""
        return self._rtc.now()


class Alerts:
    """Manages connecting to MQTT and returning alerts."""

    def __init__(self,
                 alert_timeout=10,
                 client_name='sha2017_badge',
                 server='catbus.eth.moe',
                 topic_info=None):

        self._alert = None
        self._alert_time = 0
        self._alert_timeout = alert_timeout

        self._topic_info = topic_info

        def on_message(topic, data):
            if topic == self._topic_info:
                self._alert = str(data.decode('utf-8')).strip()
                self._alert_time = utime.time()

        self._client = umqtt.MQTTClient(client_name, server)
        self._client.set_callback(on_message)
        self._connect()

    def _connect(self):
        try:
            if not init_wifi():
                return
            self._client.connect()
            self._client.subscribe(self._topic_info, qos=1)
        except:
            pass

    def get(self):
        """Return the most recent alert, or None if there is none."""
        now = utime.time()
        if now < (self._alert_time + self._alert_timeout):
            return self._alert

        self._alert = None
        try:
            self._client.check_msg()
            return self._alert
        except:
            # reconnect and try again next time.
            self._connect()
            return None


class Output:
    """Manages all formatting, display, and neopixel behavior."""

    def __init__(self):
        self._old_alert = ''
        self._old_date_str = ''
        self._old_time_str = ''

        neopixel.enable()
        self._neopixels = False

    def draw(self, alert, datetime):
        """Draw either the alert if one is given, or the date & time.

        Clear the screen to prevent ghosting:
            - When the date changes.
            - When entering an alert.
            - When leaving an alert.
        """
        if alert:
            if alert == self._old_alert:
                if self._neopixels:
                    self._neopixels_off()
                else:
                    self._neopixels_pink()
                return

            self._old_alert = alert
            self._old_time_str = ''

            # clear the screen to prevent ghosting.
            display.drawFill(BLACK)
            display.flush()

            display.drawFill(WHITE)

            width = display.width()
            y = 0
            words = alert.split(' ')
            chunk = words[0]
            for word in words[1:]:
                joined = chunk + ' ' + word
                if (display.getTextWidth(joined, FONTS['7x5']) * 3) >= width:
                    display.drawText(0, y, chunk, BLACK, FONTS['7x5'], 3, 3)
                    chunk = word

                    text_height = display.getTextHeight(
                        chunk, FONTS['7x5']) * 3
                    line_height = int(text_height * 1.4)
                    y += line_height
                else:
                    chunk = joined
            display.drawText(0, y, chunk, BLACK, FONTS['7x5'], 3, 3)
            display.flush()
        else:
            time_str = self._format_time(datetime)
            date_str = self._format_date(datetime)

            if time_str == self._old_time_str:
                return

            if self._old_alert or date_str != self._old_date_str:
                # we've come out of an alert or the date changed,
                # so clear the screen to prevent ghosting.
                display.drawFill(BLACK)
                display.flush()

            self._old_alert = ''
            self._old_date_str = date_str
            self._old_time_str = time_str
            self._neopixels_off()

            display.drawFill(WHITE)
            display.drawText(0, 0, time_str, BLACK, FONTS['7x5'], 5, 5)

            bottom = display.height() - 2  # the bottom pixel seems to clip.
            date_y = bottom - \
                (display.getTextHeight(date_str, FONTS['7x5']) * 3)
            display.drawText(0, date_y, date_str, BLACK, FONTS['7x5'], 3, 3)
            display.flush()

    def _neopixels_off(self):
        data = [0x00, 0x00, 0x00, 0x00] * NUM_NEOPIXELS
        neopixel.send(bytes(data))
        self._neopixels = False

    def _neopixels_white(self):
        data = [0x00, 0x00, 0x00, 0x10] * NUM_NEOPIXELS
        neopixel.send(bytes(data))
        self._neopixels = True

    def _neopixels_pink(self):
        data = [0x00, 0x10, 0x10, 0x00] * NUM_NEOPIXELS
        neopixel.send(bytes(data))
        self._neopixels = True

    def _format_time(self, datetime):
        hours = datetime[3]
        minutes = datetime[4]
        return '%02d:%02d' % (hours, minutes)

    def _format_date(self, datetime):
        weekday = datetime[6]
        return WEEKDAYS[weekday]


main()
