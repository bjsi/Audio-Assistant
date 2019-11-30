from AudioAssistant import AudioAssistant
from BluetoothDevices import BTDevice
from config import CONTROLLER, HEADPHONES
from select import select


def main_loop():
    """Set up the main loop for the controller.
    Reads key codes and values from the connected
    device and executes the associated commands in the
    AudioAssistant active_keys dict.
    """
    while True:
        r, w, x = select(c.devices, [], [])
        for fd in r:
            for event in c.devices[fd].read():
                if event.value == 1:
                    if event.code in aa.active_keys:
                        aa.active_keys[event.code]()


if __name__ == "__main__":
    aa = AudioAssistant()
    h = BTDevice(CONTROLLER['address'],
                 CONTROLLER['name'])
    c = BTDevice(HEADPHONES['address'],
                 HEADPHONES['name'],
                 CONTROLLER['input_devices'],
                 CONTROLLER['keys'])

    if c.bt_connect() and h.bt_connect():
        aa.load_global_topics()
        aa.seek_to_cur_timestamp()
        try:
            main_loop()
        except PermissionError:
            c.bt_connect()
            h.bt_connect()
        finally:
            main_loop()
