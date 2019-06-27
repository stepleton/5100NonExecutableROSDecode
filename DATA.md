# About data recovered from the IBM 5100 non-executable ROS

![A visualisation of the IBM 5100 non-executable ROS](non_executable_ros.png)  
_A visualisation of all the data in the IBM 5100's non-executable ROS. Slight
differences in texture identify portions filled with System/3 (top) and
System/360 (middle and bottom) machine code. Some native IBM 5100 code is also
present._

| :warning: Content warning :warning: |
|:-----------------------------------:|
|               BORING                |

This document provides altogether too much detail about the non-executable ROS
data recovered from an [IBM 5100 portable computer](
https://en.wikipedia.org/wiki/IBM_5100) with APL and BASIC language options
installed. Skip ahead to the download link at [Getting the data](
#getting-the-data) if you wish.

## Background

The IBM 5100 portable computer came with some of its built-in programs stored
in a read-only memory called the "non-executable ROS". (ROS = "read-only
storage".) In contrast with the "executable ROS", which supplies instructions
to the 5100's processor directly, the non-executable ROS is accessed using
sequential I/O operations, a bit like a tape.

Most notably, the non-executable ROS holds the interactive interpreters for the
APL and BASIC programming languages. These are not "native" 5100 programs but
were expressed instead in System/370 mainframe and System/3 minicomputer
machine code respectively. The 5100 runs emulator programs for those computers
in order to host the interpreters, so perhaps it's just as well that the
non-executable ROS is non-executable.

(A project to recover the IBM 5100 executable ROS is described
[here](https://github.com/stepleton/5100ExecutableROSDecode).)

## Recovery into RAM

Loosely, the non-executable ROS on the 5100 is organised into two "banks": one
for some common utility code and the BASIC interpreter, the other for the APL
interpreter. The process I used to recover the ROS data involved reading
portions of each bank into the 5100's RAM (or RWS = "read/write storage" in
IBM-speak), then transferring the data from there into a modern computer using
[an elaborate procedure described in a separate write-up](WRITEUP.md).

When the 5100 processor wants to read data from one of the banks, it uses an
I/O "control" instruction to choose which one, then two "put" instructions to
select a 16-bit initial reading address. (Note: this address is a _word_
address; multiply by two to get a byte address.) Subsequent I/O "get"
instructions stream individual bytes from the ROS in sequence, starting from
the selected address and counting upward, perhaps akin to a C
[stdio](https://en.wikipedia.org/wiki/C_file_input/output) stream or an
iterator in Python. The "next byte" address remains internal to the
non-executable ROS mechanism, although this position can be queried with other
I/O instructions.

Christian Corti's superb technical webpage ([German](
http://computermuseum.informatik.uni-stuttgart.de/dev/ibm_5110/technik/5110.html),
[English](http://computermuseum.informatik.uni-stuttgart.de/dev/ibm_5110/technik/en/index.html))
about the successor system to the 5100, the IBM 5110, lists a machine code
[program](
http://computermuseum.informatik.uni-stuttgart.de/dev/ibm_5110/technik/en/rosread.html)
for loading non-executable ROS data into the 5110's RAM. This program is short
enough to type into the computer by hand using the built-in "DCP" diagnostic
monitor facility (see [archived IBM 5100 maintenance documentation](
http://bitsavers.informatik.uni-stuttgart.de/pdf/ibm/5100/) for details on
DCP). As written, the program freezes my 5100 (triggering a "PROCESS CHECK"
fault, requiring a reset), but a modified version that gives a little more time
for the ROS to work succeeds:
```
; This is a modified version of a program created by Christian Corti, who
; retains its copyright. The original program can be found here:
; http://computermuseum.informatik.uni-stuttgart.de/dev/ibm_5110/technik/en/rosread.html
; Modifications:
;   - 0B14: changing $4000 to $2000 to accommodate my 5100's smaller RWS
;   - 0B1A,0B1C,0B20,0B22: extra NOPs to give the executable ROS extra time
;   - 0B30: change jump address to accommodate extra NOPs

		Start:
0B00 1104       	CTRL    1, #$04         ; select APL ROS
0B02 D301 000B  	LWI     R3, #$000B      ; address of low-byte of R5
0B06 8500       	LBI     R5, #0          ; source ROS address ...
0B08 4138       	PUTB    1, (R3)         ; ... high-byte
0B0A 8500       	LBI     R5, #0
0B0C 4138       	PUTB    1, (R3)         ; ... low-byte
0B0E 0004		NOP
0B10 D701 1000		LWI     R7, #$1000      ; destination RWS address
0B14 D801 2000		LWI     R8, #$2000      ; word count

		_loop:
0B18 011E		GETB    R1, 1           ; get high-byte
0B1A 0004		NOP
0B1C 0004		NOP
0B1E 016E		GETB    R6, 1           ; get low-byte
0B20 0004		NOP
0B22 0004		NOP
0B24 061D		MLH     R6, R1          ; make one word
0B26 5671		MOVE    (R7)+, R6       ; write to RWS
0B28 F800		SUB     R8, #1          ; decrement word count
0B2A 018C		MHL     R1, R8
0B2C 0186		OR      R1, R8
0B2E C103		SZ      R1              ; zero?
0B30 F019		BRA     _loop           ; no

0B32 0000		HALT
```
By changing the low-order byte at 0B06 through $00, $20, $40... and running
this program, 16KiB portions of the APL ROS starting from location $0000,
$4000, $8000... are loaded into the RAM at location $1000. Changing the
low-order byte of 0B00 from $04 to $08 reads the BASIC/Common ROS instead of
the the APL ROS.

Reassembling the data fragments copied into RAM by this procedure yielded the
recovered non-executable ROS data linked below.

## Getting the data

Download: [non_executable_ros.tar.gz](
http://stepleton.com/non_executable_ros.tar.gz). Contents:
```
-rw-rw-r-- tom/tom       98304 2019-04-02 01:25 binary_APL_LROS.bin
-rw-rw-r-- tom/tom       55296 2019-04-02 01:25 binary_BCom.bin
```

The first file is the 96KiB APL non-executable ROS; the second is the 54KiB
BASIC/Common non-executable ROS.

A more permanent, curated hosting location for the data would be desirable.

## Extra data? Jumbled data?

The recovery procedure described above gave 128KiB of "raw" data for both the
APL and BASIC/Common non-executable ROS "banks", covering the non-executable
ROS's entire 16-bit address space (again, non-executable ROS addresses refer to
16-bit words, not 8-bit bytes). All the excess in comparison to the recovered
data above, along with the peculiar arrangements of the non-executable ROS
contents within the raw data below, is likey due to the way the ROS reader
program interacted with the hardware implementation of the non-executable ROS,
not to the way the data are actually organised there. It's even possible that
different reading procedures (e.g. reading 8KiB at a time instead of 16KiB)
would retrieve different arrangements of data.

I'm not certain what the reasons for or causes of these effects might be, but
since some people might wish to use the recovered data to make emulator
software, or to make replacement ROS circuits for their own 5100s, I'm
reporting the following observations in case they might come in handy for
building accurate reproductions.

Both non-executable ROS "banks" organise data into $1800-byte segments
identified by two-digit hex numbers (these are the numbers shown briefly on the
5100's display during phase I of the "bring up diagnostic"---the power-on
self-test). The APL non-executable ROS has segments 20 through 2F, and the
BASIC/Common non-executable ROS has segments 10 through 18. These identifiers
will be useful for depicting the memory composition of the raw recovered data.

For the APL ROS, the first 96KiB read were the data in the file
`binary_APL_LROS.bin`. 26KiB of zeros followed, then a repetition of the last
6KiB of the first 92KiB. In tabular form:

  Data region   |  Contents
:--------------:| ----------
`$00000-$017ff` | Segment 20
`$01800-$02fff` | Segment 21
`$03000-$047ff` | Segment 22
`$04800-$05fff` | Segment 23
`$06000-$077ff` | Segment 24
`$07800-$08fff` | Segment 25
`$09000-$0a7ff` | Segment 26
`$0a800-$0bfff` | Segment 27
`$0c000-$0d7ff` | Segment 28
`$0d800-$0efff` | Segment 29
`$0f000-$107ff` | Segment 2A
`$10800-$11fff` | Segment 2B
`$12000-$137ff` | Segment 2C
`$13800-$14fff` | Segment 2D
`$15000-$167ff` | Segment 2E
`$16800-$17fff` | Segment 2F
`$18000-$1e7ff` | *zeros*
`$1e800-$1ffff` | Segment 2F, again

For the BASIC/Common non-executable ROS, the organisation of the raw data was
more complicated:

  Data region   |  Contents
:--------------:| ----------
`$00000-$017ff` | Segment 10
`$01800-$02fff` | Segment 11
`$03000-$03fff` | First $1000 bytes of Segment 12
`$04000-$04fff` | Last $1000 bytes of Segment 11
`$05000-$067ff` | Segment 12
`$06800-$07fff` | Segment 13
`$08000-$087ff` | Last $800 bytes of Segment 12
`$08800-$09fff` | Segment 13, again
`$0a000-$0b7ff` | Segment 14
`$0b800-$0bfff` | First $800 bytes of Segment 15
`$0c000-$0d7ff` | Segment 14, again
`$0d800-$0efff` | Segment 15
`$0f000-$0ffff` | First $1000 bytes of Segment 16
`$10000-$10fff` | Last $1000 bytes of Segment 15
`$11000-$127ff` | Segment 16
`$12800-$13fff` | Segment 17
`$14000-$147ff` | Last $800 bytes of Segment 16
`$14800-$15fff` | Segment 17, again
`$16000-$177ff` | Segment 18
`$17800-$17fff` | *zeros*
`$18000-$197ff` | Segment 18, again
`$19800-$1b7ff` | *zeros*
`$1b800-$1bfff` | First $800 bytes of Segment 15
`$1c000-$1d7ff` | *zeros*
`$1d800-$1dfff` | First $800 bytes of Segment 15
`$1e000-$1f7ff` | Segment 10, except the first byte is 0
`$1f800-$1ffff` | First $800 bytes of Segment 11

A clever hardware engineer might be able to identify patterns in these tables
that hint at the way addressing works in the non-executable ROS hardware.

Regardless of the layout of the raw data, it's clear that the segments are
meant to be arranged in order in the non-executable ROS (the 5100's "bring up
diagnostic" depends on it, for a start). The binary files linked above were
made by recreating this arrangement from the raw data.

## Acknowledgements

This project would not have been possible without 

- Christian Corti's excellent IBM 5110 technical webpage ([German](
http://computermuseum.informatik.uni-stuttgart.de/dev/ibm_5110/technik/5110.html),
[English](http://computermuseum.informatik.uni-stuttgart.de/dev/ibm_5110/technik/en/index.html))
as well as helpful remarks from Christian over email.
- The source code for Christian's IBM 5110 emulator (available at the same link, or [try it in your web browser](
http://members.aon.at/nkehrer/ibm_5110/emu5110.html)), which helpfully
clarified what certain IBM 5100/5110 instructions really did.
- [bitsavers.org](http://www.bitsavers.org/), for its archived [IBM 5100](
http://bitsavers.informatik.uni-stuttgart.de/pdf/ibm/5100/) and [IBM 5110](
http://bitsavers.informatik.uni-stuttgart.de/pdf/ibm/5110/) technical
documentation.
- Andrew M. for technical advice.

## Who, where, when

Tom Stepleton, London, 2019-04-04
