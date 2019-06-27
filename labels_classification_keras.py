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
import math
import numpy as np
import os
import pathlib
import scipy as sp
import scipy.ndimage
import skimage
import skimage.io
import sys

for backend in ['theano', 'tensorflow']:
  os.environ['KERAS_BACKEND'] = backend
  try:
    import keras
    break
  except ModuleNotFoundError:
    pass
else:
  raise RuntimeError("Couldn't find a working backend for Keras.")
import keras.preprocessing.image

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
        cfier = train_classifier(images_train, train_data[d],
                                 images_test, test_data[d])
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


def train_classifier(inputs, labels, test_inputs, test_labels):
  """Train a classifier from flattened image inputs to labels.

  Args:
    inputs: a Kx29x16x1 array of input training images.
    labels: a K-vector of integer training labels.
    test_inputs: a Kx29x16x1 array of input testing images.
    test_labels: a K-vector of integer testing labels.

  Returns:
    A Keras model trained on the argument data.
  """
  # Derived from
  # https://github.com/keras-team/keras/blob/master/examples/cifar10_cnn.py
  batch_size = 48
  epochs = 130

  # Construct a model with a convnet.
  classifier = keras.models.Sequential()
  classifier.add(keras.layers.Conv2D(filters=16, kernel_size=(3, 3),
                                     padding='same',
                                     input_shape=inputs.shape[1:]))
  classifier.add(keras.layers.Activation('relu'))
  # # classifier.add(keras.layers.Conv2D(filters=16, kernel_size=(3, 3)))
  # # classifier.add(keras.layers.Activation('relu'))
  classifier.add(keras.layers.MaxPooling2D(pool_size=(2, 2)))
  # classifier.add(keras.layers.Dropout(0.25))

  # classifier.add(keras.layers.Conv2D(filters=16, kernel_size=(3, 3)))
  # classifier.add(keras.layers.Activation('relu'))
  # classifier.add(keras.layers.MaxPooling2D(pool_size=(2, 2)))
  # classifier.add(keras.layers.Dropout(0.25))

  classifier.add(keras.layers.Flatten())
  # classifier.add(keras.layers.Dense(256))
  classifier.add(keras.layers.Dense(48))
  classifier.add(keras.layers.Activation('relu'))
  # classifier.add(keras.layers.Dense(32))
  # classifier.add(keras.layers.Dense(28))
  classifier.add(keras.layers.Dense(38))
  classifier.add(keras.layers.Activation('relu'))
  classifier.add(keras.layers.Dropout(0.3333))
  classifier.add(keras.layers.Dense(16))
  classifier.add(keras.layers.Activation('softmax'))

  # Our optimiser, decaying the learning rate from 0.001 to 0.0001.
  update_steps = epochs * (inputs.shape[0] / batch_size)
  optimiser = keras.optimizers.Adam(
      lr=0.001,
      decay=(1.0 - math.exp(math.log(0.1)/update_steps)),
  )

  # Compile the model.
  classifier.compile(loss='sparse_categorical_crossentropy',
                     optimizer=optimiser,
                     metrics=['accuracy'])

  # Prepare data augmentation.
  data_generator = keras.preprocessing.image.ImageDataGenerator(
      featurewise_center=False,             # set input mean to 0 over dataset
      samplewise_center=False,              # set each sample mean to 0
      featurewise_std_normalization=False,  # divide inputs by std of dataset
      samplewise_std_normalization=False,   # divide each input by its std
      zca_whitening=False,                  # apply ZCA whitening
      zca_epsilon=1e-06,                    # epsilon for ZCA whitening
      rotation_range=0.05,                  # randomly rotate (-this, this) degs
      # randomly shift images horizontally (fraction of total width)
      width_shift_range=0.05,
      # randomly shift images vertically (fraction of total height)
      height_shift_range=0.05,
      shear_range=0.05,                     # set range for random shear
      zoom_range=0.05,                      # set range for random zoom
      channel_shift_range=0.,               # set range for channel shifts
      # set mode for filling points outside the input boundaries
      fill_mode='nearest',
      cval=0.,                              # value for fill_mode = "constant"
      horizontal_flip=False,                # randomly flip images
      vertical_flip=False,                  # randomly flip images
      # set rescaling factor (applied before any other transformation)
      rescale=None,
      # set function that will be applied on each input
      preprocessing_function=None,
      # image data format, either "channels_first" or "channels_last"
      data_format='channels_last',
  )
  data_generator.fit(inputs)

  # Train the classifier!
  classifier.fit(
      x=inputs, y=labels,
      batch_size=batch_size,
      epochs=epochs,
      validation_data=(test_inputs, test_labels),
      verbose=2)

  # classifier.fit_generator(
  #     data_generator.flow(inputs, labels, batch_size=batch_size),
  #     epochs=epochs,
  #     steps_per_epoch=math.ceil(inputs.shape[0] / batch_size),
  #     validation_data=(test_inputs, test_labels),
  #     verbose=2,
  #     workers=4)

  return classifier


