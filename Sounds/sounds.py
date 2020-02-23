import simpleaudio as sa
import subprocess


# TODO: Add credits to the person who made these free sounds.


def negative_beep():
    """ Beeps to indicate command failure.
    """
    filename = '/home/pi/bin/lecture_assistant/Sounds/negative_2.wav'
    wave_obj = sa.WaveObject.from_wave_file(filename)
    wave_obj.play()


def click_sound1():
    """ Clicks as feedback when pressing buttons.
    """
    filename = '/home/pi/bin/lecture_assistant/Sounds/click_2.wav'
    wave_obj = sa.WaveObject.from_wave_file(filename)
    wave_obj.play()


def click_sound2():
    """ Clicks as feedback when pressing buttons.
    """
    filename = '/home/pi/bin/lecture_assistant/Sounds/click.wav'
    wave_obj = sa.WaveObject.from_wave_file(filename)
    wave_obj.play()


def positive_beep():
    """ Beeps to indicate command success.
    """
    filename = '/home/pi/bin/lecture_assistant/Sounds/positive.wav'
    wave_obj = sa.WaveObject.from_wave_file(filename)
    wave_obj.play()


def load_beep():
    """ Beeps to indicate archiving of topics, items and extracts
    """
    filename = '/home/pi/bin/lecture_assistant/Sounds/load.wav'
    wave_obj = sa.WaveObject.from_wave_file(filename)
    wave_obj.play()


def espeak(words: str):
    """ Text to speech communication with the user
    """
    if words:
        subprocess.Popen(['espeak', words])
