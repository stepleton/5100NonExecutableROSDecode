#!/usr/bin/python3
"""Manual intervention to resolve disagreements between labelings.

This program identifies labels that don't match across several label databases.
It presents these one-by-one alongside their mislabeled images in an interface
that allows the user to do any of the following:

    (a) Select one of the database labels for the image.
    (b) Manually specify the label to use.
    (c) Mark all images in the same screen image as 'XXXX'.

NOTE: This file uses functions that also live in
`labels_exploit_disagreement.py`. It's bad and I don't care.

Runs on Unix systems only for now. Sorry, windows...

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""


import argparse

import label_database
import labels_exploit_disagreement as led
import os
import sys
import wand.image


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Resolve label database disagreements with manual labels.')

  flags.add_argument('label_database', type=str,
                     help=('CSV file containing image paths, labels, and '
                           'the number of times a particular label was '
                           'supplied for an image. The CSV header should be '
                           '"Filename,Label,Count". This database will '
                           'participate in label comparisons; label changes '
                           'will be saved here.'))

  flags.add_argument('screen_image_subdir', type=str,
                     help=('Directories found in label image paths in the '
                           'label database are assumed to differ from screen '
                           'image directories in only the last subdirectory. '
                           'This flag specifies that subdirectory\'s name.'))

  flags.add_argument('databases_to_compare', type=str, nargs='+',
                     help=('Label databases to compare for finding labeling '
                           'disagreements. Will only be opened read-only.'))

  return flags


#### MAIN PROGRAM ####


def main(FLAGS):
  # Load databases that we will compare.
  if FLAGS.label_database in FLAGS.databases_to_compare: raise ValueError(
      'The label database to modify should not also be listed as one of the '
      'additional databases under comparison.')
  if len(FLAGS.databases_to_compare) > 9: raise ValueError(
      'Too many databases are listed. This program supports ten databases max.')
  print('Loading label databases to compare...')
  compare_dbs = [label_database.Database(dbfile, readonly=True)
                 for dbfile in FLAGS.databases_to_compare]

  print('Opening label database to modify...')
  with label_database.Database(FLAGS.label_database) as db:
      
    # Identify word images that different databases have labeled differently.
    print('Looking for ambiguous images (takes a bit)...')
    ambiguous_word_images = find_ambiguous_word_images(db, compare_dbs)

    # OK, go to town!
    ui_for_resolving_ambiguous_word_images(
            db, compare_dbs, FLAGS.screen_image_subdir, ambiguous_word_images)


#### ODD IMAGE IDENTIFICATION AND MARKING ####


def find_ambiguous_word_images(db, compare_dbs):
  """Identify ambiguous word images based on label differences.

  All label entries in databases in `compare_dbs` are compared, as well as
  checked against entries in the "ground truth" database `db`. If there are
  disagreements, the filename of the corresponding image is included in the
  returned list.

  Args:
    db: label database that this program (but not this function!) will modify.
    compare_dbs: set of additional label databases whose labels this function
        will compare.

  Returns:
    A list of filenames of ambiguous word images.
  """
  ambiguous_word_images = []

  for fn, _ in db.all_labels_with_counts_of_at_least(0):
    labels = set()
    label, count = db[fn]
    if label == 'XXXX' and count >= 2: continue
    for cdb in [db] + compare_dbs:
      label, count = cdb[fn]
      if count >= 2: labels.add(label)
    if len(labels) > 1: ambiguous_word_images.append(fn)

  return ambiguous_word_images


def ui_for_resolving_ambiguous_word_images(db, compare_dbs, screen_image_subdir,
                                           ambiguous_word_images):
  """A Sixel UI that allows the user to resolve ambiguous word images.

  The UI allows the user to select one of several actions (including supplying
  their own image label). When they do this, they must commit the action
  (space bar) or clear it (` key) before moving to another image or quitting.

  Args:
    db: label database that this program will modify.
    compare_dbs: additional databases supplying labels for the same images.
    screen_image_subdir: subdirectory for screen image files; in other words,
        the contents of the screen_image_subdir flag.
    ambiguous_word_images: word images known to be ambiguous (see
        `find_ambiguous_word_images`.
  """
  # Interface state:
  pos_images = 0     # Index of the current image.
  status = 'Ready!'  # Status message to print.
  action = None      # Action to commit to the database (None or a tuple).

  sys.stdout.write('\x1b[H\x1b[J')  # Clear screen

  # UI loop.
  while True:
    # Load word image and screen image.
    fn_word = ambiguous_word_images[pos_images]
    fn_screen = led.word_image_to_screen_image(fn_word, screen_image_subdir)
    image_word = wand.image.Image(filename=fn_word)
    image_screen = wand.image.Image(filename=fn_screen)
    # Scale up word image.
    image_word.resize(width=round(3 * image_word.width),
                      height=round(3 * image_word.height))

    # Collect labels for this word image.
    labels = ['    '] * 10
    for i, cdb in enumerate([db] + compare_dbs):
      label, count = cdb[fn_word]
      if count >= 2: labels[i] = label

    # Draw user interface.
    sys.stdout.write('\x1b[H')  # Back to top left.
    print('  \x1b[32m-=[ Distorted image resolution tool ]=-\x1b[0m')
    print()
    sys.stdout.buffer.write(image_screen.make_blob('sixel'))
    print()
    sys.stdout.buffer.write(image_word.make_blob('sixel'))
    print()
    print('\x1b[32m   image:\x1b[34m', pos_images + 1, '/',
          len(ambiguous_word_images), '\x1b[0m     ')
    print('\x1b[32m    file:\x1b[34m', fn_word, '\x1b[0m               ')
    print('\x1b[32m')
    print(' ', '     '.join(['\x1b[1m{})\x1b[0;32m {}'.format(i, labels[i])
                             for i in range(5)]))
    print(' ', '     '.join(['\x1b[1m{})\x1b[0;32m {}'.format(i, labels[i])
                             for i in range(5, 10)]))
    print('  \x1b[1mA)\x1b[0;32m prev   \x1b[1mD)\x1b[0;32m next '
          '  \x1b[1mM)\x1b[0;32m manual label '
          '  \x1b[1mX)\x1b[0;32m mark all XXXX')
    print('  \x1b[1mZ)\x1b[0;32m clear action '
          '  \x1b[1mSPACE)\x1b[0;32m commit action! '
          '  \x1b[1mR)\x1b[0;32m remark')
    print('  \x1b[1mQ)\x1b[0;32m quit          '
          '  \x1b[0K\x1b[33;1m', status)
    print('\x1b[0m')

    # Clear status line.
    status = ''

    # Helper: a string description of an action, as a question.
    def action_to_str():
      if action is None: return ''
      if action[0] == 'XXXX': return 'Mark all images as XXXX?'
      if action[0] == 'Set': return 'Set label to {}?'.format(action[1])
      return 'Do... {}?'.format(action)

    # Helper: apply an action.
    def apply_action():
      if action is None: return
      if action[0] == 'Set':
        db.force(fn_word, action[1], 2)
      elif action[0] == 'XXXX':
        for fn in led.screen_image_to_word_images(fn_screen, db):
          db.force(fn, 'XXXX', 2)

    # Get and handle user key input. This is *superb* code.
    ch = led.getch().upper()
    if ch == 'Q':
      print('Quitting...')
      return
    elif ch == 'A':
      if action is None:
        pos_images = max(0, pos_images - 1)
      else:
        status = 'Well? {}'.format(action_to_str())
    elif ch == 'D':
      if action is None:
        pos_images = min(pos_images + 1, len(ambiguous_word_images) - 1)
      else:
        status = 'Well? {}'.format(action_to_str())
    elif ch == '[':
      if action is None:
        for maybe_pos in range(pos_images-1, -1, -1):
          if db[ambiguous_word_images[maybe_pos]][1] < 2:
            pos_images = maybe_pos
            break
        else:
          status = 'No earlier image with no 0 label.'
      else:
        status = 'Well? {}'.format(action_to_str())
    elif ch == ']':
      if action is None:
        for maybe_pos in range(pos_images+1, len(ambiguous_word_images)):
          if db[ambiguous_word_images[maybe_pos]][1] < 2:
            pos_images = maybe_pos
            break
        else:
          status = 'No later image with no 0 label.'
      else:
        status = 'Well? {}'.format(action_to_str())
    elif ch in '0123456789':
      label = labels[ord(ch) - ord('0')]
      if label != '    ': action = ('Set', label)
      status = action_to_str()
    elif ch == 'X':
      action = ('XXXX',)
      status = action_to_str()
    elif ch == 'Z':
      action = None
    elif ch == ' ':
      apply_action()
      action = None
    elif ch == 'M':
      # Allow user to specify a manual label.
      sys.stdout.write('\x1b[1;35m  Label >:  \x1b[1;36m')
      sys.stdout.flush()
      label = [' '] * 4
      pos = 0
      while True:
        ch = led.getch()
        if ch in '\n\r': break
        elif ch in '\b\x7f':
          if pos > 0:
            pos -= 1
            sys.stdout.write('\b \b')
            label[pos] = ' '
        elif ch in '0123456789ABCDEF':
          if pos < 4:
            label[pos] = ch
            pos += 1
            sys.stdout.write(ch)
        sys.stdout.flush()
      sys.stdout.write('\x1b[0m\x1b[2K')
      if pos == 4: action = ('Set', ''.join(label))
      status = action_to_str()
    elif ch == 'R':
      # Allow user to type a message for video recordings.
      sys.stdout.write('\x1b[1;35m  Remark >:  \x1b[1;36m')
      sys.stdout.flush()
      while True:
        ch = led.getch()
        if ch in '\n\r':
          break
        elif ch in '\b\x7f':
          sys.stdout.write('\b \b')
        else:
          sys.stdout.write(ch)
        sys.stdout.flush()
      sys.stdout.write('\x1b[0m\x1b[2K')
      status = action_to_str()
    else:
      status = action_to_str()


#### MISCELLANEOUS ####


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)

