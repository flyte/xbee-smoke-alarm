import argparse
from serial import Serial
from datetime import datetime, timedelta
from time import sleep

from xbee import ZigBee
from pushbullet import Pushbullet


DEBOUNCE_TIME = timedelta(seconds=2)

value = None
last_sent_value = None
last_transition = datetime.min


def msg_rx(data):
    """
    Receive a message from the ZigBee device, check if it's got the sample data
    we want and store it in last_value. Set last_value_time to datetime.now().
    """
    global value
    global last_transition

    print "Got data from %s (%s)" % (data["source_addr_long"], data["source_addr"])
    print data

    try:
        samples = data["samples"][0]
    except (IndexError, KeyError):
        print "No samples in data."

    try:
        new_value = samples["dio-0"]
    except KeyError:
        print "Sample did not include pin dio-0."
        return

    if new_value != value:
        last_transition = datetime.now()
        value = new_value


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("serial_port")
    p.add_argument("pb_api_key")
    args = p.parse_args()

    s = Serial(args.serial_port)
    zb = ZigBee(s, callback=msg_rx)
    pb = Pushbullet(args.pb_api_key)

    print "Waiting for input.."
    try:
        while True:
            if last_transition < (datetime.now() - DEBOUNCE_TIME) and value != last_sent_value:
                if not value:
                    msg = ("Alarm!", "Smoke detector has been triggered!")
                else:
                    msg = ("Safe", "Smoke detector has reset.")
                print "Sending Pushbullet note: %s: %s" % msg
                pb.push_note(*msg)
                last_sent_value = value
            sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        zb.halt()
        s.close()
