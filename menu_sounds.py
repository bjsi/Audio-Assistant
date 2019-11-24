import simpleaudio as sa

def negative(func):
    def wrapper(*args, **kwargs):
        filename = '/home/pi/bin/lecture_assistant/menu-sounds/negative_2.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        func(*args, **kwargs)
    return wrapper


def click_two(func):
    def wrapper(*args, **kwargs):
        filename = '/home/pi/bin/lecture_assistant/menu-sounds/click_2.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        func(*args, **kwargs)
    return wrapper


def click_one(func):
    def wrapper(*args, **kwargs):
        filename = '/home/pi/bin/lecture_assistant/menu-sounds/click.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        func(*args, **kwargs)
    return wrapper


def positive(func):
    def wrapper(*args, **kwargs):
        filename = '/home/pi/bin/lecture_assistant/menu-sounds/positive.wav'
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        func(*args, **kwargs)
    return wrapper
