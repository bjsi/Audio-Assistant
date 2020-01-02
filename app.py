from Queue.Controller import Controller
from select import select
import time
from config import CONTROLLER
from Bluetooth.Device import (BTHeadphones,
                              BTController)

# Loop until headphones and controller are both connected
# Wait until user presses the launch key
# Then launch the actual program


def main_loop(C: Controller, hp: BTHeadphones, con: BTController):
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
            while not hp.is_connected():
                print("Connecting to headphones")
                hp.connect()
            while not con.is_connected():
                print("Connecting to controller")
                con.connect()
                con.load_devices()
            continue


def launch_loop(hp: BTHeadphones, con: BTController):
    """ Loop until the launch key is pressed
    When launch key pressed, run the main loop """

    LAUNCH_KEY = CONTROLLER['keys']['KEY_A']
    launched = False

    while not launched:
        try:
            r, w, x = select(con.devices, [], [])
            for fd in r:
                for event in con.devices[fd].read():
                    if event.value == 1:
                        if event.code == LAUNCH_KEY:
                            launched = True
        except (PermissionError, OSError):
            while not hp.is_connected():
                print("Connecting to headphones")
                hp.connect()
            while not con.is_connected():
                print("Connecting to controller")
                con.connect()
                con.load_devices()
            continue

    C = Controller()
    C.get_global_topics()
    main_loop(C, hp, con)


if __name__ == "__main__":
    # C = Controller()
    hp = BTHeadphones()
    con = BTController()
    while (not hp.is_connected()) and (not con.is_connected()):
        time.sleep(3)

    print(hp)
    print(con)
    con.load_devices()
    launch_loop(hp, con)
