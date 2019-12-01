from AudioAssistant import AudioAssistant
from BluetoothDevices import BTDevice
from config import CONTROLLER, HEADPHONES
from select import select


def main_loop():
    """Set up the main loop for the controller.
    Reads key codes and values from the connected
    device and executes the associated commands in the
    AudioAssistant active_keys dict.
    """
    while True:
        r, w, x = select(controller.devices, [], [])
        for fd in r:
            for event in controller.devices[fd].read():
                if event.value == 1:
                    if event.code in audio_assistant.active_keys:
                        audio_assistant.active_keys[event.code]()


if __name__ == "__main__":
    audio_assistant = AudioAssistant()
    headphones = BTDevice(CONTROLLER['address'],
                 CONTROLLER['name'])
    controller = BTDevice(HEADPHONES['address'],
                 HEADPHONES['name'],
                 CONTROLLER['input_devices'],
                 CONTROLLER['keys'])

    # TODO Test this
    if controller.bt_connect() and headphones.bt_connect():
        audio_assistant.load_global_topics()
        audio_assistant.seek_to_cur_timestamp()
        try:
            main_loop()
        except (PermissionError, OSError):
            controller.bt_connect()
            headphones.bt_connect()
        finally:
            main_loop()
