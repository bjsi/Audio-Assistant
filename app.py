from Queue.Controller import Controller
from select import select
import time
from config import CONTROLLER
from Bluetooth.Device import (BTHeadphones,
                              BTController)

# Loop until headphones and controller are both connected
# Wait until user presses the launch key
# Then launch the actual program


def main_loop(C: Controller):
    """Set up the main loop for the controller.
    Reads key codes and values from the connected
    device and executes the associated commands in the
    AudioAssistant active_keys dict.
    """
    while True:
        try:
            r, w, x = select(con.devices, [], [])
            for fd in r:
                for event in con.devices[fd].read():
                    if event.value == 1:
                        if event.code in C.active_keys:
                            C.active_keys[event.code]()
        except (PermissionError, OSError):
            # attempt to reconnect?
            pass


def launch_loop():
    """ Loop until the launch key is pressed
    When launch key pressed, run the main loop """

    LAUNCH_KEY = CONTROLLER.keys.KEY_A

    while True:
        try:
            r, w, x = select(con.devices, [], [])
            for fd in r:
                for event in con.devices[fd].read():
                    if event.value == 1:
                        if event.code == LAUNCH_KEY:
                            break
        except (PermissionError, OSError):
            # attempt to reconnect?
            pass

    C = Controller()
    main_loop(C)


if __name__ == "__main__":
    # C = Controller()
    hp = BTHeadphones()
    con = BTController()
    while (not hp.is_connected()) and (not con.is_connected()):
        time.sleep(3)
    launch_loop()
