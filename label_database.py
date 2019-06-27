"""Library for our database of image labels.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import collections
import contextlib
import copy
import csv
import random
import shutil
import threading
import time


class Database(object):
  """Our database of image labels. Use as a context manager to ensure saving."""

  def __init__(self, filename, readonly=False, save_backups=True):
    """Open and load the image label database.

    Args:
      filename: the CSV file containing the database.
      readonly: whether to open the database in read-only mode.
      save_backups: whether to move old saved databases to backup locations
          (filename~<unix time>~) before saving new data.
    """
    self._filename = filename
    self._readonly = readonly
    self._save_backups = save_backups

    if readonly:
      self._lock_db = contextlib.suppress()  # Null context.
      self._lock_io = contextlib.suppress()
    else:
      self._lock_db = threading.RLock()  # For data in memory.
      self._lock_io = threading.RLock()  # For data on disk.
    # Maps filename to (label, count).
    self._database = collections.OrderedDict()
    # Maps counts to sets of filenames.
    self._by_count = collections.defaultdict(set)
    self.reload()

  def __enter__(self):
    return self

  def __exit__(self, *args):
    if not self._readonly: self.save()

  def __len__(self):
    return len(self._database)

  def __contains__(self, filename):
    with self._lock_db:
      return filename in self._database

  def __getitem__(self, filename):
    with self._lock_db:
      return self._database[filename]

  def num_labels_with_counts_of_at_least(self, n):
    """How many labels have been supplied at least `n` times?"""
    with self._lock_db:
      return sum(len(s) for count, s in self._by_count.items() if count >= n)

  def num_labels_with_counts_of(self, n):
    """How many labels have been supplied exactly `n` times?"""
    with self._lock_db:
      return sum(len(s) for count, s in self._by_count.items() if count == n)

  def random(self):
    """Retrieve an image filename, any filename."""
    with self._lock_db:
      return random.sample(self._database.keys(), 1)[0]

  def example_filename(self):
    """But if you just want an example filename, this is faster."""
    with self._lock_db:
      return next(iter(self._database))

  def random_label_with_count_of(self, n):
    """Retrieve a filename receiving the same label `n` times (or None)."""
    with self._lock_db:
      return (random.sample(self._by_count[n], 1)[0]
              if self._by_count[n] else None)

  def all_labels_with_counts_of(self, n):
    """Retrieve all labels with a count of `n` as (filename, label) tuples."""
    with self._lock_db:
      return [(fn, label) for fn, (label, count) in self._database.items()
              if count == n]

  def all_labels_with_counts_of_at_least(self, n):
    """Retrieve all labels with a count >= `n` as (filename, label) tuples."""
    with self._lock_db:
      return [(fn, label) for fn, (label, count) in self._database.items()
              if count >= n]

  def label(self, filename, label):
    """Add or confirm/disavow a label in the image label database.

    If the image has no label, then the image is given the label and a label
    count of 1. If the image has a label equal to label, then the image's
    label count is incremented. If the image has a label different to label,
    then the image's label count is decremented, but nothing is done with the
    new label.

    Args:
      filename: filename of image to (re)(un)label.
      label: proposed label for this image.

    Raises:
      RuntimeError: the database is open in read-only mode.
    """
    self._check_writable()

    with self._lock_db:
      if filename not in self._database: raise KeyError(
          '{} is not an image file known to the database stored in {}.'.format(
              filename, self._filename))

      old_label, count = self._database[filename]
      if count == 0 or label == old_label:
        self._database[filename] = (label, count + 1)
        self._by_count[count].remove(filename)
        self._by_count[count + 1].add(filename)
      else:
        if count == 1: old_label = '0000'  # Default label for count == 0.
        self._database[filename] = (old_label, count - 1)
        self._by_count[count].remove(filename)
        self._by_count[count - 1].add(filename)

  def force(self, filename, label, count):
    """Force a particular label and count in the image label database.

    List an image in the database as having a particular label and count.
    This method can also add new image filenames to the database.

    Args:
      filename: filename of image to force-label.
      label: label for this image.
      count: label count for the label.

    Raises:
      RuntimeError: the database is open in read-only mode.
    """
    self._check_writable()

    with self._lock_db:
      if filename in self._database:
        self._by_count[self._database[filename][1]].remove(filename)
      self._database[filename] = (label, count)
      self._by_count[count].add(filename)

  def reload(self):
    """Reload the image label database from the CSV file."""
    with self._lock_db, self._lock_io:
      with open(self._filename, newline='') as csvfile:
        reader = csv.reader(csvfile)
        fieldnames = next(reader)
        assert fieldnames == ['Filename', 'Label', 'Count'], (
            'Label database column names must be "Filename,Label,Count"')

        self._database = collections.OrderedDict()
        self._by_count = collections.defaultdict(set)
        for imgfile, label, count in reader:
          count = int(count)
          self._database[imgfile] = (label, count)
          self._by_count[count].add(imgfile)

  def save(self):
    """Save the image label database to the CSV file, making backups."""
    self._check_writable()

    with self._lock_db:  # Make local copy.
      db_copy = copy.deepcopy(self._database)

    with self._lock_io:
      # Move the current database file to a backup location.
      if self._save_backups:
        shutil.move(self._filename,
                    '{}~{}~'.format(self._filename, int(time.time())))

      # Write a new database file.
      with open(self._filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, dialect='unix')
        writer.writerow(['Filename', 'Label', 'Count'])
        for imgfile, (label, count) in self._database.items():
          writer.writerow([imgfile, label, count])

  def _check_writable(self):
    """Raise `RuntimeError` if the database is in read-only mode."""
    if self._readonly: raise RuntimeError(
        'The label database "{}" has been opened in read-only mode and will '
        'not be mutated or overwritten.'.format(self._filename))
