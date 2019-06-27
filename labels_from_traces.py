#!/usr/bin/python3
"""Import labels for grayscale word images from aligned logic analyser traces.

This program solves a slightly complicated problem. Basically: we have images
of words in 2000-word portions of the non-executable ROS, and we have faulty
traces from a logic analyser that was listening to the data bus whilst the ROS
was being read into memory. The traces have hiccups and gaps in them, but there
are runs within the traces---contiguous strings of bytes---that are good. We
want to align these runs with the word images and use them to generate labeled
data. Once we have enough of that, we can train a classifier to recognise all
of the digits.

As an additional wrinkle, in addition to images of individual words, we also
have cropped screen images showing 32 bytes at a time. These are a bit more
pleasing to look at, so we're going to use those images for display, not the
individual word images.

Here's what happens. Using Sixel graphics in the terminal (so use a compatible
terminal emulator program like mlterm), the user sees one of the cropped screen
images and a 32-byte portion of the data from the trace, formatted to have the
same visual layout. The user can shift the data from the trace forward or
backward in 1- and 32-byte increments, and they can also advance forward and
backward through the cropped screen images. If the trace data matches the
screen image, they can assign the data to the words in the screen image.

With luck, paging through a number of images in this way will help label a lot
of data quickly.

Runs on Unix systems only for now. Sorry, windows...

Licensing:

This program and any supporting programs, software libraries, and documentation
distributed alongside it are released into the public domain without any
warranty. See the LICENSE file for details.
"""

import argparse
import csv
import os
import sys
import termios
import tty
import wand.image

import label_database


def _define_flags():
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description='Get word image labels from aligned logic analyser traces.')

  flags.add_argument('label_database', type=str,
                     help=('CSV file containing image paths, labels, and '
                           'the number of times a particular label was '
                           'supplied for an image. The CSV header should be '
                           '"Filename,Label,Count".'))

  flags.add_argument('traces', type=str,
                     help=('CSV file containing nanosecond timestamps and '
                           'bytes recorded by the logic analyser. There should '
                           'be no CSV header. The CSV file should be '
                           '"deduplicated", meaning that runs of identical '
                           'bytes should be pared down so only the first byte '
                           'in the run remains.'))

  flags.add_argument('screen_image_path', type=str,
                     help=('Path to cropped screen images containing 32 bytes '
                           'in hexadecimal. This path must match the paths in '
                           'the label database in all but the final directory, '
                           'and the filenames of images inside the path (not '
                           'counting the extension) must prefix the filenames '
                           'of word images in the database.'))

  flags.add_argument('--min-byte-duration', default=15, type=int,
                     help=('Ignore bytes in the traces file that persist no '
                           'longer than this value (in nanoseconds).'))

  flags.add_argument('--split-bytes-longer-than', default=900, type=int,
                     help=('Bytes in traces that are longer than this (in '
                           'nanoseconds) get split into multiple bytes'))

  flags.add_argument('--divide-long-bytes-by', default=500, type=int,
                     help=('When dividing long bytes in traces, aim to make '
                           'the split-up bytes about this long.'))

  flags.add_argument('--max-long-byte-splits', default=16, type=int,
                     help=('When splitting up long bytes in traces, split '
                           'single bytes no more than this many times.'))

  return flags


#### MAIN PROGRAM ####


def main(FLAGS):
  print('Loading trace data...')
  traces = read_traces_csv(FLAGS.traces)
  traces = deltaify_traces(traces)
  traces = filter_silly_bytes(traces, FLAGS.min_byte_duration)
  traces = expand_long_bytes(traces,
                             FLAGS.split_bytes_longer_than,
                             FLAGS.divide_long_bytes_by,
                             FLAGS.max_long_byte_splits)

  print('Listing screen image files...')
  images = sorted(os.path.join(FLAGS.screen_image_path, f)
                  for f in os.listdir(FLAGS.screen_image_path))

  print('Opening label database...')
  with label_database.Database(FLAGS.label_database) as db:
    # Determine how the paths of word images and screen images differ. Verify
    # that they differ in only the right way.
    wordfile = db.random()
    wf_parts = wordfile.split(os.sep)
    wf_innermost_dir = wf_parts[-2]

    screenfile = images[0]
    sf_parts = screenfile.split(os.sep)
    sf_root, sf_ext = os.path.splitext(sf_parts[-1])

    made_up_wordfile = os.sep.join(
        sf_parts[:-2] + [wf_innermost_dir, sf_root + '_1_1' + sf_ext])
    assert made_up_wordfile in db, (
        'Label database file paths and the screen image path appear to differ '
        'in more ways than the innermost directory name. Parts that should '
        'have been more common---labels: {}, images: {}. Giving up...'
        ''.format(wf_parts, sf_parts))

    # Start up the user interface.
    ui(db, traces, images, wf_innermost_dir)


