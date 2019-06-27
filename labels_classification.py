#!/usr/bin/python3
"""Classify digits in word images.

This program uses the training data to train four classifiers: one for each
digit in a word image. It uses these classifiers to label the digits in all of
the word images.

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import collections
import numpy as np
import pathlib
import scipy as sp
import scipy.ndimage
import skimage
import skimage.io
import sklearn.ensemble
import sklearn.svm
import sklearn.neighbors
import sklearn.neural_network
import sys

import label_database


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Classify digits in entire word image label databases.')

  flags.add_argument('input_label_database', type=str,
                     help=('CSV file containing image paths, labels, and '
                           'the number of times a particular label was '
                           'supplied for an image. The CSV header should be '
                           '"Filename,Label,Count". Labels in this file will '
                           'serve as training data for the classifier.'))

  flags.add_argument('output_label_database', type=str,
                     help=('CSV file receiving image content labels from the '
                           'classifier. (Need not refer to an existing file.)'))

  flags.add_argument('--minimum-label-count', default=2, type=int,
                     help=('Only use image labels with at least this many '
                           'counts as training data.'))

  flags.add_argument('--max-0000', default=200, type=int,
                     help=('Load no more than this many "0000" images from the '
                           'labeled data. (There are many thousands and we '
                           'probably need fewer to train the classifier.)'))

  flags.add_argument('--train-data-fraction', default=0.8, type=float,
                     help=('Fraction of the labels in input_label_database '
                           'to use as training data. (The remainder will be '
                           'used as test data.)'))

  flags.add_argument('--mask-digits', default=False, type=bool,
                     help=('Mask individual digits in the images when they '
                           'are presented to or used to train classifiers for '
                           'those digits.'))

  return flags


#### MAIN PROGRAM ####


def main(FLAGS):
  if FLAGS.input_label_database == FLAGS.output_label_database:
    raise ValueError("Input and output label databases can't be the same file.")
  if FLAGS.minimum_label_count < 1: raise ValueError(
      'The value of --minimum-label-count must be greater than 2.')

  # Create new output label database if it doesn't exist yet.
  if not pathlib.Path(FLAGS.output_label_database).exists():
    with open(FLAGS.output_label_database, 'w') as f:
      f.write('"Filename","Label","Count"\n')

  # Open label databases.
  print('Opening input label database...')
  with label_database.Database(
      FLAGS.input_label_database, readonly=True) as db_in:
    print('Opening output label database...')
    with label_database.Database(
        FLAGS.output_label_database, save_backups=False) as db_out:

      # Load labeled images and per-digit labels.
      print('Loading labeled images; arranging test/train data...')
      all_data = load_data(db_in, FLAGS.minimum_label_count, FLAGS.max_0000)

      # Divide into training and test data.
      train_data, test_data = divide_data(all_data, FLAGS.train_data_fraction)
      print('   ...loaded', len(train_data), 'data points for training,',
            len(test_data), 'for testing.')

      # Train classifiers.
      classifiers = []
      for d in range(1, train_data.num_digits() + 1):
        images_train = train_data.images
        images_test = test_data.images
        if FLAGS.mask_digits:
          print('Preprocessing data for digit {}...'.format(d))
          images_train = mask_nth_digit_in_images(images_train, d - 1)
          images_test = mask_nth_digit_in_images(images_test, d - 1)

        print('Training classifier for digit {}...'.format(d))
        cfier = train_classifier(images_train, train_data[d])
        print('        Training set accuracy:',
              test_classifier(cfier, images_train, train_data[d]))
        print('            Test set accuracy:',
              test_classifier(cfier, images_test, test_data[d]))
        classifiers.append(cfier)

      # Now classify all of the data.
      print('Classifying all word images...')
      classify_everything(db_in, db_out, classifiers, FLAGS.mask_digits)

      # All done!
      print('Saving output label database...')


#### CLASSIFICATION ####


def train_classifier(inputs, labels):
  """Train a classifier from flattened image inputs to labels.

  Args:
    inputs: a Kx464 array of linearised input images.
    labels: a K-vector of integer labels.

  Returns:
    A scikit-learn classifier trained on the argument data.
  """
  # classifier = sklearn.svm.LinearSVC(class_weight='balanced')
  # classifier = sklearn.neighbors.KNeighborsClassifier()
  # classifier = sklearn.ensemble.GradientBoostingClassifier(verbose=100)
  # classifier = sklearn.ensemble.RandomForestClassifier(class_weight='balanced')
  classifier = sklearn.neural_network.MLPClassifier(
      hidden_layer_sizes=(50, 40, 30),
      # hidden_layer_sizes=(80, 60, 40),  # Probably too big.
      # hidden_layer_sizes=(40, 30, 20),  # Too small?
      # hidden_layer_sizes=(40, 20, 30),
      # hidden_layer_sizes=(60, 50, 40, 30),  # :-P
      # hidden_layer_sizes=(30, 20, 20, 30),  # 8-P
      # tol=1e-4,
      solver='lbfgs',
      tol=1e-6,
      max_iter=10000,
      # batch_size=500,
      batch_size=5000,
      verbose=True)
  classifier.fit(inputs, labels)
  return classifier


def test_classifier(classifier, inputs, labels):
  """Compute mean subset accuracy for a classifier.

  Args:
    classifier: A scikit-learn classifier.
    inputs: a Kx464 array of linearised input images.
    labels: a K-vector of integer labels.

  Returns:
    A scalar mean accuracy score.
  """
  return classifier.score(inputs, labels)


def classify_everything(db_in, db_out, classifiers, do_masking):
  """Apply classifiers to every word image.

  Args:
    db_in: Label database object listing all of the files in the dataset.
    db_out: Label database object receiving classifier-derived labels.
    classifiers: List of 16-class classifiers, one for each digit.
    do_masking: Whether to mask digits during classification.
  """
  label = 'XXXX'  # Early first value for progress indicator.
  all_images = [fn for fn, _ in db_in.all_labels_with_counts_of_at_least(0)]
  for i, fn in enumerate(all_images):
    # Display percentage progress indicator.
    sys.stdout.write('   {}% '.format(round(100 * i / len(all_images))))
    sys.stdout.write('{} '.format(label))  # This display should look cool :-)
    sys.stdout.flush()

    # Load the image and classify its digits. Commit the label.
    original_image = (
        skimage.color.rgb2gray(skimage.io.imread(fn)).astype(np.float32))
    if do_masking:
      original_masked = np.zeros_like(original_image)
      # A flattened view with a "batch dimension" for the classifier.
      masked = original_masked.ravel()[np.newaxis, ...]
      label = ''
      for i, cfier in enumerate(classifiers):
        mask_nth_digit_in_image(original_image, i, out=original_masked)
        label += '0123456789ABCDEF'[cfier.predict(masked)[0]]
    else:
      # A flattened view with a "batch dimension" for the classifier.
      image = original_image.ravel()[np.newaxis, ...]
      label = ''.join('0123456789ABCDEF'[cfier.predict(image)[0]]
                      for cfier in classifiers)
    db_out.force(fn, label, 2)

    # Clear away progress indicator.
    sys.stdout.write('\r\x1b[K')
    sys.stdout.flush()


#### IMAGE PROCESSING ####


def mask_nth_digit_in_image(image, n, out=None):
  """Return a copy of `image` with all but the `n`th digit masked."""
  # If we sum the image vertically, a plot of the column sums will present
  # four humps, each corresponding to a digit. This masking routine detects
  # the humps and masks the image so only the pixels contributing to the n'th
  # hump are visible.
  colsum = np.sum(image, axis=0)

  # # Now we need to find the least t such that image > t obtains four separate
  # # contiguous 'True' regions. We'll scan up from t = 0...
  # thresholded = colsum > 0                   # These two lines are just for
  # labels = sp.ndimage.label(thresholded)[0]  # memory allocation.

  # for t in range(int(max(colsum))):
  #   np.greater(colsum, t, out=thresholded)
  #   if sp.ndimage.label(thresholded, output=labels) == 4: break
  # else:
  #   raise RuntimeError('mask_nth_digit could not find four distinct digits '
  #                      'in an image.')

  # # We can now mask off the columns not containing the n'th digit.
  # if out is None:
  #   out = image.copy()
  # else:
  #   np.copyto(out, image)
  # out[:, labels != (n + 1)] = 0
  # return out

  colsum[:7] = 1000
  colsum[9:13] = 1000
  colsum[16:19] = 1000
  colsum[23:] = 1000
  # The columns containing the four digits are separated by the three smallest
  # minima of colsum not at the edges of the image.
  left_less = colsum[:-1] < colsum[1:]
  # True entries in this array are 4 pixels left of all local minima in colsum.
  # This 4-offset allows us to ignore pixels at the edges of the image.
  minima_mask = left_less[4:-3] & ~left_less[3:-4]
  # So these are the minima's indices:
  minima_inds = np.argwhere(minima_mask).ravel() + 4
  # Find which three indices are associated with the smallest minima.
  boundaries = np.sort(minima_inds[np.argsort(colsum[minima_inds])[:3]])

  # Perform the masking now.
  if out is None:
    out = image.copy()
  elif out is not image:
    np.copyto(out, image)

  if n > 0: out[:, :(boundaries[n-1])] = 0
  if n < 3: out[:, (boundaries[n]+1):] = 0
  return out


def mask_nth_digit_in_images(images, n):
  """Return a copy of `images` with all but the `n`th digit masked.

  Args:
    images: a Kx464 array of linearised input images.
    n: which digit to show through the mask.

  Returns:
    A version of `images` masked as described.
  """
  masked = images.copy()
  num_images = masked.shape[0]
  for i in range(num_images):
    sys.stdout.write('   {}% '.format(round(100 * i / num_images)))
    sys.stdout.flush()
    ith_image_reshaped = masked[i].reshape((16, 29))
    mask_nth_digit_in_image(ith_image_reshaped, n, out=ith_image_reshaped)
    sys.stdout.write('\r\x1b[K')
    sys.stdout.flush()

  return masked


#### DATA SHUFFLING ####


class Data(collections.namedtuple(
    'Data', ['images', 'labels_1', 'labels_2', 'labels_3', 'labels_4'])):
  """A data container for images and their per-digit labels."""

  def __len__(self):
    return len(self.images)

  def num_digits(self):
    return len(self._fields) - 1


def load_data(db, minimum_label_count, max_0000):
  """Load labeled images and create classifier training inputs.

  Args:
    db: Label database object.
    minimum_label_count: Do not use labels with a count less than this value.
    max_0000: Load no more than this many examples of "0000" labels.

  Returns:
    A 5-tuple with the following elements:
    [0]: A Kx464 array of linearised images, where K is the number of files
         in the database with a label count exceeding `minimum_label_count`.
    [1]: A K-vector of integer labels in [0, 15] for the first digit.
    [2]: A K-vector of integer labels in [0, 15] for the second digit.
    [3]: A K-vector of integer labels in [0, 15] for the third digit.
    [4]: A K-vector of integer labels in [0, 15] for the fourth digit.
  """
  images = []
  labels = []
  num_0000 = 0

  # Note filtering for minimum label count...
  worthy_labels = db.all_labels_with_counts_of_at_least(minimum_label_count)

  for i, (fn, label) in enumerate(worthy_labels):
    # Display percentage progress indicator.
    sys.stdout.write('   {}% '.format(round(100 * i / len(worthy_labels))))
    sys.stdout.flush()

    # Process label if it is of interest.
    if label != '0000' or num_0000 < max_0000:
      if all(d in '0123456789ABCDEF' for d in label):
        image = skimage.io.imread(fn)
        image = skimage.color.rgb2gray(image).astype(np.float32).ravel()
        images.append(image)
        labels.append(tuple('0123456789ABCDEF'.find(d) for d in label))
        if label == '0000': num_0000 += 1

    # Clear away progress indicator.
    sys.stdout.write('\r\x1b[K')
    sys.stdout.flush()

  return Data(*[np.stack(images, axis=0), *(np.int32(l) for l in zip(*labels))])


def divide_data(data, train_data_fraction):
  """Divide data randomly into training and test sets."""

  # Create shuffled dataset.
  inds = np.arange(len(data))
  np.random.shuffle(inds)
  data = Data(*[d[inds] for d in data])

  # Split it into training and test data.
  split = round(len(data) * train_data_fraction)
  return Data(*[d[:split] for d in data]), Data(*[d[split:] for d in data])


#### MISCELLANEOUS ####


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
