import subprocess
from subprocess import DEVNULL
from config import *
import os
from models import ExtractFile, ItemFile, session


# TODO
# Change the database model to include ItemFile
# Add a function to the extract keys to load a local item queue

def cloze_processor(item):
    extract_fp = item.extractfile.extract_filepath
    extract_length = item.extractfile.topicfile_endstamp - item.extractfile.topicfile_startstamp
    cloze_start = item.cloze_startstamp
    cloze_end = item.cloze_endstamp
    # beep length = length of the cloze
    beep_length = cloze_end - cloze_start

    filename = os.path.basename(extract_fp)
    filename, ext = os.path.splitext(filename)

    # TODO Use the rowid of ItemFile to give each a unique name?
    question_fp = os.path.join(QUESTIONFILES_DIR,
                              (filename + "-" +
                               "QUESTION" + ext))
    cloze_fp = os.path.join(QUESTIONFILES_DIR,
                           (filename + "-" +
                            "CLOZE" + ext))

    # Non-blocking
    subprocess.Popen([
            ## INPUTS
            # The extract file
            'ffmpeg',
            '-i',
            extract_fp,
            # Sine wave beep generator
            '-f',
            'lavfi',
            '-i',
            'sine=frequency=1000:duration=' + str(beep_length),
            ## FILTERS
            '-filter_complex',
            # Cut the beginning of the extract before the cloze
            '[0:a]atrim=' + "0" + ":" + str(cloze_start) + "[beg]" + ";" + \
            # Cut the beginning of the cloze to the end of the cloze
            '[0:a]atrim=' + str(cloze_start) + ":" + str(cloze_end) + "[cloze]" + ";" + \
            # Cut the end of the extract after the cloze
            '[0:a]atrim=' + str(cloze_end) + ":" + str(extract_length) + "[end]" + ";" + \
            # concatenate the files and
            # [1:0] is the sine wave
            '[beg][1:0][end]concat=n=3:v=0:a=1[question]',
            '-map',
            # Output the clozed extract
            '[question]',
            question_fp,
            '-map',
            # Output the clozed word / phrase
            '[cloze]',
            cloze_fp
    ], shell=False, stdout=DEVNULL)

    # Use named tuple?
    return question_fp, cloze_fp


def get_items():
    items  = (session
              .query(ItemFile)
              .filter(ItemFile.cloze_startstamp != None)
              .filter(ItemFile.cloze_endstamp != None)
              .all())
    if items:
        return items
    else:
        return None


if __name__ == "__main__":
    items = get_items()
    if items:
        for item in items:
            question, cloze = cloze_processor(item)
            if question and cloze:
                item.question_filepath = question
                item.cloze_filepath = cloze
                session.commit()
