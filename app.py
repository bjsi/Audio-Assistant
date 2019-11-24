from controller import Controller
from config import *


if __name__ == "__main__":
    if Controller.device_connected(CONTROLLER) and \
            Controller.device_connected(HEADPHONES):
        c = Controller()
        c.menu_loop()
       
       # Have a function to ping periodically to test whether
       # either headphones or controller is disconnected
       # try:
       #     c.menu_loop()
       # except (errors):
       #     try:
       #        if Controller.device_connected(CONTROLLER) and \
       #             Controller.device_connected(HEADPHONES)
       #            c.menu_loop()
       # finally:
       #     pass
