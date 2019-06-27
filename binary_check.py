#!/usr/bin/python3
"""Do 16-bit CRC checks on $1800-byte sections of binary files.

This implementation is a Python transcription of IBM 5100 machine code from the
5100's executable ROS. The CRC is initialised with the value 0xffff and updated
with each new byte in the binary file section. The CRC check is assumed to have
passed if the final CRC is 0x0000.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
from typing import Tuple


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Do CRC checks on $1800-byte sections of the file.')

  flags.add_argument('binary_file', type=str, help=(
      'File to check for valid CRC in $1800-byte sections.'))

  flags.add_argument('--starts', type=str, nargs='*', help=(
      'List of starting positions for sections, if $1800-byte intervals '
      'isn\'t your thing. Values are parsed as hex digits.'))

  return flags


def update_crc(byte: int, crc: Tuple[int, int]) -> Tuple[int, int]:
  """Update a 16-bit CRC given a new byte."""
  # Set up the 16 registers of the 5100.
  r = [(0, 0) for _ in range(16)]
  r[9] = (crc[0] & 0xff, crc[1] & 0xff)
  r[10] = (0, byte & 0xff)

  # MHL R14, R9
  r[14] = (r[14][0], r[9][0])

  # XOR R14, R10
  r[14] = (r[14][0], r[14][1] ^ r[10][1])

  # MOVE R1, R14
  r[1] = r[14]

  # MOVE R15, R14
  r[15] = r[14]

  # SWAP R15
  r[15] = (r[15][0], (r[15][1] << 4 & 0xff) | (r[15][1] >> 4))

  # XOR R14, R15
  r[14] = (r[14][0], r[14][1] ^ r[15][1])

  # CLR R14, #$0F
  r[14] = (r[14][0], r[14][1] & 0xf0)

  # XOR R14, R9
  r[14] = (r[14][0], r[14][1] ^ r[9][1])

  # MOVE R9, R1
  r[9] = r[1]

  # CLR R15, #$F0
  r[15] = (r[15][0], r[15][1] & 0x0f)

  # XOR R9, R15
  r[9] = (r[9][0], r[9][1] ^ r[15][1])

  # ROR3 R1
  r[1] = (r[1][0], (r[1][1] << 5 & 0xff) | (r[1][1] >> 3))

  # MOVE R15, R1
  r[15] = r[1]

  # CLR R15, #$E0
  r[15] = (r[15][0], r[15][1] & 0x1f)

  # XOR R14, R15
  r[14] = (r[14][0], r[14][1] ^ r[15][1])

  # CLR R1, #$1F
  r[1] = (r[1][0], r[1][1] & 0xe0)

  # XOR R9, R1
  r[9] = (r[9][0], r[9][1] ^ r[1][1])

  # SWAP R15
  r[15] = (r[15][0], (r[15][1] << 4 & 0xff) | (r[15][1] >> 4))

  # MOVE R1, R15
  r[1] = r[15]

  # CLR R15, #$1F
  r[15] = (r[15][0], r[15][1] & 0xe0)

  # XOR R9, R15
  r[9] = (r[9][0], r[9][1] ^ r[15][1])

  # CLR R1, #$FE
  r[1] = (r[1][0], r[1][1] & 0x01)

  # XOR R14, R1
  r[14] = (r[14][0], r[14][1] ^ r[1][1])

  # MLH R9, R14
  r[9] = (r[14][1], r[9][1])

  # RET R8
  return r[9]


#### MAIN PROGRAM ####


def main(FLAGS):
  with open(FLAGS.binary_file, 'rb') as f:
    all_data = f.read()

    if FLAGS.starts:
      starts = (int(s, 16) for s in FLAGS.starts)
    else:
      starts = range(0, len(all_data), 0x1800)

    for start in starts:
      end = start + 0x1800
      data = all_data[start:end]
      
      crc = (0xff, 0xff)
      for byte in data:
        crc = update_crc(byte, crc)
      ok = 'OK' if crc == (0x0, 0x0) else '{:X}{:X}'.format(*crc)

      # data[-3] is the section identifier.
      print('{:X} to {:X}: {:X}; {}'.format(start, end-1, data[-3], ok))


#### MISCELLANEOUS ####


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
