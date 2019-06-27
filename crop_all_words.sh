#!/bin/sh

# Licensing:
#
# This program and any supporting programs, software libraries, and
# documentation distributed alongside it are released into the public domain
# without any warranty. See the LICENSE file for details.

for i in `find . -name 01_cropped`; do
  for input in $i/*.png; do
    out_prefix=`echo $input | sed 's/01_cropped/02_words/' | sed 's/\.png$/_/'`
    echo -n "Processing $input..."
    if ./crop_words.py -r 16 -c 29 --brighten "88;73;119" $input crop_list.csv $out_prefix; then
      echo " done."
    else
      echo " error!"
      echo $input >> errors.txt
    fi
  done
done
