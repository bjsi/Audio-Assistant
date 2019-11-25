import simpleaudio as sa
import subprocess


def negative(func):
    """
    Makes a negative sounding beep to indicate command failure
    """
    def wrapper(*args, **kwargs):
        filename = '/home/pi/bin/lecture_assistant/menu-sounds/negative_2.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        func(*args, **kwargs)
    return wrapper


def click_two(func):
    """
    Makes a click sound. Used for feedback when pressing
    buttons on the controller
    """
    def wrapper(*args, **kwargs):
        filename = '/home/pi/bin/lecture_assistant/menu-sounds/click_2.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        func(*args, **kwargs)
    return wrapper


def click_one(func):
    """
    Makes a click sound. Used for feedback when pressing
    buttons on the controller
    """
    def wrapper(*args, **kwargs):
        filename = '/home/pi/bin/lecture_assistant/menu-sounds/click.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        func(*args, **kwargs)
    return wrapper


def positive(func):
    """
    Makes a positive sounding beep to indicate command success
    """
    def wrapper(*args, **kwargs):
        filename = '/home/pi/bin/lecture_assistant/menu-sounds/positive.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        func(*args, **kwargs)
    return wrapper


def speak(words: str):
    """
    Uses the espeak program as text to speech to communicate
    to the user
    """
    if words:
        subprocess.Popen(['espeak',
                          words])
