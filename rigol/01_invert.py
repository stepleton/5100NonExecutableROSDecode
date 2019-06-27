#!/usr/bin/python3
"""Bitwise-invert the hex digits in our CSV files."""

import argparse


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Invert hex digits in CSV files. Output goes to stdout.')

  flags.add_argument('csv_file', type=argparse.FileType('r'),
                     help='CSV file to process')

  return flags


def main(FLAGS):
  for line in FLAGS.csv_file:
    time, bytestr = line.rstrip().split(',')
    rtsetyb = '{:02X}'.format(~int(bytestr, 16) & 0xff)
    print('{},{}'.format(time, rtsetyb))


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
