#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:     Modifies CreationWorkshop CWS files to contain your own image
#                 stack data.
#
# Author:      Ben
#
# Dependencies: This code requires imagemagick to be installed in your system path.
#
# Created:     06/02/2015
# 
# License: MIT License:
#
#    Copyright (c) 2015 Ben Weiss, University of Washington
#
#
#    Permission is hereby granted, free of charge, to any person obtaining a 
#    copy of this software and associated documentation files (the "Software"), 
#    to deal in the Software without restriction, including without limitation 
#    the rights to use, copy, modify, merge, publish, distribute, sublicense, 
#    and/or sell copies of the Software, and to permit persons to whom the 
#    Software is furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included 
#    in all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
#    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
#    DEALINGS IN THE SOFTWARE.
#
#-------------------------------------------------------------------------------
import ConfigParser

import zipfile
import os
import glob
import subprocess
import re
import tempfile
import shutil
import threading
import Queue
import difflib

on_posix = 'posix' in os.name

# regular expressions we'll need:
re_match_path = re.compile(".*[\\\\/]+(?!.*[\\\\/])")
re_match_last_number = re.compile(r"([0-9]+)(?!.*[0-9])")

# Find a folder where we can put settings files and logs on whatever platform we find ourselves on. Thanks to
# http://stackoverflow.com/questions/21761982/creating-a-folder-in-the-appdata-roaming-directory-python
try:
    settings_path = os.path.join(os.environ['APPDATA'], "Honeyguide")
except:
    # on some kind of *nix
    settings_path = os.path.join(os.path.expanduser('~'), ".Honeyguide")
if not os.path.exists(settings_path):
    os.makedirs(settings_path)


