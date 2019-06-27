#!/usr/bin/python3
"""Optimistically convert "assembly" files to binary data.

We say "optimistically" because we are going to handle disagreements via
tiebreaking---whichever label has the most votes wins. May your CRCs be ever
in your favour...

(This program is simplistic in other ways, too. It assembles binary data
according to the ordering of files supplied on the command line, and then
according to the ordering of labels in the file. It even identifies label data
in "assembly" files just by looking for the @ symbol.)

THIS PROGRAM WRITES BINARY DATA TO STDOUT.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import binascii
import sys


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Compile binary data from "assembly" files.')

  flags.add_argument('assembly_files', type=str, nargs='+', help=(
      '"Assembly" files of the kind created by assemble_labels.py. Data '
      'emitted by this program will be emitted in the order of these files '
      '(and then in the order of label data within the files, irrespective of '
      'the listed addresses at the beginning of lines in the third section).'))

  return flags


#### MAIN PROGRAM ####


def main(FLAGS):
  for asmfile in FLAGS.assembly_files:
    sys.stderr.write('Processing {}...\n'.format(asmfile))
    with open(asmfile, 'r') as f:
      for line in f:
        if '@' in line:
          best_data, best_count = b'\x00\x00', 0
          for label in line.split(' ')[1:]:
            count = label.count(',') + 1
            if count > best_count:
              best_count = count
              best_data = binascii.a2b_hex(label[:4])
          sys.stdout.buffer.write(best_data)


#### MISCELLANEOUS ####


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
