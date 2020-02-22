from Queue.MainQueue import MainQueue
from select import select
import pyudev
from evdev import InputDevice
import time
from config import CONTROLLER
from Bluetooth.Device import (BTHeadphones,
                              BTController)
import subprocess
from Sounds.sounds import espeak


def main_loop():
    """Set up the main loop for the controller.
    Reads key codes and values from the connected
    device and executes the associated commands in the
    AudioAssistant active_keys dict.
    """
    # if headphones connected TODO
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
                        # avoid dict size changed error
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
                            # run the mapped command in AA
                            queue.active_keys[event.code]()
            
        # Hacky? But works excellently
        except OSError:
            continue


if __name__ == "__main__":
    queue = MainQueue()
    queue.get_global_topics()
    main_loop()
