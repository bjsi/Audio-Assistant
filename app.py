from Queue.MainQueue import MainQueue
from select import select
import pyudev
from evdev import InputDevice
import time
from config import CONTROLLER
from Bluetooth.Device import (BTHeadphones,
                              BTController)
import subprocess
from Sounds.sounds import espeak, negative_beep
from Queue.QueueBase import QueueBase


# TODO: Logging
# Log keypress / keycodes
# Log command failure

# TODO: Add better comments.

def main_loop(queue: QueueBase):
    """Main entry point for Audio Assistant.
    
    Reads key codes from the controller and executes mapped command.

    Allows reconnection of both controller and headphones*.

    * Requires that they are trusted in bluetoothctl.
    """
    # TODO: What if this returns False?
    queue.load_initial_queue()
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    # headphones and controller both in the input subsystem
    monitor.filter_by(subsystem='input')
    monitor.start()
    # TODO What is monitor
    fds = {monitor.fileno(): monitor}
    while True:
        r, w, x = select(fds, [], [])
        if monitor.fileno() in r:
            r.remove(monitor.fileno())
            for udev in iter(monitor.poll, None):
                if udev.device_node and "event" in udev.device_node:
                    if udev.action == u'add':
                        dev = InputDevice(udev.device_node)
                        # saving both dev and udev.device_node
                        # dev for reading events
                        # udev.device node for removing the fd from the fds dict when 
                        # a removal event occurs
                        fds[dev.fd] = {"dev": dev, "device_node": udev.device_node}
                        print(f"Device added: {udev}")
                        # TODO When devices are added espeak a message
                        # when controller added 4 events occur
                        break
                    if udev.action == u'remove':
                        # TODO: Find a better way to identify devices.
                        if udev.get('DEVPATH') and "virtual" in udev.get("DEVPATH"):
                            print("Headphones disconnected")
                            # Restart pulseaudio so headphones work
                            print("Restarting pulseaudio...")
                            subprocess.call(['pulseaudio', '-k'])
                            subprocess.call(['pulseaudio', '--start'])
                        else:
                            print("Controller Removed")
                        print(f'Device removed: {udev}')
                        # Remove the fd from the fds dict
                        # Uses a copy of the dict to avoid
                        # dict size changed while iterating error
                        d = {k: v for k, v in fds.items()}
                        for fd in d:
                            if d[fd] is not monitor:
                                if d[fd]["device_node"] == udev.device_node:
                                    del fds[fd]
                        continue
        try:
            for fd in r:
                # get device events
                dev = fds.get(fd, None)
                if dev:
                    for event in dev["dev"].read():
                        if event.value == 1 and event.code in queue.active_keys:
                            # Failed commands return False
                            # TODO: Log the keypress / key name
                            if queue.active_keys[event.code]() is False:
                                negative_beep()
            
        # Hacky? But works excellently
        except OSError:
            continue


if __name__ == "__main__":
    # Change queue to an individual queue to test in isolation.
    queue = MainQueue()
    main_loop(queue)
