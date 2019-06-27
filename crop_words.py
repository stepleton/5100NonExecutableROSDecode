#!/usr/bin/python3
"""Crop multiple word images from grayscale images.

A program for cropping multiple 4-character word images from the cropped .png
files created by steps 2-3.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import csv
import imageio
import logging
import math
import numpy as np

import crop_word


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Crop multiple word images from a grayscale .png')

  flags.add_argument('input_image', type=str,
                     help='Image to crop: filename or URI')
  flags.add_argument('crop_list', type=str,
                     help=('CSV file listing crop image name and initial '
                           'x,y locations of crop box top-left corners. The '
                           'CSV header should be "Name,tlx,tly"'))
  flags.add_argument('output_prefix', type=str,
                     help='Prefix string for crop image filenames')

  flags.add_argument('-r', '--rows', required=True, type=int,
                     help='Cropped word image size: rows')
  flags.add_argument('-c', '--cols', required=True, type=int,
                     help='Cropped word image size: columns')


  flags.add_argument('-i', '--iters', default=200, type=int,
                     help='Iterations of box position refinement.')

  flags.add_argument('--brighten', type=str,
                     help=('Do conditional brightening: the code "87;73;119" '
                           'means "if the maximum pixel value is less than '
                           '87, multiply pixel values by 119 / 73"'))

  flags.add_argument('-v', '--verbose', action='store_true',
                     help='Log debug information.')

  return flags


def main(FLAGS):
  # Verbose logging if desired.
  if FLAGS.verbose: logging.getLogger().setLevel(logging.INFO)

  # Set up conditional brightening if desired.
  if FLAGS.brighten:
    thresh, denom, num = (float(x) for x in FLAGS.brighten.split(';'))
    postcrop = lambda x: np.uint8(x * num / denom) if np.max(x) < thresh else x
  else:
    postcrop = None

  # Load the .csv file listing initial crop locations.
  with open(FLAGS.crop_list, newline='') as csvfile:
    reader = csv.reader(csvfile)
    fieldnames = next(reader)
    crop_locs = list(row for row in reader)
    assert fieldnames == ['Name', 'tlx', 'tly'], (
        'Crop list file column names must be "Name,tlx,tly"')

  # Load the image and perform the crops. We raise an error if one of the
  # crops is adjusted in a way that moves it more than three pixels from its
  # initial location.
  image = imageio.imread(FLAGS.input_image, ignoregamma=True)
  for name, tlx, tly in crop_locs:
    tlx, tly = float(tlx), float(tly)
    logging.info('Cropping {} from {}, starting at tlx={}, tly={}'.format(
        name, FLAGS.input_image, tlx, tly))
    cropped_image, dx, dy = crop_word.centre_and_crop(
        image, FLAGS.rows, FLAGS.cols, tlx, tly, FLAGS.iters, postcrop)
    imageio.imwrite('{}{}.png'.format(FLAGS.output_prefix, name), cropped_image)
    logging.info('Total adjust: dtlx={:06.2f}, dtly={:06.2f}'.format(dx, dy))

    total_nudge = math.sqrt(dx*dx + dy*dy)
    assert total_nudge < 3.0, (
        'Excessive crop adjustment of {}; giving up.'.format(total_nudge))


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
