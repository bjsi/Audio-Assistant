#!/usr/bin/env python3 
import sys
import os
import subprocess
from config import *
from models import *

def generate_sine(length, out_filepath):
    """ length in seconds.miliseconds """

    if length > 0:
        subprocess.call([
            'ffmpeg',
            '-f',
            'lavfi',
            '-i',
            'sine=frequency=1000:duration=' + str(length),
            out_filepath
        ])
        # if success...
        return out_filepath

def concatenate(beginning_part, sine, end_part, out_filepath):
    
    # requires .wav extension

    subprocess.call([
        'sox',
        beginning_part,
        sine,
        end_part,
        out_filepath
    ])

    # if success
    return out_filepath


def cut(start, end, in_filepath, out_filepath):
    """ start and end in seconds.miliseconds """

    if (  end > start 
          and os.path.exists(in_filepath)
          and out_filepath ):

        subprocess.call([
            'ffmpeg',
            '-i',
            in_filepath,
            '-ss',
            str(start),
            '-to',
            str(end),
            out_filepath
        ])

        # add communicate return code
        # if success ...
        return out_filepath
    else:
        return None


def get_extracts():
    extracts = (session
                .query(ExtractFile)
                .filter(ExtractFile.cloze_startstamp != None)
                .filter(ExtractFile.cloze_endstamp != None)
                .all())

    if extracts:
        return extracts
    else:
        return None


def process_extract(extract):
    """  """
    extract_start = 0
    cloze_start = extract.cloze_startstamp
    cloze_end = extract.cloze_endstamp
    extract_end = extract.topicfile_endstamp - extract.topicfile_startstamp

    filename = os.path.basename(extract.extract_filepath)    
    filename, ext = os.path.splitext(filename)

    beginning_fp = os.path.join(QUESTIONFILES_DIR, (filename + "-" + "BEG" + ext))
    cloze_fp = os.path.join(QUESTIONFILES_DIR, (filename + "-" + "ATOM" + ext))
    end_fp = os.path.join(QUESTIONFILES_DIR, (filename + "-" + "END" + ext))

    beginning_part = cut(extract_start,
                         cloze_start,
                         extract.extract_filepath,
                         beginning_fp)

    cloze_part = cut(cloze_start,
                     cloze_end,
                     extract.extract_filepath,
                     cloze_fp)

    end_part = cut(cloze_end,
                   extract_end,
                   extract.extract_filepath,
                   end_fp)

    if ( beginning_part 
         and cloze_part
         and end_part ):
        
        duration = cloze_end - cloze_start
        sine_fp = os.path.join(QUESTIONFILES_DIR, (filename + "-" + "SINE" + ext))
        sine = generate_sine(duration, sine_fp)

        if sine:
            out_filepath = os.path.join(QUESTIONFILES_DIR, (filename + "-" + "QUESTION" + ext))
            concatenated = concatenate(beginning_part,
                                       sine,
                                       end_part,
                                       out_filepath)
            if concatenated:
                return (concatenated, cloze_part)


if __name__ == "__main__":
    extracts = get_extracts()
    if extracts:
        for extract in extracts:
            question_part, cloze_part = process_extract(extract)
            if question_part and cloze_part:
                # insert into DB
                print("Success!")
                extract.question_filepath=question_part
                extract.atom_filepath=cloze_part
                session.commit()
                # rm '/home/pi/audiofiles/questionfiles/*{BEG,END,SINE}*
