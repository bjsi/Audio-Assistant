from time import sleep
from mpd import MPDClient
from bluezero import central
from evdev import InputDevice
from select import select
import pyudev
import asyncio
from pyudev import MonitorObserver, Context, Monitor
import mpd
import subprocess

class Controller(object):
    def __init__(self):
        self.remote_device = central.Central(adapter_addr="B8:27:EB:F4:E7:F6",
                                             device_addr="E0:F8:48:05:27:EF")
        
    def connect(self):
        self.remote_device.connect()
        while not self.remote_device.services_resolved:
            sleep(0.5)
        self.remote_device.load_gatt()


#dev1 = InputDevice("/dev/input/event0")
#dev2 = InputDevice("/dev/input/event1")
#dev3 = InputDevice("/dev/input/event2")
#dev4 = InputDevice("/dev/input/event3")

client = MPDClient()

def isconnected():
    try:
        client.ping()
        return True
    except mpd.base.ConnectionError:
        return False

async def connect():
    await client.connect("localhost", 6600)

async def get_player_state():
    async for subsystem in client.idle():
        print("Change in", subsystem)
    #print("player state watcher")
    #client.send_idle('player')
    #while True:
    #    canRead = select([client], [], [], 0)[0]
    #    if canRead:
    #        client.fetch_idle()
    #        print(client.currentsong())
    #        client.send_idle('player')
    #    await asyncio.sleep(0.1)


if __name__  == '__main__':
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
                    print(udev)
                    if udev.action == u'add':
                        print(f"Device added: {udev}")
                        dev = InputDevice(udev.device_node)
                        fds[dev.fd] = dev
                        break
                    if udev.action == u'remove':
                        if udev.get('DEVPATH') and "virtual" in udev.get('DEVPATH'):
                            print("Need to reconnect headphones")
                            subprocess.Call(['pulseaudio', '-k'])
                            subprocess.Call(['pulseaudio', '--start'])
                            # This means we need to kill pulseaudio and reconnect.
                        print(f'Device removed: {udev}')
                        fds = {monitor.fileno(): monitor}
                        break
        try:
            for fd in r:
                dev = fds.get(fd, None)
                if dev:
                    for event in dev.read():
                        print(event)
                            
        # Hacky? But works excellently
        except OSError:
            continue


