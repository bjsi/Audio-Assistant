from AudioAssistant import AudioAssistant
from config import CONTROLLER, HEADPHONES
from select import select


def main_loop():
    """Set up the main loop for the controller.
    Reads key codes and values from the connected
    device and executes the associated commands in the
    AudioAssistant active_keys dict.
    """
    while True:
        try:
            r, w, x = select(aa.devices, [], [])
            for fd in r:
                for event in aa.devices[fd].read():
                    if event.value == 1:
                        if event.code in aa.active_keys:
                            aa.active_keys[event.code]()


if __name__ == "__main__":
    aa = AudioAssistant()
    h = BTDevice(CONTROLLER['address'],
                 CONTROLLER['name'],
                 CONTROLLER['input_devices'],
                 CONTROLLER['keys'])
    c = BTDevice(HEADPHONES['address'],
                 HEADPHONES['name'])
    if c.bt_connect() and h.bt_connect():
        aa.load_global_topics()
        aa.seek_to_cur_timestamp()
        try:
            main_loop()
        except PermissionError:
            # How to make this more stable
            # What if I am recording / clozing when the
            # BT device disconnects?
            c.bt_connect(HEADPHONES)
            h.bt_connect(CONTROLLER)
        finally:
            main_loop()
