#!/usr/bin/python3
"""Hand-label our grayscale word images.

This program presents word images to the terminal using Sixel graphics; a
compatible terminal emulator program is required (e.g. mlterm). The user gets
to enter labels for the images until they get sick of it (actually, they will
probably be sick of labeling well before the job is done, but that's life).

The user interface is simple: user sees an image, user types hex digits. If
the user doesn't want to label a particular image, then they can type the space
bar to move on to the next image.

Runs on Unix systems only for now. Sorry, windows...

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import itertools
import random
import sys
import termios
import tty
import wand.image

import label_database


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Label word images.')

  flags.add_argument('label_database', type=str,
                     help=('CSV file containing image paths, labels, and '
                           'the number of times a particular label was '
                           'supplied for an image. The CSV header should be '
                           '"Filename,Label,Count".'))

  flags.add_argument('-n', '--num-labels', required=True, type=int,
                     help=('Stop after this many images have been labeled '
                           'and their labels verified.'))

  flags.add_argument('-b', '--label-bias', default=0.2, type=float,
                     help=('Degree to which this program would prefer to label '
                           'new images over verifying old ones.'))
  flags.add_argument('-s', '--scale', default=3.0, type=float,
                     help='Scale images by this factor when showing them.')

  flags.add_argument('--mark-apl-ros-c000-zeros', action='store_true',
                     help=("It's known that the data words in the APL ROS are "
                           'all 0000 from C000 to DFFE. Mark them as such. '
                           "It's only necessary to do this once, but doesn't "
                           'hurt to do it more times.'))

  return flags


def main(FLAGS):
  print('Loading...')
  with label_database.Database(FLAGS.label_database) as db:
    if FLAGS.mark_apl_ros_c000_zeros:
      print('Marking APL ROS known-zeros at C000...')
      mark_apl_ros_c000_zeros(db)

    for act_count in itertools.count():
      filename, image = next_image_and_housekeeping(
          db, FLAGS.num_labels, FLAGS.label_bias, FLAGS.scale, act_count)

      if filename is None:
        print('You are finished! Thank you for your hard work!')
        return

      label = quiz_user_for_label(image)
      if not label:
        print('Skipping this image.')
      elif label == 'Q':
        print('Quitting...')
        return
      else:
        db.label(filename, label)


def quiz_user_for_label(image):
  """Present an image and request a label from the user.

  The image is printed to the screen in Sixel format. Users will type in four
  hex digits to supply a label, capital-'Q' to indicate a desire to quit, or
  ' ' to decline to label the image.

  Args:
    image: wand.image.Image to display to the user.

  Returns:
    4-character string of hex digits, 'XXXX' if the user believes the image has
    been corrupted by the image spanning multiple frames, 'Q' if the user has
    indicated that they wish to quit, or '' if they decline to label the image.
  """
  # Display the image and print prompt (note cursor positioning).
  sys.stdout.buffer.write(image.make_blob('sixel'))
  sys.stdout.write('\n   label >>    <<\b\b\b\b\b\b')
  sys.stdout.flush()

  # Obtain label characters from user.
  label_chars = [None] * 4
  pos = 0
  while None in label_chars:
    char = getch()

    if char in '0123456789abcdefABCDEF':
      label_chars[pos] = char.upper()
      pos += 1
      sys.stdout.write(char.upper())
    elif char == '\x7f' and pos > 0:  # Did the user type backspace?
      pos -= 1
      label_chars[pos] = None
      sys.stdout.write('\b \b')
    elif char in 'zZ':  # Did the user type 'Z'?
      print()           # Image is all zeroes.
      print()
      return '0000'
    elif char in 'mM':  # Did the user type 'M'?
      print()           # Image is corrupted by screen transition.
      print()
      return 'XXXX'
    elif char == 'Q':  # Did the user want to quit?
      print()
      return 'Q'
    elif char == ' ':  # Did the user decide not to label this image?
      print()
      return ''

    sys.stdout.flush()

  print()
  print()
  return ''.join(label_chars)


def next_image_and_housekeeping(db, num_labels, label_bias, scale, act_count):
  """Retrieve the next image to label, and do some housekeeping.

  Args:
    db: a label_database.Database object.
    num_labels: Number of verified labels desired by the user.
    label_bias: A bias that controls the degree to which we ought to load a new
        image to label rather than an already-labeled image for verification.
    scale: amount of scaling to apply to loaded images.
    action_count: how many labeling actions the user has undertaken in this
        session prior to now. This function will save the database to disk after
        every 100 labeling actions.

  Returns:
    (None, None) if there are already `num_labels` verified labels in the
    database. Otherwise, a 2-tuple whose elements are:
    [0]: filename of an image to label.
    [1]: wand.image.Image object of the (scaled) image to label.
  """
  # Save the database occasionally, and find out if we have work to do.
  if (act_count + 1) % 100 == 0: db.save()
  num_done = db.num_labels_with_counts_of_at_least(2)
  if num_done >= num_labels: return None, None

  # Choose an image to label: either a novel one or an unverified one.
  num_unverified = db.num_labels_with_counts_of(1)
  fraction_unlabeled = (num_labels - num_done - num_unverified) / num_labels
  novel_image_probability = fraction_unlabeled * (1 + label_bias)
  if num_unverified > 0 and random.random() > novel_image_probability:
    filename = db.random_label_with_count_of(1)  # Choose to verify a label.
  else:
    filename = db.random_label_with_count_of(0)  # Label a novel image.

  # Attempt to load the image, and scale it.
  image = wand.image.Image(filename=filename)
  image.resize(width=round(image.width * scale),
               height=round(image.height * scale))

  return filename, image


def mark_apl_ros_c000_zeros(db):
  """Mark APL ROS known-zeros between C000-DFFE."""
  for prefix in ('./APL/APL_LROS_C000/02_words',
                 './APL_ii/APL_LROS_ii_C000/02_words'):
    for frame in range(2500):  # Not sure quite which frames it is...
      for subimage in ('0_1', '0_2', '0_3', '0_4', '0_5', '0_6', '0_7', '0_8',
                       '1_1', '1_2', '1_3', '1_4', '1_5', '1_6', '1_7', '1_8'):
        filename = '{}/{:04d}_{}.png'.format(prefix, frame, subimage)
        if filename in db:
          db.label(filename, '0000')  # Label twice: verify '0000' value.
          db.label(filename, '0000')


def getch():
  """Retrieve a single character from stdin with the terminal in raw mode."""
  stdin_fd = sys.stdin.fileno()
  old_attrs = termios.tcgetattr(stdin_fd)
  try:
    tty.setraw(stdin_fd)
    char = sys.stdin.read(1)
  finally:
    termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attrs)
  return char


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
