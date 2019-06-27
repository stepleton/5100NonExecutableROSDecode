#!/usr/bin/python3
"""Let's slim down our CSV files.

We'll do it by getting rid of lines where the byte on the lines is the same
as the byte at the preceding timestep.

We'll also strip out the weird non-ascii characters from the file. Oh Rigol...
"""

import argparse
import string


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Slim down CSV files. Output goes to stdout.')

  flags.add_argument('csv_file', type=argparse.FileType('r'),
                     help='CSV file to process')

  return flags


def main(FLAGS):
  # Strip first two lines (headers) from the file.
  next(FLAGS.csv_file)
  next(FLAGS.csv_file)

  prev_byte = ''
  for line in FLAGS.csv_file:
    # Strip out non-ASCII, since some lines have plenty of $00 bytes.
    #line = line.encode('ascii', errors='ignore').decode().rstrip()
    line = ''.join(c for c in line if c in string.printable).rstrip()
    # Robustly parse the line so that partial lines prepended to the current
    # line don't wreck things.
    try:
      timestep, byte = line.split(',')[-2:]
    except ValueError:
      pass  # Not enough values to unpack, probably.

    if byte != prev_byte:
      print('{},{}'.format(timestep, byte))
      prev_byte = byte


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
