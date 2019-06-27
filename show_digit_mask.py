#!/usr/bin/python3
"""Show digit masking on an image file. Uses Sixel graphics.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import numpy as np
import os
import skimage
import skimage.io
import sys
import tempfile
import wand.image

import labels_classification


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Show how our image masking segments digits.')

  flags.add_argument('image', type=str, help='Image file to segment.')

  return flags


def main(FLAGS):
  # Load the image.
  image = skimage.color.rgb2gray(
      skimage.io.imread(FLAGS.image)).astype(np.float32)

  # Obtain versions with the four digits masked.
  masked = [labels_classification.mask_nth_digit_in_image(image, n)
            for n in range(4)]

  # Create temporary files for the masked images.
  t_masked = [tempfile.mkstemp(suffix='.png')[1] for _ in masked]
  for m, fn in zip(masked, t_masked):
    skimage.io.imsave(fn, m.astype(np.uint8))

  # Display each image with Sixel graphics.
  print('Original image')
  _imshow(FLAGS.image)
  for i, fn in enumerate(t_masked):
    print('Masked digit', i + 1)
    _imshow(fn)

  # Delete temporary files.
  for fn in t_masked:
    os.remove(fn)


def _imshow(filename):
  """Show an image file using Sixel graphics."""
  image = wand.image.Image(filename=filename)
  image.resize(width=(image.width * 2), height=(image.height * 2))
  sys.stdout.buffer.write(image.make_blob('sixel'))


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
