import subprocess
from config import *
import os
from models import ExtractFile, TopicFile, session


# TODO
# Change the database model to include ItemFile
# Add a function to the extract keys to load a local item queue

def cloze_processor(extract):
      
    ext = ".wav"
    extract_fp = extract.extract_filepath       
    extract_length = extract.topicfile_endstamp - extract.topicfile_startstamp
    cloze_start = extract.cloze_startstamp
    cloze_end = extract.cloze_endstamp
    # beep length = length of the cloze
    beep_length = cloze_end - cloze_start

    filename = os.path.basename(extract.extract_filepath)    
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
            ##FILTERS
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
    ])
    
    # Use named tuple?
    return (question_fp, cloze_fp)


def get_extracts():
    extracts = (session
                .query(ExtractFile)
                .filter(ExtractFile.cloze_startstamp != None)
                .filter(ExtractFile.cloze_endstamp != None)
                .filter_by(id=1)
                .all())
    if extracts:
        return extracts
    else:
        return None


if __name__ == "__main__":
    extracts = get_extracts()
    if extracts:
        for extract in extracts:
            question, cloze = cloze_processor(extract)
            if question and cloze:
                extract.question_filepath = question
                extract.atom_filepath = cloze
                session.commit()

