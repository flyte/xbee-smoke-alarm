import argparse
from datetime import datetime, timedelta
from time import sleep
from threading import Thread, Event
from binascii import hexlify

from serial import Serial

from xbee import ZigBee
from pushbullet import Pushbullet


COOLDOWN_TIME = timedelta(seconds=60)
ALARM_NOTIFICATION_REPEAT_SECONDS = 30
ALARM_VALUE = False

last_alarm_value = None
alarm_thread = None
disable_pushbullet = False


def send_pb(topic, msg):
    if not disable_pushbullet:
        pb.push_note(topic, msg)


class AlarmThread(Thread):
    start_time = None

    def __init__(self, stop_event, *args, **kwargs):
        super(AlarmThread, self).__init__(*args, **kwargs)
        self.stop_event = stop_event

    def run(self):
        print "Sending the first alarm notification over Pushbullet..."
        self.start_time = datetime.now()
        send_pb("Alarm!", "Smoke detector is going off!")
        # Repeat every fifteen seconds while alarm is sounding
        while not self.stop_event.wait(ALARM_NOTIFICATION_REPEAT_SECONDS):
            print "Sending another alarm notification over Pushbullet..."
            send_pb("Alarm!", "Smoke detector is still going off!")
        print "Sending an all-clear notification over Pushbullet..."
        send_pb("All Clear", "The Smoke detector has stopped sounding.")


def msg_rx(data):
    """
    Receive a message from the ZigBee device, check if it's got the sample data
    we want and start the alarm thread if it matches ALARM_VALUE.
    """
    global last_alarm_value
    global alarm_thread

    print "Got sample from %s (%s)" % (
        hexlify(data["source_addr_long"]), hexlify(data["source_addr"]))
    print data

    try:
        samples = data["samples"][0]
    except (IndexError, KeyError):
        print "No samples in data."

    try:
        value = samples["dio-0"]
    except KeyError:
        print "Sample did not include pin dio-0."
        return

    if value == ALARM_VALUE:
        last_alarm_value = datetime.now()
        if alarm_thread is None:
            print "Starting alarm..."
            alarm_thread = AlarmThread(Event())
            alarm_thread.start()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("serial_port")
    p.add_argument("pb_api_key")
    p.add_argument("--baud", default=9600)
    p.add_argument("--disable-pushbullet", action="store_true")
    args = p.parse_args()

    disable_pushbullet = args.disable_pushbullet
    s = Serial(args.serial_port, args.baud)
    zb = ZigBee(s, callback=msg_rx)
    pb = Pushbullet(args.pb_api_key)

    print "Waiting for input..."
    try:
        while True:
            if last_alarm_value is not None and alarm_thread is not None:
                if last_alarm_value + COOLDOWN_TIME < datetime.now():
                    print "Stopping alarm..."
                    alarm_thread.stop_event.set()
                    alarm_thread.join(5)
                    alarm_thread = None
            sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        zb.halt()
        s.close()
        if alarm_thread is not None:
            print "Waiting for alarm thread to stop..."
            alarm_thread.stop_event.set()
            alarm_thread.join()
