#!/usr/bin/python3
"""Gather labels from multiple classification runs.

The classification file stores information in three sections: one listing the
label files used as input to this program, one listing the image files referred
to by those label files, and finally the inferred labels at each memory address.
A very short version of this file might look like this:

    ======== Label databases:
    0: path/to/a/label_file.csv
    1: path/to/another/label_file.csv
    ======== Images:
    0: ./images/set1/0000_0_0.png
    1: ./images/set1/0000_0_1.png
    2: ./images/set1/0000_0_2.png
    3: ./images/set1/0000_0_3.png
    4: ./images/set1/0000_0_4.png
      ...
    ======== Labels:
    1000: 12AB@0,0/0,16/0,32 12A8@1,0/1,16/1,32
    1001: 34CD@0,1/0,17 34C0@0,33/1,1/1,17 84CD@1,33
      ...

The format of the labels line is as follows:

    <hex address>: <label> <label> <label> ...

where the format of <label> is:

    <hex label>@<locator>/<locator>/...

where <locator> is a comma-separated pair of numbers. The first number indexes
into the list of label databases; the second indexes into the list of images.

Inputs to this program are image label databases. It's assumed that image
filenames will code the position of the hex word in the DCP1 on-screen memory
dump display as an underscore-separated pair of numbers just before the file
extension: the first number (in {0, 1}) lists the row; the second (in [0, 8])
lists the column. Memory addresses are derived from the two images that appear
in column 0.

Output is printed to standard output.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import collections
import sys

import label_database


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Gather labels from multiple classification runs.')

  flags.add_argument('ground_truth_database', type=str, help=(
      'A database of presumed ground-truth image labels, and perhaps more '
      'importantly, of ambiguous ("XXXX") images. These images will be '
      'excluded from the output. Other labels from this database will be '
      'treated like labels from any other input database. Will be opened '
      'read-only; will always be associated with index 0.'))

  flags.add_argument('image_substrings', type=str, help=(
      'Comma-separated list of path substrings. This program will only examine '
      'images in the label databases whose paths contain at least one of these '
      'substrings.'))

  flags.add_argument('label_databases', type=str, nargs='+', help=(
      'Databases of classifier-generated labels. Will be opened read-only.'))

  return flags


#### MAIN PROGRAM ####


def main(FLAGS):
  sys.stderr.write('Loading...\n')
  # Load ground-truth database.
  db_truth = label_database.Database(FLAGS.ground_truth_database, readonly=True)
  # Load other databases.
  # Nevermind, this uses up too much RAM. Guess we'll trade space for time.
  # dbs_other = tuple(label_database.Database(dbfile, readonly=True)
  #                   for dbfile in FLAGS.label_databases)
  # dbs_all = (db_truth,) + dbs_other


  sys.stderr.write('Preliminaries..')
  # Print out the databases we've loaded.
  print('======== Label databases:')
  print('0:', FLAGS.ground_truth_database)
  for i, dbfile in enumerate(FLAGS.label_databases, start=1):
    print('{}:'.format(i), dbfile)

  # Gather image filenames.
  image_filenames = set()
  filtering_substrings = FLAGS.image_substrings.split(',')
  #for db in dbs_all:  # too memory intensive!
  for dbfile in [FLAGS.ground_truth_database] + FLAGS.label_databases:
    # Load the database.
    if dbfile == FLAGS.ground_truth_database:
      db = db_truth
    else:
      db = label_database.Database(dbfile, readonly=True)
    sys.stderr.write('.')
    sys.stderr.flush()
    # Gather image filenames.
    for fn, _ in db.all_labels_with_counts_of_at_least(2):
      for substring in filtering_substrings:
        if substring in fn:
          image_filenames.add(fn)
          break
    # Release memory early.
    if db is not db_truth: del db
  image_filenames = collections.OrderedDict(
      (imfile, i) for i, imfile in enumerate(sorted(image_filenames)))
  print('======== Images:')
  for imfile, i in image_filenames.items():
    print('{}:'.format(i), imfile)

  # Isolate image filename stems; that is, everything prior to the 1_3.png part
  # at the end of the filename. We could do it the right way and parse the
  # filenames, but easier just to lop off the last seven characters.
  image_filename_stems = set()
  for imfile in image_filenames:
    image_filename_stems.add(imfile[:-7])

  # Filter out all stems where either of the leftmost columns has the label
  # 'XXXX' in the ground truth database.
  filtered_image_filename_stems = set()
  for stem in image_filename_stems:
    l1, c1 = db_truth['{}0_0.png'.format(stem)]
    l2, c2 = db_truth['{}1_0.png'.format(stem)]
    if c1 >= 2 and l1 == 'XXXX': continue
    if c2 >= 2 and l2 == 'XXXX': continue
    filtered_image_filename_stems.add(stem)
  image_filename_stems = filtered_image_filename_stems
  del filtered_image_filename_stems  # No longer used.

  sys.stderr.write('\n')


  sys.stderr.write('Assembly..')
  # We assemble the data structure described in the class docstring in this:
  # a mapping from memory addresses to (a mapping from labels to the <locator>
  # pairs described in the top docstring).
  result = collections.defaultdict(lambda: collections.defaultdict(list))

  #for stem in image_filename_stems:
    #for db_index, db in enumerate(dbs_all):  # too memory intensive!
  for db_index, dbfile in enumerate(
      [FLAGS.ground_truth_database] + FLAGS.label_databases):
    # 0. Load the database.
    if dbfile == FLAGS.ground_truth_database:
      db = db_truth
    else:
      db = label_database.Database(dbfile, readonly=True)
    sys.stderr.write('.');
    sys.stderr.flush()

    for stem in image_filename_stems:
      # 1. Collect memory addresses associated with this video frame by the
      #    current database. There should be a gap of 0x10 between both.
      l1, c1 = db['{}0_0.png'.format(stem)]
      l2, c2 = db['{}1_0.png'.format(stem)]
      if c1 < 2 or c2 < 2: continue  # Address words haven't been parsed.
      l1, l2 = int(l1, 16), int(l2, 16)
      if l2 - l1 != 0x10: continue   # Gap is not 0x10.

      # 2. For each memory address shown in this video frame, record labels
      #    associated with that address by the current database.
      def lookup_and_record_label(imfile, address):
        label, count = db[imfile]
        if count >= 2:  # Only if this image is parsed in this database.
          if_index = image_filenames[imfile]
          result['{:04X}'.format(address)][label].append((db_index, if_index))

      for i, pos in enumerate(
          ('0_1', '0_2', '0_3', '0_4', '0_5', '0_6', '0_7', '0_8')):
        imfile = '{}{}.png'.format(stem, pos)
        lookup_and_record_label(imfile, l1 + 2 * i)

      for i, pos in enumerate(
          ('1_1', '1_2', '1_3', '1_4', '1_5', '1_6', '1_7', '1_8')):
        imfile = '{}{}.png'.format(stem, pos)
        lookup_and_record_label(imfile, l2 + 2 * i)

    # 3. Help the garbage collector.
    if db is not db_truth: del db

  sys.stderr.write('\n')


  # Print out the result.
  print('======== Labels:')
  for address in sorted(result):
    line = '{}:'.format(address)
    for label, locators in sorted(result[address].items()):
      line += ' {}@{}'.format(label, '/'.join(
          '{},{}'.format(dbi, imi) for dbi, imi in sorted(locators)))
    print(line)


  # Just for the user's information, print out whether we have a contiguous
  # range of addresses.
  prev_address = int(min(result), 16)
  sys.stderr.write('INFO: first address {:04x}\n'.format(prev_address))
  for address in sorted(result):
    address = int(address, 0x10)
    if address - prev_address > 0x10:
      for gone_address in range(prev_address + 0x10, address, 0x10):
        sys.stderr.write('WARNING: no data for {:04X}\n'.format(gone_address))
    prev_address = address
  sys.stderr.write('INFO: last address {:04X}\n'.format(prev_address))

  # Just for the user's information, print out a histogram of the number of
  # addresses that have K labels associated with them.
  histogram = collections.defaultdict(lambda: 0)
  for labelings in result.values():
    histogram[len(labelings)] += 1
  sys.stderr.write(
      'INFO: {} addresses with unanimous labeling\n'.format(histogram[1]))
  for i in range(2, max(histogram) + 1):
    sys.stderr.write(
        'INFO: {} addresses with {} labels\n'.format(histogram[i], i))


  return result


#### MISCELLANEOUS ####


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
