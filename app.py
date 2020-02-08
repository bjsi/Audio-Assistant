from Queue.MainQueue import MainQueue
from select import select
import pyudev
from evdev import InputDevice
import time
from config import CONTROLLER
from Bluetooth.Device import (BTHeadphones,
                              BTController)
import subprocess

# Loop until headphones and controller are both connected
# Wait until user presses the launch key
# Then launch the actual program

# queue: MainQueue, hp: BTHeadphones, con: BTController


def main_loop():
    """Set up the main loop for the controller.
    Reads key codes and values from the connected
    device and executes the associated commands in the
    AudioAssistant active_keys dict.
    """
    queue = MainQueue()
    queue.get_global_topics()
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='input')
    monitor.start()
    fds = {monitor.fileno(): monitor}
    while True:
        r, w, x = select(fds, [], [])
        if monitor.fileno() in r:
            r.remove(monitor.fileno())
            for udev in iter(monitor.poll, None):
                if udev.device_node and "event" in udev.device_node:
                    if udev.action == u'add':
                        print(f"Device added: {udev}")
                        dev = InputDevice(udev.device_node)
                        fds[dev.fd] = dev
                        break
                    if udev.action == u'remove':
                        if udev.get('DEVPATH') and "virtual" in udev.get("DEVPATH"):
                            print("Restarting pulseaudio...")
                            subprocess.Call(['pulseaudio', '-k'])
                            subprocess.Call(['pulseaudio', '--start'])
                        print(f'Device removed: {udev}')
                        fds = {monitor.fileno(): monitor}
                        break
        try:
            for fd in r:
                dev = fds.get(fd, None)
                if dev:
                    for event in dev.read():
                        if event.value == 1 and event.code in queue.active_keys:
                            queue.active_keys[event.code]()
        # Hacky? But works excellently
        except OSError:
            continue

    # while True:
    #     try:
    #         r, w, x = select(con.devices, [], [])
    #         for fd in r:
    #             for event in con.devices[fd].read():
    #                 if event.value == 1:
    #                     if event.code in queue.active_keys:
    #                         queue.active_keys[event.code]()
    #     except (PermissionError, OSError):
    #         while not hp.is_connected():
    #             print("Connecting to headphones")
    #             hp.connect()
    #         while not con.is_connected():
    #             print("Connecting to controller")
    #             con.connect()
    #             con.load_devices()
    #         continue


def launch_loop2():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='input')
    monitor.start()
    fds = {monitor.fileno(): monitor}
    while True:
        r, w, x = select(fds, [], [])
        if monitor.fileno() in r:
            r.remove(monitor.fileno())
            for udev in iter(monitor.poll, None):
                if udev.device_node and "event" in udev.device_node:
                    if udev.action == u'add':
                        print(f"Device added: {udev}")
                        dev = InputDevice(udev.device_node)
                        fds[dev.fd] = dev
                        break
                    if udev.action == u'remove':
                        if udev.get('DEVPATH') and "virtual" in udev.get("DEVPATH"):
                            print("Restarting pulseaudio...")
                            subprocess.Call(['pulseaudio', '-k'])
                            subprocess.Call(['pulseaudio', '--start'])
                        print(f'Device removed: {udev}')
                        fds = {monitor.fileno(): monitor}
                        break
        try:
            for fd in r:
                dev = fds.get(fd, None)
                if dev:
                    for event in dev.read():
                        if event.value == 1 and event.code == CONTROLLER['keys']['KEY_A']:
                            ## Check if 
                            main_loop()
        # Hacky? But works excellently
        except OSError:
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

    queue = MainQueue()
    queue.get_global_topics()
    main_loop(queue, hp, con)


if __name__ == "__main__":
   # # C = Controller()
   # hp = BTHeadphones()
   # con = BTController()
   # while (not hp.is_connected()) and (not con.is_connected()):
   #     time.sleep(3)

   # print(hp)
   # print(con)
   # con.load_devices()
   # launch_loop(hp, con)
   main_loop()