class Honeyguide:

    def __init__(self, logfile=None):
        # Status variables used for communicating with the host.
        self.quiet = False
        self.imagemagick_cmd = 'magick'
        self.negate = False
        self.threshold = False
        self.threshold_val = 0
        self.repeat_first = False
        self.logfile = logfile
        self.use_mask = False
        self.mask_image = ''
        
        # background processing variables
        self._thread = None
        self._messages = Queue.Queue()
        self._done = False
        self._success = False
        self._message_final = ""
        self._percent = 0.
        self._cancel = False

    @staticmethod
    def template_check(template_cws):
        """Checks whether a template CWS contains image slices we can use in Honeyguide.
        Best to do this in a background thread. Returns a tuple (success, message, sliceCount)
        where Success is a boolean, Message is a string to tell the user, and SliceCount is the
        number of slices found in the cws file."""

        # Check -- is the cws file a real file?
        if not os.path.exists(template_cws):
            return False, "Please select a template CWS file.", 0
        if not zipfile.is_zipfile(template_cws):
            return False, "Not a valid CWS file.", 0

        # Check the contents on the zip file manifest for images.
        try:
            zf = zipfile.ZipFile(template_cws, "r")
            files = []
            for fl in zf.filelist:
                if ".png" == fl.orig_filename[-4:].lower():
                    files.append(fl.orig_filename)
            zf.close()
        except:
            try:
                zf.close()
            except:
                pass
            return False, "Error opening CWS file.", 0

        if len(files) > 0:
            return True, "CWS file has %i slices" % len(files), len(files)
        else:
            return False, "CWS has no embedded slices!", 0

    @staticmethod
    def imstack_check(input_slice):
        """Checks whether an image stack is valid, and returns (valid, message, image_count) where
        valid is a boolean, True if the image stack is valid and False otherwise,
        message is a message to give to your user, and
        image_count is the number of successive images found in the same folder."""

        # check that the image file exists
        if not os.path.exists(input_slice):
            return False, "Please select your first image slice.", 0

        # figure out how long the numbers are (by testing length of result on first slice)
        result = re_match_last_number.search(input_slice)
        if result is None:
            return False, "Couldn't find a number in your image filename", 1
        slice_numpad = result.span()[1] - result.span()[0]
        slice_id = int(result.group())

        count = Honeyguide._count_slice_images(input_slice, slice_numpad, slice_id)

        return True, "Found %i slice images." % count, count

    @staticmethod
    def output_check(output_fname):
        """Checks that the output filename exists in a valid folder. Returns True if we think we can use this."""
        # Extract the path from the filename, if present
        path = re_match_path.match(output_fname)
        if path is None:
            # local file; this is fine.
            return True

        return os.path.exists(path.group())

    @staticmethod
    def mask_check(input_slice):
        """Checks whether an image is a valid mask, and returns (valid, message) where
        valid is a boolean, True if the image stack is valid and False otherwise,
        message is a message to give to your user, and
        image_count is the number of successive images found in the same folder."""

        # check that the image file exists
        if not os.path.exists(input_slice):
            return False, "File doesn't exist"

        return True, "OK"

    def do_honeyguide_background(self, template_cws, input_slice, output_cws):
        """Launches the honeyguide stack replacement process in a background thread. For arguments, see the following
        declaration. This just does that in background. Returns success if the job started.

        To check on output, use status_check() and status_message()"""
        # build args
        args = (template_cws, input_slice, output_cws)
        try:
            self._done = False
            # create the thread
            self._thread = threading.Thread(target=self.do_honeyguide, args=args)
            # set to daemon - kill the thread if the app quits
            self._thread.daemon = True
            # run!
            self._thread.start()
        except threading.ThreadError:
            self._done = True
            return False
        return True

    def do_honeyguide(self, template_cws, input_slice, output_cws):
        """Does the Honeyguide operation, inserting custom slices into a template CWS file.
        Options:
          * template_cws - CWS file to use as a template
          * input_slice - first image in the stack of new images to insert (except see erpeat_first, below)
          * output_cws - filename of CWS file to output results to.
        The following options are now class members:
          * quiet - Suppress most command line output.
          * im_path - path to ImageMagick executable. '' means it's in the system's PATH environment variable.
          * negate - negate the images before running the script.
          * threshold - threshold (binarize) the images before processing
          * threshold_val - value to use for the 1/0 transition threshold (0-255)
          * repeat_first - if True, instead of using successively numbered images from input_slice, just repeat the
                           same one over and over again.
          * use_mask - use a mask image which is multiplied with the input image on each slice to compensate for
                           projection system irregularities
          * mask_image - image to use for masking.

        Output: Returns (success, message), where success is a boolean and message is a string explaining what went wrong.

        Notes: Only basic checks on arguments are performed here. Be sure to run the first three through the corresponding
            check functions directly above.
        """
        self._done = False
        self._success = True
        self._message_final = "Success"
        self._cancel = False
        self._percent = 0

        try:
            if not os.path.exists(template_cws) or not os.path.exists(input_slice) or output_cws == '' or \
                        (self.use_mask and not os.path.exists(self.mask_image)):
                self._write_message("Invalid input to Honeyguide! One of the input paths is invalid.")
                self._success = False
                self._message_final = "Invalid input filenames"     # cancel!
                self._done = True
                return self._success, self._message_final

            cws_dir = tempfile.mkdtemp()

            # Unzip the file
            try:
                zf = zipfile.ZipFile(template_cws, "r")
                zf.extractall(cws_dir)
                zf.close()
            except:
                try:
                    zf.close()
                finally:
                    self._write_message("Error reading template CWS file.")
                    self._success = False
                    self._message_final = "Error reading template CWS file."
                    self._done = True
                    return self._success, self._message_final

            # get the size of the template images as well as their name form
            imlist = glob.glob(cws_dir + "/*.png")

            if len(imlist) == 0:
                self._write_message("Couldn't find any png images in the CWS! Make sure you slice before you save!")
                self._success = False
                self._message_final = "Invalid CWS file. No embedded images."
                self._done = True
                return self._success, self._message_final

            cws_imname = imlist[0]

            sizestr = self._get_size_str(cws_imname)
            if sizestr == "":
                self._write_message("Error getting the size of the CWS template image! Is your ImageMagick path correct?")
                self._success = False
                self._message_final = "Error using ImageMagick"
                self._done = True
                return self._success, self._message_final
            # set up the conversion function.
            #  -negate - invert the image colors
            #  -threshold - threshold at 50% brightness (to deal with gray inputs)
            #  -background - set the background of any unused portion of the frame to black
            #  -compose - operator for use when compositing new images on top of background pixels
            #  -gravity - center the new image on the scene
            #  -extent - size of output image (on which the input image will be composited)
            #  -composite - command to combine the images
            #  () - imagemagick groupings. Note that these have to be escaped on *nix shells, so I'll use variables for them

            im_bp = '\\(' if on_posix else '('
            im_ep = '\\)' if on_posix else ')'
            imagemagick_prefix = [im_bp]
            imagemagick_flags = []
            if self.negate:
                imagemagick_flags.extend(['-channel', 'RGB', '-negate'])
            if self.threshold:
                imagemagick_flags.extend(['-threshold', '%i%%'%self.threshold_val])
            imagemagick_flags.extend(['-background', 'black', '-compose', 'Copy', '-gravity', 'center', '-extent', sizestr, '-composite', im_ep])
            if self.use_mask:
                imagemagick_flags.extend([im_bp, self.mask_image, '-resize', '%s!'%sizestr, im_ep, '-compose',
                                          'Multiply', '-gravity', 'center', '-composite'])


            # figure out how long the numbers are (by testing length of result on first slice)
            result = re_match_last_number.search(input_slice)
            if result is None and not self.repeat_first:
                self._write_message("Couldn't find number in the filename of your slice input.")
                self._success = False
                self._message_final = "Couldn't find number in the filename of your slice input."
                self._done = True
                return self._success, self._message_final
            if self.repeat_first:
                slice_numpad = 0
                slice_id = 0
            else:
                slice_numpad = result.span()[1] - result.span()[0]
                slice_id = int(result.group())

            # Set up the file name templates
            cws_id = 0
            cws_numpad = 4      # the cws format alwasy uses 4-digit file numbers.
            next_cws_in = cws_imname[:-8] + "0000.png"
            next_slice = input_slice
            # figure out the name of the output image
            first_cws_out = re_match_path.match(cws_imname).group() + re_match_path.sub("", output_cws)[:-4] + "0000.png"
            next_cws_out = first_cws_out

            # check that we have enough slices in the cws to incorporate the whole slice stack.
            if not self.repeat_first:
                # figure out how many images are in the set of slice images
                slice_count = self._count_slice_images(input_slice, slice_numpad, slice_id)
                leftover_slices = slice_count - len(imlist)
                if len(imlist) < slice_count:
                    self._write_message("There are not enough slices in the CWS to fill all the slices in your dataset! %i slices will be lost" % leftover_slices)
                if slice_count == 0:
                    self._write_message("slice count for the incoming image stack is 0. This should not be!")
                    slice_count = 1
            else:
                slice_count = len(imlist)

            self._percent = 5

            if self._cancel:
                # delete the temporary directory
                try:
                    filelist = glob.glob(cws_dir + "/*.*")
                    for filename in filelist:
                        os.remove(filename)
                    os.rmdir(cws_dir)
                finally:
                    self._write_message("Cancelled!")
                    self._percent = 100
                    self._message_final = "Cancelled!"
                    self._success = False
                    self._done = True
                    return self._success, self._message_final

            # go through the files until we run out of source or destination filenames.
            # CW is strange in that the names of the image files need to match the name
            # of the output archive, not the input!
            while os.path.exists(next_cws_in) and os.path.exists(next_slice):
                if not self.quiet:
                    self._write_message("Converting slice %i/%i\r" % (cws_id, slice_count))
                # filter the slice and copy it onto the cws:
                args = [self.imagemagick_cmd]
                args.extend(imagemagick_prefix)
                args.append(next_slice)
                args.extend(imagemagick_flags)
                args.append(next_cws_out)
                # TESTING
                #print(args)
                if subprocess.call(args, shell=True) != 0:
                    self._write_message("Got an odd return code form ImageMagick. Output CWS may be corrupt, or ImageMagick Install Folder may need to be set.")
                    self._success = False
                    self._message_final = "Got an odd return code form ImageMagick. Output CWS may be corrupt, or ImageMagick Install Folder may need to be set."

                # delete the input cws image file if it is different than the output cws image file
                if re_match_path.sub("", next_cws_in).lower() != re_match_path.sub("", next_cws_out).lower():
                    #pass
                    try:
                        os.remove(next_cws_in)
                    finally:
                        pass        # don't care if it fails...

                # figure out the next filenames based on the current ones.
                cws_id += 1
                if not self.repeat_first:
                    slice_id += 1
                    next_slice = re_match_last_number.sub(("%0" + ("%i"%slice_numpad) + "i") % slice_id, input_slice)
                next_cws_out = first_cws_out[:-8] + ("%04i" % cws_id) + ".png"
                next_cws_in = cws_imname[:-8] + ("%04i" % cws_id) + ".png"

                # update status; check for cancel
                self._percent = 5 + 80.0 * float(cws_id) / slice_count
                if self._cancel:
                    # delete the temporary directory
                    try:
                        filelist = glob.glob(cws_dir + "/*.*")
                        for filename in filelist:
                            os.remove(filename)
                        os.rmdir(cws_dir)
                    finally:
                        self._write_message("Cancelled!")
                        self._percent = 100
                        self._message_final = "Cancelled!"
                        self._success = False
                        self._done = True
                        return self._success, self._message_final

            # if we ran out of slice files before we ran out of cws slices, set all remaining cws slices to black.
            blankfile = os.path.join(cws_dir, "blank.png")
            # generate a blank image and save it to blankfile
            args = [self.imagemagick_cmd, "-size", sizestr, "xc:black", blankfile]
            # TESTING
            print(args)
            subprocess.call(args, shell=True)
            while os.path.exists(next_cws_in):
                if not self.quiet:
                    self._write_message("Blanking slice %i/%i\r" % (cws_id, len(imlist)))

                try:
                    shutil.copy(blankfile, next_cws_out)
                except:
                    self._write_message("Error creating blanked file. Resulting CWS may be corrupt.")
                    self._success = False
                    self._message_final = "Error creating blanked file. Resulting CWS may be corrupt."

                # delete the input cws image file if it is different than the output cws image file
                if re_match_path.sub("",next_cws_in).lower() != re_match_path.sub("",next_cws_out).lower() :
                    #pass
                    try:
                        os.remove(next_cws_in)
                    finally:
                        pass        # don't care if it fails

                # figure out the next filenames based on the current ones.
                cws_id += 1
                next_cws_out = first_cws_out[:-8] + ("%04i" % cws_id) + ".png"
                next_cws_in = cws_imname[:-8] + ("%04i" % cws_id) + ".png"

                # update status; check for cancel
                self._percent = 85 + 10.0 * float(cws_id - slice_count) / float(len(imlist) - slice_count + 1)
                if self._cancel:
                    # delete the temporary directory
                    try:
                        filelist = glob.glob(cws_dir + "/*.*")
                        for filename in filelist:
                            os.remove(filename)
                        os.rmdir(cws_dir)
                    finally:
                        self._write_message("Cancelled!")
                        self._percent = 100
                        self._message_final = "Cancelled!"
                        self._success = False
                        self._done = True
                        return self._success, self._message_final

            try:
                os.remove(blankfile)
            finally:
                pass        # don't care if it fails.

            # re-zip the files into the "new" cws
            filelist = glob.glob(cws_dir + "/*.*")
            try:
                zf = zipfile.ZipFile(output_cws, "w")
                for file in filelist:
                    zf.write(file, re_match_path.sub("", file))
                zf.close()
            except:
                self._write_message("Error writing new CWS file.")
                self._success = False
                self._message_final = "Error writing new CWS file"

            self._percent = 99

            # delete the temporary directory
            try:
                filelist = glob.glob(cws_dir + "/*.*")
                for filename in filelist:
                    os.remove(filename)
                os.rmdir(cws_dir)
            finally:
                self._write_message("Done!")
                self._percent = 100
                self._done = True
                return self._success, self._message_final

        except: # catch-all for the whole process.
            self._write_message("An unknown error occurred")
            self._success = False
            self._message_final = "An unknown error occurred"
            self._done = True
            return self._success, self._message_final

    def status_check(self):
        """Returns the status of a background honeyguide operation in the tuple (done?, success?, message, percent)
        where done is False if the code is still running and True if we're finished, success is False if the whole
        operation failed and True if it succeeded (value indeterminate if done==False), message is the final output
        message from the process (but indeterminate during run) and percent stores the percentage of the
        operation that's complete at this time."""
        return self._done, self._success, self._message_final, self._percent

    def status_message(self):
        """Returns the most recent status message from the background honeyguide job. If nothing's new, returns an
        empty string."""
        return "" if self._messages.empty() else self._messages.get()

    def cancel(self):
        """Cancels the background Honeyguide operation."""
        self._cancel = True
    
    def _write_message(self, message):
        """Writes a message to the status message queue for future reading if running in background. Also prints
        it to the console. Doesn't use the mutex because queues are thread safe"""
        self._messages.put(message)
        self._log(message)

    def _log(self, message):
        print(message)
        try:
            if self.logfile is not None:
                self.logfile.write(message + "\n")
                self.logfile.flush()
        except:
            pass

    @staticmethod
    def get_path(filename):
        """Returns just the path (folder part) of the complete filename <filename>"""
        out = re_match_path.match(filename)
        if not out is None:
            return out.group()
        else:
            return filename

    def _get_size_str(self, im_name) :
        """Returns the size of an image as a string, "WWWxHHH" in a format ImageMagick can recognize.
        * im_name = name of image to check size of.
        """
        # gets the size of the image in a form imagemagick can understand
        try:
            sizestr = subprocess.check_output([self.imagemagick_cmd, im_name, '-ping', '-format', '"%wx%h"', 'info:'], shell=True)
            return sizestr[1:-1]     # trim leading & trailing quotes
        except subprocess.CalledProcessError:
            return ""

    @staticmethod
    def _count_slice_images(slice_fname, slice_numpad, slice_id):
        # iterate until we can't find a next matching slice image name.
        next_slice = slice_fname
        count = 0

        while os.path.exists(next_slice):
            # figure out the next filenames based on the current ones.
            slice_id += 1
            count += 1
            next_slice = re_match_last_number.sub(("%0" + ('%i'%slice_numpad) + "i") % slice_id, slice_fname)

        return count

    def compare_cws_files(self, file1, file2, imagemagick_cmd="magick"):
        """Compares two CWS files, checking for differences and storing them in ./<file1 fname>_diff.
        Returns True if the cws files contain identical data (images, gcode, slicing files, and manifest)
        and False otherwise."""
        if not os.path.exists(file1) or not os.path.exists(file2):
            self._log("Can't find one of the input files for comparing")
            return False

        same = True

        cws_dir1 = tempfile.mkdtemp()
        cws_dir2 = tempfile.mkdtemp()
        diff_dir = os.path.join(".", file1[:-4] + "_diff")
        if not os.path.exists(diff_dir):
            os.mkdir(diff_dir)

        # Unzip the file
        try:
            zf = zipfile.ZipFile(file1, "r")
            zf.extractall(cws_dir1)
            zf.close()

            zf = zipfile.ZipFile(file2, "r")
            zf.extractall(cws_dir2)
            zf.close()
        except:
            try:
                zf.close()
            finally:
                self._log("Error reading CWS files.")
                return False

        # use the filenames to find the images inside. This is not intuitive, but it's how CW works.
        cws_imname1 = os.path.split(file1)[1][:-4] + "0000.png"
        cws_imname2 = os.path.split(file2)[1][:-4] + "0000.png"

        # get the size of the template images as well as their name form
        imlist1 = glob.glob(cws_dir1 + cws_imname1[:-8] + "*.png")
        imlist2 = glob.glob(cws_dir2 + cws_imname1[:-8] + "*.png")

        if len(imlist1) != len(imlist2):
            self._log("CWS's have a different number of images in them!")
            same = False

        # Set up the file name templates
        cws_id = 0
        samecount = 0
        diffcount = 0
        cws_numpad = 4      # the cws format alwasy uses 4-digit file numbers.
        next_cws_in1 = os.path.join(cws_dir1, cws_imname1[:-8] + "0000.png")
        next_cws_in2 = os.path.join(cws_dir2, cws_imname2[:-8] + "0000.png")

        slice_count = len(imlist1)

        imagemagick_prefix = [imagemagick_cmd]
        imagemagick_postfix = ["-metric", "AE", "-compare", "-format", '"%[distortion]"', 'info:']

        # go through the files until we run out of source or destination filenames.
        # Check each pair of frames for matching.
        while os.path.exists(next_cws_in1) and os.path.exists(next_cws_in2):
            # compare the two slice images...
            args = []
            args.extend(imagemagick_prefix)
            # add the names of the two files to be compared
            args.extend([next_cws_in1, next_cws_in2])
            args.extend(imagemagick_postfix)
            # add the diff file location
            diffname = os.path.join(diff_dir, "diff%04u.png" % cws_id)
            #args.extend([os.path.join(diff_dir, diffname)])
            # TESTING
            print('comp = ' + str(args))

            # check the output of the imagemagick call
            try:
                out = subprocess.check_output(args, shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                out = e.output
            # find a number in out
            match = re.search('[0-9]+',out)

            if match is not None and match.group() == '0':     # This means no difference between the two images
                # The two are identical. Delete the diff image.
                #os.remove(os.path.join(diff_dir, diffname))
                samecount += 1
            else:
                diffcount += 1
                self._log("Found differences: %s" % diffname)
                # generate a difference image
                args[-1] = diffname

                try:
                    subprocess.call(args, shell=True, stderr=subprocess.STDOUT)
                finally:
                    pass

            # figure out the next filenames based on the current ones.
            cws_id += 1
            next_cws_in1 = cws_imname1[:-8] + ("%04i" % cws_id) + ".png"
            next_cws_in2 = cws_imname2[:-8] + ("%04i" % cws_id) + ".png"

        if diffcount > 0:
            self._log("Found differences on at least one slice.")
            same = False

        # check for gcode changes
        # TODO: Check these functions...I never actually tested them.
        gcode1 = glob.glob(os.path.join(cws_dir1, "*.gcode"))
        gcode2 = glob.glob(os.path.join(cws_dir2, "*.gcode"))
        if len(gcode1) != 1 or len(gcode2) != 1:
            self._log("More than one gcode file detected! Only the first one is checked.")

        if not Honeyguide._diff_text_files(gcode1[0], gcode2[0], os.path.split(file1)[1], os.path.split(file2)[1],
                                           diff_dir):
            self._log("Gcode files don't match.")
            same = False
        
        # check for slicing changes
        slice1 = glob.glob(os.path.join(cws_dir1, "*.slicing"))
        slice2 = glob.glob(os.path.join(cws_dir2, "*.slicing"))
        if len(slice1) != 1 or len(slice2) != 1:
            self._log("More than one slicing file detected! Only the first one is checked.")

        if not Honeyguide._diff_text_files(slice1[0], slice2[0], os.path.split(file1)[1], os.path.split(file2)[1],
                                           diff_dir):
            self._log("Slicing files don't match.")
            same = False
        
        # check for manifest changes
        xml1 = glob.glob(os.path.join(cws_dir1, "manifest.xml"))
        xml2 = glob.glob(os.path.join(cws_dir2, "manifest.xml"))
        if len(xml1) != 1 or len(xml2) != 1:
            self._log("More than one manifest file detected! Only the first one is checked.")

        if not Honeyguide._diff_text_files(xml1[0], xml2[0], os.path.split(file1)[1], os.path.split(file2)[1],
                                           diff_dir):
            self._log("Manifest files don't match. This usually does not cause issues.")
            same = False
            
        if same:
            try:
                os.rmdir(diff_dir)
            except:
                pass

        return same

    @staticmethod
    def _diff_text_files(file1, file2, name1, name2, diffdir):
        """Compares two text files. If there are differences, creates an html diff using pythons diff utility.
        Returns same? (boolean)
        """

        fromlines = open(file1, 'U').readlines()
        tolines = open(file2, 'U').readlines()

        # check for any differences between the two files
        same = True
        for line_id in range(len(tolines)):
            if fromlines[line_id] != tolines[line_id]:
                same = False
                break

        if same:
            return True
        else:
            diff = difflib.HtmlDiff().make_file(fromlines, tolines, name1, name2, context=True, numlines=3)
            with open(os.path.join(diffdir, os.path.split(file1)[1]), "w") as fout:
                fout.writelines(diff)
            return False


# Run some checks to see if my cws files match a reference set
if __name__ == "__main__":

    h = Honeyguide()
    cp = ConfigParser.SafeConfigParser()

    cp.read("./Tests/tests.ini")

    temp_dir = tempfile.mkdtemp()

    h.imagemagick_cmd = cp.get("General", "imagemagickcmd")
    h.quiet = True

    all_passed = True

    for test in cp.sections():
        if test != "General":
            print("Building %s" % test)
            # load this test...
            template = cp.get(test, "template")
            image = cp.get(test, "inputimages")
            refcws = cp.get(test, "refcws")

            h.negate = int(cp.get(test, "negate"))
            h.threshold = int(cp.get(test, "threshold"))
            h.threshold_val = int(cp.get(test, "threshval"))
            h.repeat_first = int(cp.get(test, "replicatefirst"))
            h.use_mask = int(cp.get(test, "usemask"))
            h.mask_image = cp.get(test, "maskimage")

            temp_cws = os.path.join(temp_dir, test + ".cws")

            # run this test
            h.do_honeyguide(template, image, temp_cws)

            # check the results
            print("Checking %s" % test)
            if h.compare_cws_files(refcws, temp_cws, h.imagemagick_cmd):
                print("%s Passed" % test)
            else:
                print("%s Failed!" % test)
                all_passed = False

    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed!")

    files = glob.glob(temp_dir + "/*.*")
    for file in files:
        os.remove(file)
    os.rmdir(temp_dir)