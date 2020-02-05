import subprocess
import time
from evdev import InputDevice
from config import (CONTROLLER,
                    HEADPHONES)


class BTDevice(object):

    """ Generic bluetooth device class
    Gets inherited by Headphone and Controller subclasses
    """

    def __init__(self, address: str, name: str):

        """
        :mac_address: String. MAC address of the Bluetooth Device
        :name: String. Human-readable name of the device

        :connected: Bool. True if device is connected
        """

        self.address = address
        self.name = name
        self.connected = False

    def is_connected(self) -> bool:
        """ Check if the bluetooth device is connected or not
        """
        connected_devs = subprocess.check_output(["hcitool", "con"],
                                                 encoding="UTF-8")
        if self.address in connected_devs.split():
            self.connected = True
            return True
        return False

    def connect(self, attempts=5) -> bool:
        """ Connect to a bluetooth device
        :attempts: Int. How many connection attempts to make
        :returns: Bool. True if connected
        """
        count = 0
        while count < attempts:
            count += 1
            bt_data = subprocess.check_output(["hcitool", "con"],
                                              encoding="UTF-8")
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


class BTHeadphones(BTDevice):

    """ Class for bluetooth headphones """

    def __init__(self):
        super().__init__(HEADPHONES['address'],
                         HEADPHONES['name'])

    def __repr__(self):
        return f"<BTHeadphones: name={self.name}, address={self.address}>"


class BTController(BTDevice):

    """ Calss for bluetooth controller """

    def __init__(self):
        """
        :keys: Dict[key name: key code]
        :input_devices: TODO
        :devices: TODO
        """
        super().__init__(CONTROLLER['address'],
                         CONTROLLER['name'])
        self.keys = CONTROLLER['keys']
        self.input_devices = map(InputDevice,
                                 CONTROLLER['input_devices'])
    
    def load_devices(self):
        if self.is_connected():
            self.devices = {device.fd: device
                            for device in self.input_devices}

    def __repr__(self):
        return f"<BTController: name={self.name}, address={self.address}>"