def test_classifier(classifier, inputs, labels):
  """Compute mean subset accuracy for a classifier.

  Args:
    classifier: A Keras model.
    inputs: a Kx464 array of linearised input images.
    labels: a K-vector of integer labels.

  Returns:
    A scalar mean accuracy score.
  """
  return classifier.evaluate(inputs, labels)[1]


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
    original_image = skimage.io.imread(fn)
    original_image = (
        skimage.color.rgb2gray(original_image).astype(np.float32) / 255.0)
    original_image = original_image[..., np.newaxis]  # One colour channel.
    if do_masking:
      original_masked = np.zeros_like(original_image)
      # A view with a "batch dimension" for the classifier.
      masked = original_masked[np.newaxis, ...]
      label = ''
      for i, cfier in enumerate(classifiers):
        mask_nth_digit_in_image(original_image, i, out=original_masked)
        label += '0123456789ABCDEF'[np.argmax(cfier.predict(masked)[0])]
    else:
      # A view with a "batch dimension" for the classifier.
      image = original_image[np.newaxis, ...]
      label = ''.join('0123456789ABCDEF'[np.argmax(cfier.predict(image)[0])]
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
  colsum = np.sum(image, axis=0).ravel()

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

  # These columns are not allowed to have image boundaries in them.
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

  if n > 0: out[:, :(boundaries[n-1]), ...] = 0
  if n < 3: out[:, (boundaries[n]+1):, ...] = 0
  return out


def mask_nth_digit_in_images(images, n):
  """Return a copy of `images` with all but the `n`th digit masked.

  Args:
    images: a Kx16x29x1 array of input images.
    n: which digit to show through the mask.

  Returns:
    A version of `images` masked as described.
  """
  masked = images.copy()
  num_images = masked.shape[0]
  for i in range(num_images):
    sys.stdout.write('   {}% '.format(round(100 * i / num_images)))
    sys.stdout.flush()
    mask_nth_digit_in_image(masked[i], n, out=masked[i])
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
    [0]: A Kx16x29x1 array of images, where K is the number of files in the
         database with a label count exceeding `minimum_label_count`.
    [1]: A Kx1 array of integer labels in [0, 15] for the first digit.
    [2]: A Kx1 array of integer labels in [0, 15] for the second digit.
    [3]: A Kx1 array of integer labels in [0, 15] for the third digit.
    [4]: A Kx1 array of integer labels in [0, 15] for the fourth digit.
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
        image = skimage.color.rgb2gray(image).astype(np.float32) / 255.0
        image = image[..., np.newaxis]  # One colour channel.
        images.append(image)
        labels.append(tuple('0123456789ABCDEF'.find(d) for d in label))
        if label == '0000': num_0000 += 1

    # Clear away progress indicator.
    sys.stdout.write('\r\x1b[K')
    sys.stdout.flush()

  return Data(*[
      np.stack(images, axis=0),
      *(np.int64(l)[:, np.newaxis] for l in zip(*labels))])


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
