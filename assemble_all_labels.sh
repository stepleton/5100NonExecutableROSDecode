#!/bin/bash

# Licensing:
# 
# This program and any supporting programs, software libraries, and
# documentation distributed alongside it are released into the public domain
# without any warranty. See the LICENSE file for details.

TRUTH=database.csv

read -d '' ALL_FILES << EOF
database_classified_44.csv
database_classified_45.csv
database_classified_46.csv
database_classified_47.csv
database_classified_48.csv
database_classified_49.csv
database_classified_50.csv
database_classified_51.csv
database_classified_52.csv
database_classified_53.csv
database_classified_54.csv
database_classified_55.csv
database_classified_56.csv
database_classified_57.csv
database_classified_58.csv
database_classified_59.csv
database_classified_60.csv
database_classified_61.csv
database_classified_62.csv
database_classified_63.csv
database_classified_64.csv
database_classified_65.csv
database_classified_66.csv
database_classified_67.csv
database_classified_68.csv
database_classified_69.csv
database_classified_70.csv
database_classified_71.csv
EOF

read -d '' ALL_PARTS << EOF
./APL/APL_LROS_0000,./APL_ii/APL_LROS_ii_0000
./APL/APL_LROS_2000,./APL_ii/APL_LROS_ii_2000
./APL/APL_LROS_4000,./APL_ii/APL_LROS_ii_4000
./APL/APL_LROS_6000,./APL_ii/APL_LROS_ii_6000
./APL/APL_LROS_8000,./APL_ii/APL_LROS_ii_8000
./APL/APL_LROS_A000,./APL_ii/APL_LROS_ii_A000
./APL/APL_LROS_C000,./APL_ii/APL_LROS_ii_C000
./APL/APL_LROS_E000,./APL_ii/APL_LROS_ii_E000
./BCom/BCom_0000,./BCom_ii/BCom_ii_0000
./BCom/BCom_2000,./BCom_ii/BCom_ii_2000
./BCom/BCom_4000,./BCom_ii/BCom_ii_4000
./BCom/BCom_6000,./BCom_ii/BCom_ii_6000
./BCom/BCom_8000,./BCom_ii/BCom_ii_8000
./BCom/BCom_A000,./BCom_ii/BCom_ii_A000
./BCom/BCom_C000,./BCom_ii/BCom_ii_C000
./BCom/BCom_E000,./BCom_ii/BCom_ii_E000
EOF

for part in $ALL_PARTS; do
  title=$(echo $part | cut -d '/' -f 3 | sed s/,.$//)
  output="assembly_$title.txt"
  echo "Working on $output..."
  ./assemble_labels.py $TRUTH $part $ALL_FILES > $output
done
