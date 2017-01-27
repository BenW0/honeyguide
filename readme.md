# Honeyguide
Honeyguide is an application which inserts custom image stacks into a Creation Workshop CWS file.

For usage instructions and other information, see instructions.html

## Required packages
This code uses stock Python 2, but relies on the binaries of ImageMagick for image processing. By default, the code
is distributed with a portable copy of ImageMagick in the ./ImageMagick directory. Currently, the code is tested
and distributed against ImageMagick-7.0.3-4-portable-Q16-x64.

To build a Windows executable, the setup module can be used. It requires Py2EXE (py2exe.org)

## Change log
* 0.12
** Mask functionality
** Incorporates ImageMagick in the distributed version
** Installer for the py2exe result (using Inno Installer)
** Moved log and config files to %appdata% on Windows and ~/.Honeyguide on other platforms