def ui(db, traces, images, wf_innermost_dir):

  # This code is generally horrible, write-once stuff. Do not emulate!

  # Interface state:
  pos_traces = 0     # Current byte position in the traces.
  pos_images = 0     # Index of the current image.
  status = 'Ready!'  # Status message to print.
  search = []        # Last search query, as an array of char (so: mutable).

  all_trace_bytes = ''.join(b for d, b in traces)  # For searching.

  sys.stdout.write('\x1b[H\x1b[J')  # Clear screen

  # UI loop.
  while True:
    # Load image file.
    image = wand.image.Image(filename=images[pos_images])

    # Draw user interface.
    sys.stdout.write('\x1b[H')  # Back to top left.
    print('  \x1b[32m-=[ Trace alignment tool ]=-\x1b[0m')
    print()
    sys.stdout.buffer.write(image.make_blob('sixel'))
    print_trace_bytes(traces[pos_traces:pos_traces+32])
    print()
    print('\x1b[32mfirst byte:\x1b[34m', pos_traces, '\x1b[0m     ')
    print('\x1b[32m     image:\x1b[34m', images[pos_images], '\x1b[0m     ')
    print()
    print('\x1b[32m')
    print('  \x1b[1mA)\x1b[0;32m <--1-bytes  \x1b[1mD)\x1b[0;32m bytes-1-->   '
          '    \x1b[1mJ)\x1b[0;32m <--1-image  \x1b[1mL)\x1b[0;32m image-1-->')
    print('  \x1b[1mZ)\x1b[0;32m <-32-bytes  \x1b[1mC)\x1b[0;32m bytes-32->   '
          '    \x1b[1m?)\x1b[0;32m <---search  \x1b[1m/)\x1b[0;32m search--->')
    print()
    print('  \x1b[1mR)\x1b[0;32m remark '
          '  \x1b[1mQ)\x1b[0;32m quit '
          '  \x1b[1mSPACE)\x1b[0;32m commit     '
          '  \x1b[0K\x1b[33;1m', status)
    print('\x1b[0m')

    # Clear status line.
    status = ''

    # Get and handle user key input
    ch = getch().upper()
    if ch == 'Q':
      print('    \x1b[33;1mPlease wait, saving... \x1b[0m')
      return
    elif ch == 'A':
      pos_traces = max(0, pos_traces - 1)
    elif ch == 'D':
      pos_traces = min(pos_traces + 1, len(traces) - 32)
    elif ch == 'Z':
      pos_traces = max(0, pos_traces - 32)
    elif ch == 'C':
      pos_traces = min(pos_traces + 32, len(traces) - 32)
    elif ch == 'J':
      pos_images = max(0, pos_images - 1)
    elif ch == 'L':
      pos_images = min(pos_images + 1, len(images) - 1)
    elif ch == 'R':
      # Allow user to type a message for video recordings.
      sys.stdout.write('\x1b[1;35m  Remark >:  \x1b[1;36m')
      sys.stdout.flush()
      while True:
        ch = getch()
        if ch in '\n\r':
          break
        elif ch in '\b\x7f':
          sys.stdout.write('\b \b')
        else:
          sys.stdout.write(ch)
        sys.stdout.flush()
      sys.stdout.write('\x1b[0m\x1b[2K')
    elif ch == ' ':
      # Commit these bytes to the label database.
      sf_parts = images[pos_images].split(os.sep)
      sf_root, sf_ext = os.path.splitext(sf_parts[-1])
      wordstem = os.sep.join(sf_parts[:-2] + [wf_innermost_dir, sf_root])
      wordext = sf_ext
      for i, word_pos in enumerate([
          '_0_1', '_0_2', '_0_3', '_0_4', '_0_5', '_0_6', '_0_7', '_0_8',
          '_1_1', '_1_2', '_1_3', '_1_4', '_1_5', '_1_6', '_1_7', '_1_8']):
        wordfile = wordstem + word_pos + wordext
        label = traces[pos_traces + 2*i][1] + traces[pos_traces + 2*i + 1][1]
        db.label(wordfile, label)  # Label twice to confirm the label as a
        db.label(wordfile, label)  # "sure thing".
      status = 'Committed.'
    elif ch in '/?':
      # Forward or backward search. Which one to use?
      find_fn = (all_trace_bytes.find if ch == '/' else
                 all_trace_bytes.rfind)
      next_fn = ((lambda s: find_fn(s, 2*pos_traces + 2)) if ch == '/' else
                 (lambda s: find_fn(s, 0, max(0, 2*pos_traces - 1))))
      # Now obtain the search query.
      sys.stdout.write('\x1b[1;35m  Search >:  \x1b[1;36m')
      sys.stdout.write(''.join(search))
      sys.stdout.flush()
      while True:
        ch = getch()
        if ch in '\n\r':
          break
        elif ch in '\b\x7f' and search:
          sys.stdout.write('\b \b')
          search.pop()
        elif ch.upper() in '0123456789ABCDEF':
          sys.stdout.write(ch.upper())
          search.append(ch.upper())
        sys.stdout.flush()
      sys.stdout.write('\x1b[0m\x1b[2K')
      # Next, perform the search.
      if search:
        query = ''.join(search)
        for search_fn, success_str in [(next_fn, 'Found!'),
                                       (find_fn, 'Found after wrapping.')]:
          pos = search_fn(query)
          if pos != -1:
            # Convert nybble index to byte index, and don't allow a window that
            # extends beyond the end of the traces. Note that this introduces
            # a bug such that if the search query is in the final 32 bytes,
            # continuing to search forward won't wrap around to the start of
            # the traces. Oh well.
            pos_traces = min(pos // 2, len(traces) - 32)
            status = success_str
            break
        else:
          status = 'Not found.'
      else:
        status = 'Search cancelled.'


def print_trace_bytes(dtrace_snippet):
  """Print trace bytes in a way that resembles the 5100 hex dumper.

  Albeit without the addresses at the start of the line. This means 16 bytes
  per line, with blank lines in between, in pairs.

  Args:
    dtrace_snippet: trace entries to print.
  """
  for i, (_, b) in enumerate(dtrace_snippet):
    if i % 16 == 0:
      sys.stdout.write('        ')  # Indent bytes.
    sys.stdout.write(b)
    if (i+1) % 16 == 0:
      print('     \n')  # Double newline.
    elif (i+1) % 2 == 0:
      sys.stdout.write('  ')


#### LOADING TRACE DATA ####


def read_traces_csv(filename):
  """Read a .csv file containing deduplicated logic analyser traces.

  The file should contain two columns: nanosecond start time and byte value.
  The byte value should be assumed to persist on the bus until the start time
  in the next record.

  Args:
    filename: .csv file to read.

  Returns:
    A list of (start time, byte value) tuples.
  """
  traces = []
  with open(filename) as f:
    for timestamp, byte in csv.reader(f):
      traces.append((int(timestamp), byte))
  return traces


def deltaify_traces(traces, final_byte_duration=9999):
  """Convert absolute start times in traces to durations.

  Traces returned by `read_traces_csv` pair bytes with start times. This
  function computes how long each byte remains on the bus and replaces the
  start time with this value in its output. Note that the final duration can't
  be calculated and will be given the duration `final_byte_duration`.

  Args:
    traces: Traces to "deltaify" as described.
    final_byte_duration: Duration to assign to the final byte.

  Returns:
    "Deltaified" traces as described.
  """
  deltaified_traces = []
  for i in range(len(traces) - 1):
    dt = traces[i+1][0] - traces[i][0]
    deltaified_traces.append((dt, traces[i][1]))
  deltaified_traces.append((final_byte_duration, traces[-1][1]))
  return deltaified_traces


def filter_silly_bytes(dtraces, min_duration=15):
  """Remove bytes in traces that seem nonsensical.

  Some bytes that appear on the bus are spurious for various reasons, including
  brief glitches while the bus switches between bytes. This function collects
  various filtering steps to remove spurious bytes.

  (Will there ever be more than one? We'll see...)

  Args:
    dtraces: "Deltaified" traces (see `deltaify_traces`).
    min_duration: Filter bytes that persist on the bus for less time than this
        (in nanoseconds). Wikipedia says that the PALM clock was 1.9 MHz, so
        perhaps bytes that last only fractions of that that interval are not
        legitimate...

  Returns:
    "Filtered" traces.
  """
  # Filter bytes that don't last long enough.
  dtraces = [(d, b) for d, b in dtraces if d >= min_duration]

  return dtraces


def expand_long_bytes(dtraces, longer_than=900, divide_by=500, max_expand=16):
  """Turn long-lasting bytes into multiple bytes.

  Oh, it's too bad we don't have a clock signal. We just have to guess: is a
  $0D that lasts 1200ns a single $0D byte or several $0D bytes in a row? This
  function takes bytes that hang around for more than `longer_than` ns and
  splits them into N separate bytes of duration `d // N`, where
  
      d = round(L / divide_by)

  and `d` is the original duration. There is a minor adjustment on the last
  byte so that the sequence lasts just as long as the original byte (i.e. we
  add the remainder). BUT: this function will refuse to add more than
  `max_expand` bytes to the traces, so some data will be dropped in extreme
  cases.

  Well, here's hoping that this is better than nothing!

  Args:
    dtraces: "Deltaified" traces (see `deltaify_traces`).
    longer_than: As described above.
    divide_by: As described above.

  Returns:
    Traces with bytes expanded as described.
  """
  expanded_dtraces = []

  for d, b in dtraces:
    if d <= longer_than:
      expanded_dtraces.append((d, b))
    else:
      num_bytes = round(d / divide_by)
      new_d = d // num_bytes
      bytes_to_add = [(new_d, b)] * (num_bytes - 1)
      bytes_to_add.append((new_d + d % num_bytes, b))  # See doc. on last byte.
      expanded_dtraces.extend(bytes_to_add[:max_expand])

  return expanded_dtraces


#### MISCELLANEOUS ####


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
