from Queue.MainQueue import MainQueue
from select import select
import pyudev
from evdev import InputDevice
import time
import subprocess
from Sounds.sounds import espeak, negative_beep
from Queue.QueueBase import QueueBase
import logging
from typing import Dict
from config import CONTROLLER, HEADPHONES


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s:%(name)s:%(funcName)s():"
                              "%(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("main_loop.log")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Log keypress / keycodes
# Log command failure


class QueueLoop(object):

    """Methods and state for managing the main loop.
    """

    def __init__(self, queue: QueueBase):
        """
        :controller_add_event_count: 4 per connection / disconnection.

        :queue: The queue object.

        :controller: Controller info dict.

        :headphones: Headphones info dict.

        :fds: Dict of file descriptors of monitored devices.
        """
        self.controller_add_event_count: int = 0
        self.controller_remove_event_count: int = 0
        self.queue: QueueBase = queue
        self.controller = CONTROLLER
        self.headphones = HEADPHONES
        self.monitor: pyudev.Monitor
        # File Descriptors
        # TODO: typing
        # Maps file descriptor
        self.fds: Dict = {}

    def wait_connect_headphones(self) -> None:
        """Loop until headphones are connected.
        """
        while not self.headphones_connected():
            logger.info("Headphones not connected. "
                        "Waiting to load initial queue.")
            time.sleep(6)

    def headphones_connected(self) -> bool:
        """
        :returns: True if headphones connected else false.
        """
        stdoutdata = subprocess.getoutput("hcitool con")

        if self.headphones["address"] in stdoutdata.split():
            return True
        return False

    def controller_connected(self) -> bool:
        """
        :returns: True if controller is connected else false.
        """
        stdoutdata = subprocess.getoutput("hcitool con")

        if self.controller["address"] in stdoutdata.split():
            return True
        return False

    def handle_controller_add_event(self, udev: pyudev.Device):
        """Add a controller file descriptor to the fds dict.
        """
        self.controller_add_event_count += 1
        if self.controller_add_event_count == 4:
            logger.info("Controller has been connected.")
            espeak("Controller connected")
            self.controller_add_event_count = 0
        dev = InputDevice(udev.device_node)
        self.fds[dev.fd] = {
            "dev": dev,
            "device_node": udev.device_node
        }

    def handle_controller_removed_event(self, udev: pyudev.Device):
        """Removes a controller file descriptor from the fds dict.
        """
        # Create a deep copy of the fds dict.
        # NOTE: Prevents dict size changed while iterating error.
        dic = {k: v for k, v in self.fds.items()}
        for fd in dic:
            if dic[fd] is not self.monitor:
                if dic[fd]["device_node"] == udev.device_node:
                    del self.fds[fd]
                    self.controller_remove_event_count += 1
                    if self.controller_remove_event_count == 4:
                        logger.info("Controller disconnected.")
                        self.controller_remove_event_count = 0

    def handle_headphones_add_event(self, udev: pyudev.Device):
        """Add the device information to the fds dict.
        """
        dev = InputDevice(udev.deviceNode)
        self.fds[dev.fd] = {
            "dev": dev,
            "device_node": udev.device_node
        }
        logger.info("Headphones connected.")

    def handle_headphones_removed_event(self, udev: pyudev.Device):
        """Removes a headphones file descriptor from the fds dict.
        """
        # Create a deep copy of the fds dict
        # NOTE: Prevents dict size changed while iterating error.
        dic = {k: v for k, v in self.fds.items()}
        for fd in dic:
            if dic[fd] is not self.monitor:
                if dic[fd]["device_node"] == udev.device_node:
                    del self.fds[fd]
                    logger.info("Headphones disconnected.")

                    # Restart pulseaudio so headphones work.
                    # Kill the current pulseaudio process.
                    try:
                        kill_ret = subprocess.call(['pulseaudio', '-k'])
                        if kill_ret != 0:
                            logger.error("Subprocess call to kill the current "
                                         "pulseaudio instance failed.")
                        elif kill_ret == 0:
                            logger.info("Successfully killed the current "
                                        "pulseaudio instance.")
                    except OSError:
                        logger.info("Subprocess call failed to kill "
                                    "pulseaudio.")

                    # Start a new pulseaudio process.
                    try:
                        start_ret = subprocess.call(['pulseaudio', '--start'])
                        if start_ret != 0:
                            logger.error("Subprocess call to start pulseaudio "
                                         "failed.")
                        elif start_ret == 0:
                            logger.info("Successfully started a pulseaudio "
                                        "instance.")
                    except OSError:
                        logger.info("Subprocess call failed to start "
                                    "pulseaudio.")

    def handle_add_event(self, udev: pyudev.Device) -> None:
        """Handle controller and headphones udev add events.
        """
        if udev.get('DEVPATH') and 'event' in udev.get('DEVPATH'):
            if udev.parent:
                dev_name: str = udev.parent.get("NAME")

                # Controller add event
                if self.controller["name"] in dev_name or \
                   self.controller["address"] in dev_name:
                    self.handle_controller_add_event(udev)

                # Headphones add event
                elif self.headphones["name"] in dev_name or \
                        self.headphones["address"] in dev_name:
                    self.handle_headphones_add_event(udev)

    def handle_remove_event(self, udev: pyudev.Device) -> None:
        """Sends controller / headphone remove events to their
        respective event handlers.
        """
        if udev.get('DEVPATH') and 'event' in udev.get('DEVPATH'):
            if udev.parent:
                dev_name: str = udev.parent.get('NAME')
                
                # Controller remove event
                if dev_name:
                    if dev_name.contains(self.controller["name"]) or \
                       dev_name.contains(self.controller["address"]):
                        self.handle_controller_removed_event(udev)

                    # Headphones remove event
                    elif dev_name.contains(self.headphones["name"]) or \
                            dev_name.contains(self.headphones["address"]):
                        self.handle_headphones_removed_event(udev)

    def main_loop(self):
        """Main entry point for Audio Assistant.
        
        Reads key codes from the controller and executes mapped command.

        Allows reconnection of both controller and headphones*.

        * Requires that they are trusted in bluetoothctl.
        """

        self.wait_connect_headphones()

        # TODO: load_secondary_queue?
        if not self.queue.load_initial_queue():
            logger.info("Failed to load initial queue.")
            while True:
                if self.headphones_connected():
                    espeak("No files")
                logger.info("Failed to load initial queue.")
                time.sleep(8)

        context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(context)
        # BT headphones and controller are both in the input subsystem
        self.monitor.filter_by(subsystem='input')
        self.monitor.start()

        self.fds = {self.monitor.fileno(): self.monitor}

        while True:
            # TODO: What is select.
            r, w, x = select(self.fds, [], [])
            if self.monitor.fileno() in r:
                r.remove(self.monitor.fileno())
                # TODO: is this python2?
                for udev in iter(self.monitor.poll, None):
                    if udev.device_node and "event" in udev.device_node:
                        if udev.action == u'add':
                            self.handle_add_event(udev)
                            break
                        elif udev.action == u'remove':
                            self.handle_remove_event(udev)
                            continue
            try:
                for fd in r:
                    # get device events
                    dev = self.fds.get(fd, None)
                    if dev:
                        for event in dev["dev"].read():
                            if event.value == 1:
                                if event.code in self.queue.active_keys:
                                    # Failed commands return False
                                    if queue.active_keys[event.code]() is False:
                                        negative_beep()
                                    # Log the name of the pressed key.
                                    for keyname, keycode in self.controller['keys'].items():
                                        if keycode == event.code:
                                            logger.info(f"{keyname} pressed.")
                
            # TODO: Test without this except block.
            # Hacky? But works excellently
            except OSError:
                continue


if __name__ == "__main__":
    # Change queue to an individual queue
    # eg. (TopicQueue) to test in isolation.
    queue = MainQueue()
    queue_loop = QueueLoop(queue)
    queue_loop.main_loop()
