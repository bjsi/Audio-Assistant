from time import sleep
from bluezero import central
from evdev import InputDevice
from select import select


class Controller(object):
    def __init__(self):
        self.remote_device = central.Central(adapter_addr="B8:27:EB:F4:E7:F6",
                                             device_addr="E0:F8:48:05:27:EF")
        
    def connect(self):
        self. remote_device.connect()
        while not self.remote_device.services_resolved:
            sleep(0.5)
        self.remote_device.load_gatt()


devices = ('/dev/input/event0',
           '/dev/input/event1',
           '/dev/input/event2',
           '/dev/input/event3')

input_devices = map(InputDevice, devices)
devices = {device.fd: device
           for device in input_devices}


if __name__ == "__main__":
    while True:
        r, w, x = select(devices, [], [])
        for fd in r:
            for event in devices[fd].read():
                print(event)
