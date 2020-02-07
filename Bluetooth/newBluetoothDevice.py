from time import sleep
from bluezero import central
from evdev import InputDevice
from select import select
import pyudev
from pyudev.glib import MonitorObserver


class Controller(object):
    def __init__(self):
        self.remote_device = central.Central(adapter_addr="B8:27:EB:F4:E7:F6",
                                             device_addr="E0:F8:48:05:27:EF")
        
    def connect(self):
        self.remote_device.connect()
        while not self.remote_device.services_resolved:
            sleep(0.5)
        self.remote_device.load_gatt()



def print_events(observer, device):
    print(device.action, device)




if __name__ == "__main__":
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='input')
    monitor.start()

    fds = {monitor.fileno(): monitor}
    finalizers = []
    while True:
        r, w, x = select(fds, [], [])
        if monitor.fileno() in r:
            r.remove(monitor.fileno())
            for udev in iter(monitor.poll, None):
                if udev.device_node in ["/dev/input/event0",
                                        "/dev/input/event1",
                                        "/dev/input/event2",
                                        "/dev/input/event3"]:
                    if udev.action == u'add':
                        print(f"Device added: {udev}")
                        dev = InputDevice(udev.device_node)
                        fds[dev.fd] = dev
                        break
                    if udev.action == u'remove':
                        print(f'Device removed: {udev}')
                        fds = {monitor.fileno(): monitor}
                        continue

        for fd in r:
            dev = fds[fd]
            event = dev.read_one()
            if event:
                print(event) 
            else:
                pass

        for i in range(len(finalizers)):
            finalizers.pop()()

    #controller = Controller()
    #controller.connect()
    #if controller.remote_device.connected:
    #    event1 = InputDevice('/dev/input/event1')
    #    event2 = InputDevice('/dev/input/event2')
    #    event3 = InputDevice('/dev/input/event3')
    #    for device in event1, event2, event3:
    #        asyncio.ensure_future(print_events(device))
    #    loop = asyncio.get_event_loop()
    #    loop.run_forever()
    #else:
    #    print("error")

    #devices = {device.fd: device
    #           for device in input_devices}
    #while True:
    #    r, w, x = select(devices, [], [])
    #    for fd in r:
    #        for event in devices[fd].read():
    #            print(event)
