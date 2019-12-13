from .Topics import TopicQueue
from .Extracts import ExtractQueue
from .Items import ItemQueue
from select import select


class Controller(TopicQueue, ExtractQueue, ItemQueue, object):
    """ Combines TopicQueue, ExtractQueue, ItemQueue,
    MpdBase and Device classes. Connects bluetooth, and
    runs the menu loop and saves the state of the program"""

    def __init__(self):
        TopicQueue.__init__(self)
        ExtractQueue.__init__(self)
        ItemQueue.__init__(self)
        self.current_playlist = ""
        self.clozing = False
        self.recording = False
        self.active_keys = {}

    def main_loop(self):
        """ Main menu loop for Audio Assistant """
        # Loads global topic queue by default
        self.get_global_topics()
        self.load_global_topics()
        self.load_topic_options()
        while True:
            r, w, x = select(controller.devices, [], [])
            for fd in r:
                for event in controller.devices[fd].read():
                    if event.value == 1:
                        if event.code in audio_assistant.active_keys:
                            audio_assistant.active_keys[event.code]()
