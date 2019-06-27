#!/bin/sh

# Licensing:
#
# This program and any supporting programs, software libraries, and
# documentation distributed alongside it are released into the public domain
# without any warranty. See the LICENSE file for details.

dd if=binary_APL_LROS_raw_undump.bin bs=6144 count=16 of=binary_APL_LROS.bin

dd if=binary_BCom_raw_undump.bin bs=1 count=6144 of=binary_BCom.bin  # 10
dd if=binary_BCom_raw_undump.bin bs=1 count=6144 skip=6144 oflag=append conv=notrunc of=binary_BCom.bin  # 11
dd if=binary_BCom_raw_undump.bin bs=1 count=6144 skip=20480 oflag=append conv=notrunc of=binary_BCom.bin  # 12
dd if=binary_BCom_raw_undump.bin bs=1 count=6144 skip=26624 oflag=append conv=notrunc of=binary_BCom.bin  # 13
dd if=binary_BCom_raw_undump.bin bs=1 count=6144 skip=40960 oflag=append conv=notrunc of=binary_BCom.bin  # 14
dd if=binary_BCom_raw_undump.bin bs=1 count=6144 skip=55296 oflag=append conv=notrunc of=binary_BCom.bin  # 15
dd if=binary_BCom_raw_undump.bin bs=1 count=6144 skip=69632 oflag=append conv=notrunc of=binary_BCom.bin  # 16
dd if=binary_BCom_raw_undump.bin bs=1 count=6144 skip=75776 oflag=append conv=notrunc of=binary_BCom.bin  # 17
dd if=binary_BCom_raw_undump.bin bs=1 count=6144 skip=90112 oflag=append conv=notrunc of=binary_BCom.bin  # 18
