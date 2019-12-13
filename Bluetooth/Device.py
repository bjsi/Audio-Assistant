from config import CONTROLLER, HEADPHONES
import subprocess
import time
from evdev import InputDevice


# Not sure that this is necessary
class BTDevice(object):
    """Bluetooth device base class"""

    def __init__(self, address, name, input_devices="", keys=""):
        """TODO: to be defined. """

        self.keys = keys
        self.address = address
        self.name = name
        if input_devices:
            self.input_devices = map(InputDevice, input_devices)
            self.devices = {device.fd: device
                            for device in self.input_devices}
        self.connected = False

    def bt_connect(self, attempts=5) -> bool:
        """Connect to a bluetooth device

        :attempts: TODO
        :returns: TODO

        """
        count = 0
        while count < attempts:
            count += 1
            bt_data = subprocess.getoutput("hcitool con")
            if self.address in bt_data.split():
                return True
            print("{} not connected.".format(self.name))
            print("Connecting now. Attempt #{}".format(count))
            connected = subprocess.call(['bluetoothctl',
                                         'connect',
                                         self.address])
            if connected == 0:
                print("{} connected!".format(self.name))
                return True
            print("Connection attempt {} failed.".format(count))
            time.sleep(3)
        return False
