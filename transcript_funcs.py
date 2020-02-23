import webvtt
import os
import time
from models import session, ExtractFile
from config import *


def vtt_to_text(subs_file):
    vtt = webvtt.read(subs_file)
    transcript = ""

    lines = []
    for line in vtt:
        # strip newlines
        # split string if newline present in the middle
        # add lines to lines array
        lines.extend(line.text.strip().splitlines())

    previous = None
    for line in lines:
        if line == previous:
            continue
        transcript += " " + line
        previous = line

    return transcript


def find_within_range(start, end, subs_file):
    # Returns captions within between a start and
    # end timestamp

    # Takes seconds and converts into %H:%M:%S format
    # Works up to 24hrs
    start = time.strftime("%H:%M:%S", time.gmtime(int(start)))
    end = time.strftime("%H:%M:%S", time.gmtime(int(end)))

    vtt = webvtt.read(subs_file)
    transcript = ""
    lines = []
    for caption in vtt:
        if caption.end > start and caption.start < end:
            lines.extend(caption.text.strip().splitlines())
    previous = None
    for line in lines:
        if line == previous:
            continue

        transcript += " " + line
        previous = line

    return transcript


def update_extract_table():
    # Check if there exists a subs file first
    extracts = (session
                .query(ExtractFile)
                .filter_by(extract_transcript=None)
                .all())
    if extracts:
        for extract in extracts:
            start = extract.topicfile_startstamp
            end = extract.topicfile_endstamp
            filepath = extract.topicfiles.filepath
            subsfile = os.path.join(
                    TOPICFILES_DIR,
                    os.path.splitext(os.path.basename(filepath))[0] + ".en.vtt")
            transcript = find_within_range(start, end, subsfile)
            extract.extract_transcript = transcript
            session.commit()
