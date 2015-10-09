from __future__ import print_function

import os
import re
import time
import fcntl
import logging
import hashlib
import unicodedata
import json

from distutils.util import strtobool
from subprocess import Popen, PIPE
from contextlib import contextmanager

# Constants needed for `open_with_lock` function
MAX_ATTEMPTS = 1000
TIME_BETWEEN_ATTEMPTS = 1  # In seconds


def print_boxed(string):
    splitted_string = string.split('\n')
    max_len = max(map(len, splitted_string))
    box_line = u"\u2500" * (max_len + 2)

    out = u"\u250c" + box_line + u"\u2510\n"
    out += '\n'.join([u"\u2502 {} \u2502".format(line.ljust(max_len)) for line in splitted_string])
    out += u"\n\u2514" + box_line + u"\u2518"
    print(out)


def yes_no_prompt(query, default=None):
    available_prompts = {None: " [y/n] ", 'y': " [Y/n] ", 'n': " [y/N] "}

    if default not in available_prompts:
        raise ValueError("Invalid default: '{}'".format(default))

    while True:
        try:
            answer = raw_input("{0}{1}".format(query, available_prompts[default]))
            return strtobool(answer)
        except ValueError:
            if answer == '' and default is not None:
                return strtobool(default)


def chunks(sequence, n):
    """ Yield successive n-sized chunks from sequence. """
    for i in xrange(0, len(sequence), n):
        yield sequence[i:i + n]


def generate_uid_from_string(value):
    """ Create unique identifier from a string. """
    return hashlib.sha256(value).hexdigest()


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to underscores. Also strips leading and
    trailing whitespace.

    Reference
    ---------
    https://github.com/django/django/blob/1.7c3/django/utils/text.py#L436
    """
    value = unicodedata.normalize('NFKD', unicode(value, "UTF-8")).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return str(re.sub('[-\s]+', '_', value))


def encode_escaped_characters(text, escaping_character="\\"):
    """ Escape the escaped character using its hex representation """
    def hexify(match):
        return "\\x{0}".format(match.group()[-1].encode("hex"))

    return re.sub(r"\\.", hexify, text)


def decode_escaped_characters(text):
    """ Convert hex representation to the character it represents """
    if len(text) == 0:
        return ''

    def unhexify(match):
        return match.group()[2:].decode("hex")

    return re.sub(r"\\x..", unhexify, text)


@contextmanager
def open_with_lock(*args, **kwargs):
    """ Context manager for opening file with an exclusive lock. """
    dirname = os.path.dirname(args[0])
    filename = os.path.basename(args[0])
    lockfile = os.path.join(dirname, "." + filename)

    no_attempt = 0
    while no_attempt < MAX_ATTEMPTS:
        try:
            os.mkdir(lockfile)  # Atomic operation
            f = open(*args, **kwargs)
            yield f
            f.close()
            os.rmdir(lockfile)
            break
        except OSError:
            logging.info("Can't immediately write-lock the file ({0}), retrying in {1} sec. ...".format(filename, TIME_BETWEEN_ATTEMPTS))
            time.sleep(TIME_BETWEEN_ATTEMPTS)
            no_attempt += 1


def save_dict_to_json_file(path, dictionary):
    with open(path, "w") as json_file:
        json_file.write(json.dumps(dictionary, indent=4, separators=(',', ': ')))


def load_dict_from_json_file(path):
    with open(path, "r") as json_file:
        return json.loads(json_file.read())


def detect_cluster():
    # Get server status
    try:
        output = Popen(["qstat", "-B"], stdout=PIPE).communicate()[0]
        if isinstance(output, bytes):
            output = output.decode("utf-8")
    except OSError:
        # If qstat is not available we assume that the cluster is unknown.
        return None
    # Get server name from status
    server_name = output.split('\n')[2].split(' ')[0]
    # Cleanup the name and return it
    cluster_name = None
    if server_name.split('.')[-1] == 'm':
        cluster_name = "mammouth"
    elif server_name.split('.')[-1] == 'guil':
        cluster_name = "guillimin"
    elif server_name.split('.')[-1] == 'helios':
        cluster_name = "helios"
    return cluster_name


def get_launcher(cluster_name):
    if cluster_name == "helios":
        return "msub"
    else:
        return "qsub"
