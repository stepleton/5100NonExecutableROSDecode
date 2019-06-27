#!/usr/bin/python3
"""Identify differences in label databases.

Opens two label databases in read-only mode and shows which records differ.
It's possible to threshold on a minimum label count to ignore unlabeled
images in either database.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import sys

import label_database


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Identify label differences in two image label databases.')

  flags.add_argument('label_database_1', type=str,
                     help=('CSV file containing image paths, labels, and '
                           'the number of times a particular label was '
                           'supplied for an image. The CSV header should be '
                           '"Filename,Label,Count". '))

  flags.add_argument('label_database_2', type=str,
                     help=('CSV file containing image paths, labels, and '
                           'the number of times a particular label was '
                           'supplied for an image. The CSV header should be '
                           '"Filename,Label,Count". '))

  flags.add_argument('--minimum-label-count', default=2, type=int,
                     help=('Only use image labels with at least this many '
                           'counts as training data.'))

  flags.add_argument('--skip-XXXX', default=True, type=bool,
                     help='Ignore "XXXX" entries in either database.')

  flags.add_argument('--skip-XXXX-from', type=str,
                     help=('CSV label database. Files with "XXXX" entries in '
                           'this database will be ignored when comparing the '
                           'other two databases.'))

  return flags


def main(FLAGS):
  # Load the collection of filenames whose labels we ignore.
  ignorables = set()
  if FLAGS.skip_XXXX_from:
    sys.stderr.write('Opening {}...\n'.format(FLAGS.skip_XXXX_from))
    with label_database.Database(FLAGS.skip_XXXX_from, readonly=True) as db:
      db_all_labels = db.all_labels_with_counts_of_at_least(0)
      ignorables.update(fn for fn, label in db_all_labels if label =='XXXX')

  # Open label databases.
  sys.stderr.write('Opening {}...\n'.format(FLAGS.label_database_1))
  with label_database.Database(FLAGS.label_database_1, readonly=True) as db1:
    sys.stderr.write('Opening {}...\n'.format(FLAGS.label_database_2))
    with label_database.Database(FLAGS.label_database_2, readonly=True) as db2:
      # Print differences.
      db1_all_labels = db1.all_labels_with_counts_of_at_least(
           FLAGS.minimum_label_count)
      for fn, label1 in db1_all_labels:
        label2, count2 = db2[fn]
        if count2 < FLAGS.minimum_label_count: continue
        if FLAGS.skip_XXXX and 'XXXX' in [label1, label2]: continue
        if label1 == label2: continue
        if fn in ignorables: continue
        print('{}   {} <> {}'.format(fn, label1, label2))


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
