#!/usr/bin/python3
"""Crop individual word images in grayscale images.

A library and program for cropping individual 4-character word images from the
cropped .png files created by steps 2-3.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import logging

import imageio
import numpy as np
from scipy import ndimage


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Crop an individual word image from a grayscale .png')

  flags.add_argument('input_image', type=str,
                     help='Image to crop: filename or URI')
  flags.add_argument('output_image', type=str,
                     help='Write output here: filename or URI')

  flags.add_argument('-r', '--rows', required=True, type=int,
                     help='Cropped word image size: rows')
  flags.add_argument('-c', '--cols', required=True, type=int,
                     help='Cropped word image size: columns')

  flags.add_argument('-tlx', '--top-left-x', required=True, type=float,
                     help='Initial x coord. of crop box left edge')
  flags.add_argument('-tly', '--top-left-y', required=True, type=float,
                     help='Initial y coord. of crop box top edge')

  flags.add_argument('-i', '--iters', default=100, type=int,
                     help='Iterations of box position refinement')

  flags.add_argument('--brighten', type=str,
                     help=('Do conditional brightening: the code "87;73;119" '
                           'means "if the maximum pixel value is less than '
                           '87, multiply pixel values by 119 / 73"'))

  flags.add_argument('-v', '--verbose', action='store_true',
                     help='Log debug information')

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

  # Perform the crop.
  image = imageio.imread(FLAGS.input_image, ignoregamma=True)
  cropped_image, dtlx, dtly = centre_and_crop(
      image,
      FLAGS.rows, FLAGS.cols, FLAGS.top_left_x, FLAGS.top_left_y, FLAGS.iters,
      postcrop)
  imageio.imwrite(FLAGS.output_image, cropped_image)
  logging.info('Total adjust: dtlx={:06.2f}, dtly={:06.2f}'.format(dtlx, dtly))


def centre_and_crop(image, rows, cols, tlx, tly, iters, postcrop=lambda x: x):
  """Crop a subimage of `image`, nudging crop window to centre on bright pixels.

  Args:
    rows: subimage rows.
    cols: subimage cols.
    tlx: initial x coordinate of subimage's top-left corner.
    tly: initial y coordinate of subimage's top-left corner.
    iters: number of nudging iterations.
    postcrop: a callable to apply to subimages after they are cropped.

  Returns: a 3-tuple with the following items:
    [0]: cropped subimage.
    [1]: nudging displacement in the X direction.
    [2]: nudging displacement in the Y direction.
  """
  # Set up sampling points and unscaled positioning gradients.
  xs, ys = np.meshgrid(
      np.arange(cols, dtype=float), np.arange(rows, dtype=float))
  xs = xs.ravel()  # Flattened for ndimage.map_coordinates.
  ys = ys.ravel()
  dtlx_dcol = 2.0 * xs / (cols-1) - 1.0  # Unscaled positioning gradients range
  dtly_drow = 2.0 * ys / (rows-1) - 1.0  # linearly from -1.0 to 1.0.
  xs += tlx  # Move sampling points to their initial positions.
  ys += tly

  # Extract initial subimage.
  extract_subimage = lambda: postcrop(ndimage.map_coordinates(
      image, coordinates=[ys, xs],
      order=3, mode='constant', cval=0.0).reshape((rows, cols)))
  subimage = extract_subimage()

  # Subimage position adjustment.
  if iters > 0:
    # Scale the positioning gradients so that the first step is no more than
    # 0.01 pixels in any direction.
    dtlx = np.dot(subimage.ravel(), dtlx_dcol)
    dtly = np.dot(subimage.ravel(), dtly_drow)
    if abs(dtlx) > 0.01: dtlx_dcol *= (0.01 / abs(dtlx))
    if abs(dtly) > 0.01: dtly_drow *= (0.01 / abs(dtly))

    # Compute positioning adjustment the current subimage. Adjustment is capped
    # so that it never exceeds 0.01 in X or Y.
    for it in range(iters):
      dtlx = np.dot(subimage.ravel(), dtlx_dcol)
      dtly = np.dot(subimage.ravel(), dtly_drow)
      if abs(dtlx) > 0.01: dtlx *= (0.01 / abs(dtlx))
      if abs(dtly) > 0.01: dtly *= (0.01 / abs(dtly))
      xs += dtlx
      ys += dtly
      logging.info(
          'Crop box adjust: tlx={:06.2f}, tly={:06.2f}, (dtlx={:07.4f}, '
          'dtly={:07.4f})'.format(xs[0], ys[0], dtlx, dtly))
      # Extract subimage.
      subimage = extract_subimage()

  return subimage, xs[0] - tlx, ys[0] - tly


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
