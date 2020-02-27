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
from models import TopicFile, ExtractFile, ItemFile


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

        :controller_remove_event_count: 4 per connection / disconnection.

        :queue: The queue object eg. TopicQueue, MainQueue.

        :controller: Controller info dict.

        :headphones: Headphones info dict.

        :monitor: TODO ... Monitor is filtered down to the input subsystem
        because BT headphone and controller event devices are found there.

        :fds: Dict of file descriptors of monitored devices.
        """
        self.controller_add_event_count: int = 0
        self.controller_remove_event_count: int = 0
        self.queue: QueueBase = queue
        self.controller = CONTROLLER
        self.headphones = HEADPHONES
        self.monitor = pyudev.Monitor.from_netlink(pyudev.Context())
        # BT headphones and controller are both in the input subsystem
        self.monitor.filter_by(subsystem='input')
        self.monitor.start()
        # File Descriptors
        # TODO: typing
        # Maps file descriptor
        self.fds = {self.monitor.fileno(): self.monitor}

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

        file descriptor: int = {"dev": pyudev.Device,
                                "device_node": str path,
                                "name": str name of the device's parent}
        """
        name = udev.parent.get('NAME')
        self.controller_add_event_count += 1
        if self.controller_add_event_count == 4:
            logger.info("Controller has been connected.")
            if self.controller_connected():
                espeak("Controller connected")
            self.controller_add_event_count = 0
        dev = InputDevice(udev.device_node)
        self.fds[dev.fd] = {
            "dev": dev,
            "device_node": udev.device_node,
            "name": name
        }

    def handle_controller_removed_event(self, udev: pyudev.Device):
        """Removes a controller file descriptor from the fds dict.
        """
        # Create a deep copy of the fds dict.
        # NOTE: Prevents dict size changed while iterating error.
        # TODO: Can you just add break to remove this
        dic = {k: v for k, v in self.fds.items()}
        for fd in dic:
            if dic[fd] is not self.monitor:
                if dic[fd]["device_node"] == udev.device_node:
                    del self.fds[fd]
                    self.controller_remove_event_count += 1
                    if self.controller_remove_event_count == 4:
                        logger.info("Controller disconnected.")
                        self.controller_remove_event_count = 0
                        if self.headphones_connected():
                            espeak("Controller disconnected")

    def handle_headphones_add_event(self, udev: pyudev.Device):
        """Add the device information to the fds dict.

        file descriptor: int = {"dev": pyudev.Device,
                                "device_node": str path,
                                "name": str name of the device's parent}
        """
        name = udev.parent.get('NAME')
        dev = InputDevice(udev.device_node)
        self.fds[dev.fd] = {
            "dev": dev,
            "device_node": udev.device_node,
            "name": name
        }
        logger.info("Headphones connected.")
        if self.headphones_connected():
            espeak("Headphones connected")

    def handle_headphones_removed_event(self, udev: pyudev.Device):
        """Removes a headphones file descriptor from the fds dict.
        """
        # Create a deep copy of the fds dict
        # NOTE: Prevents dict size changed while iterating error.
        # TODO: Can you just add break to remove this
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

        Event devices can be identified by their parent's NAME property.
        """
        if udev.get('DEVPATH') and 'event' in udev.get('DEVPATH'):
            if udev.parent:
                dev_name: str = udev.parent.get("NAME")
                if dev_name:
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

            # Find the relevant object in the fds dict
            for fd in self.fds:
                if self.fds[fd] != self.monitor:
                    if self.fds[fd]['device_node'] == udev.device_node:
                        dev_name = self.fds[fd]['name']
                        # Controller remove event
                        if dev_name:
                            if self.controller["name"] in dev_name or \
                                 self.controller["address"] in dev_name:
                                self.handle_controller_removed_event(udev)
                                break

                            # Headphones remove event
                            elif self.headphones["name"] in dev_name or \
                                    self.headphones["address"] in dev_name:
                                self.handle_headphones_removed_event(udev)
                                break

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
                
            # Hacky, try to find a fix.
            except OSError:
                continue


if __name__ == "__main__":
    # Change queue to an individual queue
    # eg. (TopicQueue) to test in isolation.

    # Remove finished files before load_initial_queue call.
    # TODO
    #ItemFile.remove_finished_files()
    #ExtractFile.remove_finished_files()
    #TopicFile.remove_finished_files()
    
    queue = MainQueue()
    queue_loop = QueueLoop(queue)
    queue_loop.main_loop()
