# Honeyguide - a program for injecting image stack data into CreationWorkshop CWS files.
#
# Ben Weiss at the University of Washington
#
# Source: Sample code borrowed from the folowing places:
# http://infohost.nmt.edu/tcc/help/pubs/tkinter/web/minimal-app.html
# http://www.tkdocs.com/tutorial/firstexample.html
# https://docs.python.org/2.7/library/configparser.html
#
# Why Honeyguide? See https://en.wikipedia.org/wiki/Honeyguide and https://en.wikipedia.org/wiki/Brood_parasite
#
# (c) 2015 Ben Weiss
# License: MIT License:
#
#    Copyright (c) 2015 Ben Weiss; parts (c) 2015 Ben Weiss, University of Washington
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
#
# TODO:
#  - Document advanced options in Instructions
#  - Implement command line mode
#  - Have the app log capture python errors, if possible


__author__ = 'Ben Weiss'

import sys
import ttk
import os
import cws_scripts
import ConfigParser as cp
import workingDialog

import Tkinter as tk
import tkFileDialog


class Application(ttk.Frame):
    def __init__(self, master=None, logfile=None):
        # Non-TK class variables:
        self.logfile = logfile
        self.template_slices = 0
        self.image_slices = 0
        self.cws = cws_scripts.Honeyguide(logfile)

        ttk.Frame.__init__(self, master, padding="3 3 12 12")
        self.master.title('Honeyguide')
        # self.winfo_toplevel().rowconfigure(0, weight=1)
        self.winfo_toplevel().columnconfigure(0, weight=1)
        self._root().resizable(True, False)     # very bad hack, adapted from http://sebsauvage.net/python/gui/#add_constraint
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.grid(column=0, row=0, sticky=tk.N+tk.S+tk.W+tk.E)

        # install closing handler
        self.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.close)

        # TK variables
        self.template_cws = tk.StringVar()
        self.input_image = tk.StringVar()
        self.output_cws = tk.StringVar()

        self.template_message = tk.StringVar()
        self.image_message = tk.StringVar()
        self.output_message = tk.StringVar()

        self.advanced_title = tk.StringVar()
        self.advanced_title.set("Show Options")
        self.negate = tk.BooleanVar()
        self.negate.set(False)
        self.threshold = tk.BooleanVar()
        self.threshold.set(False)
        self.threshold_val = tk.StringVar()
        self.threshold_val.set("128")
        self.replicate_first = tk.BooleanVar()
        self.replicate_first.set(False)
        self.imagemagick_path = tk.StringVar()
        self.imagemagick_message = tk.StringVar()

        # Text validators
        templateValCmd = self.register(self.template_validate)
        imageValCmd = self.register(self.image_validate)
        outputValCmd = self.register(self.output_validate)
        threshValCmd = self.register(self.threshold_validate)
        impValCmd = self.register(self.imagemagick_path_validate)

        # Associated conditions for Process button enabling:
        self.template_ok = False
        self.image_ok = False
        self.output_ok = False
        self.thresh_ok = False
        self.imagemagick_ok = False

        # Create the widgets
        ttk.Label(self, text="Template CWS:").grid(column=0, row=1, sticky=tk.E)

        self.template_entry = ttk.Entry(self, width=35, textvariable=self.template_cws, validate='focusout',
                                        validatecommand=templateValCmd)
        self.template_entry.grid(column=1, row=1, sticky=tk.W+tk.E)

        ttk.Button(self, text="...", command=self.template_dialog, width=3).grid(column=2, row=1, sticky=tk.W)

        self.template_label = ttk.Label(self, textvariable=self.template_message)
        self.template_label.grid(column=1, row=2, columnspan=2, sticky=tk.W+tk.E+tk.N)

        # Second row
        ttk.Label(self, text="First Image:").grid(column=0, row=3, sticky=tk.E)

        self.image_entry = ttk.Entry(self, width=35, textvariable=self.input_image, validate='focusout',
                                     validatecommand=imageValCmd)
        self.image_entry.grid(column=1, row=3, sticky=tk.W+tk.E)

        ttk.Button(self, text="...", command=self.image_dialog, width=3).grid(column=2, row=3, sticky=tk.W)

        self.image_label = ttk.Label(self, textvariable=self.image_message)
        self.image_label.grid(column=1, row=4, columnspan=2, sticky=tk.W+tk.E)

        # Third row
        ttk.Label(self, text="Output CWS:").grid(column=0, row=5, sticky=tk.E)

        self.output_entry = ttk.Entry(self, width=35, textvariable=self.output_cws, validate='focusout',
                                      validatecommand=outputValCmd)
        self.output_entry.grid(column=1, row=5, sticky=tk.W+tk.E)

        ttk.Button(self, text="...", command=self.output_dialog, width=3).grid(column=2, row=5, sticky=tk.W)

        self.output_label = ttk.Label(self, textvariable=self.output_message)
        self.output_label.grid(column=1, row=6, columnspan=2, sticky=tk.W+tk.E)

        # Buttons row
        subframe = ttk.Frame(self)
        subframe.grid(column=0, row=7, columnspan=3, sticky=tk.E)
        ttk.Button(subframe, text='Instructions', command=self.instructions_dialog).grid(column=0, row=0)
        ttk.Button(subframe, textvariable=self.advanced_title, command=self.show_advanced).grid(column=1, row=0)
        self.go_button = ttk.Button(subframe, text='Process', command=self.go)
        self.go_button.state(["disabled"])
        self.go_button.grid(column=2, row=0)
        ttk.Button(subframe, text='Quit', command=self.close).grid(column=3, row=0)
        for child in subframe.winfo_children(): child.grid_configure(padx=3, pady=4)

        # Advanced options
        self.adv_frame = ttk.LabelFrame(self, text="Advanced Options")
        self.adv_frame.grid(column=0, row=8, columnspan=3, sticky=tk.E+tk.W)

        ttk.Checkbutton(self.adv_frame, text="Negate Input Images", variable=self.negate)\
            .grid(column=0, row=0, padx=3, pady=4, sticky=tk.W)
        ttk.Checkbutton(self.adv_frame, text="Threshold", variable=self.threshold)\
            .grid(column=0, row=1, padx=3, pady=4, sticky=tk.W)

        subframe = ttk.Frame(self.adv_frame)
        subframe.grid(column=0, row=2, sticky=tk.W)
        ttk.Label(subframe, text="Threshold Level (0-255):").grid(column=0, row=0, padx=8, pady=4, sticky=tk.W)
        ttk.Entry(subframe, textvariable=self.threshold_val, validate='all', validatecommand=threshValCmd)\
            .grid(column=1, row=0, padx=8, pady=4, sticky=tk.W)

        ttk.Checkbutton(self.adv_frame, text="Just Replicate First Image", variable=self.replicate_first,
                        command=self.image_validate)\
            .grid(column=0, row=4, padx=3, pady=4, sticky=tk.W)

        subframe = ttk.Frame(self.adv_frame)
        subframe.grid(column=0, row=5, sticky=tk.W)
        ttk.Label(subframe, text="ImageMagick Install Folder:").grid(column=0, row=0, padx=3, pady=4)
        ttk.Entry(subframe, textvariable=self.imagemagick_path, validate='focusout', validatecommand=impValCmd)\
            .grid(column=1, row=0, padx=3, pady=4, sticky=tk.W)
        ttk.Button(subframe, text="...", width=3, command=self.imagemagick_dialog).grid(column=2, row=0, padx=3, pady=4)
        ttk.Label(subframe, textvariable=self.imagemagick_message).grid(column=3, row=0, padx=3, pady=4)

        for child in self.winfo_children(): child.grid_configure(padx=3, pady=4)

        # Tweak the padding
        self.rowconfigure(2, minsize=30)
        self.rowconfigure(4, minsize=30)
        self.rowconfigure(6, minsize=30)
        self.template_label.grid_configure(pady=0)
        self.image_label.grid_configure(pady=0)
        self.output_label.grid_configure(pady=0)

        self.adv_frame.grid_remove()       # hide the advanced options
        self.adv_hidden = True

        # Create the dialog window (used later, but window destroys and rebuilds if we create it later)
        self.tl = tk.Toplevel(self)
        self.tl.withdraw()
        self.working_dialog = workingDialog.Working(self.tl, logfile)

        self.load_settings()

    def template_dialog(self):
        cur = self.template_cws.get()
        defdir = ''
        if cur != '':
            defdir = self.cws.get_path(cur)
        fname = tkFileDialog.askopenfilename(filetypes=[('CWS Files', '.cws'),('All Files', '.*')],
                                             title="Select CWS Template File", parent=self, initialdir=defdir)
        if fname != "":
            self.template_cws.set(fname)
            self.template_validate()

    def image_dialog(self):
        cur = self.input_image.get()
        defdir = ''
        if cur != '':
            defdir = self.cws.get_path(cur)
        fname = tkFileDialog.askopenfilename(filetypes=[('Image Files', '.png;.bmp;.tif;.tiff'), ('All Files', '.*') ],
                                             title="Select FIRST Slice File", parent=self, initialdir=defdir)

        if fname != "":
            self.input_image.set(fname)
            self.image_validate()

    def output_dialog(self):
        cur = self.output_cws.get()
        defdir = ''
        if cur != '':
            defdir = self.cws.get_path(cur)
        fname = tkFileDialog.asksaveasfilename(filetypes=[('CWS Files','.cws'), ('All Files', '.*')],
                                               defaultextension='.cws', title="Save output CWS file as...", parent=self,
                                               initialdir=defdir)

        if fname != "":
            self.output_cws.set(fname)
            self.output_validate()

    def imagemagick_dialog(self):
        def_dir = self.imagemagick_path.get()
        if def_dir == "":
            if sys.platform == "linux" or sys.platform == "linux2":
                def_dir = "/"
            elif sys.platform == "darwin":
                def_dir = "/"
            elif sys.platform == "win32":
                def_dir = "C:\\Program Files\\"

        dirname = tkFileDialog.askdirectory(parent=self, initialdir=def_dir, title="Select ImageMagick Install Location...1")
        if dirname != "":
            self.imagemagick_path.set(dirname)

            self.imagemagick_path_validate()

    def show_advanced(self):
        if self.adv_hidden:
            self.adv_frame.grid()
            self.advanced_title.set("Show Options")
        else:
            self.adv_frame.grid_remove()
            self.advanced_title.set("Hide Options")
        self.adv_hidden = not self.adv_hidden

    def instructions_dialog(self):
        """Opens the instructions dialog in the system default viewer (hopefully)"""
        os.system("instructions.html")

    def template_validate(self):
        """Validates changes to the Template field using the CWS scripts"""
        # TODO: Figure out whether this needs to go on a background thread.
        self.template_ok, message, slices = self.cws.template_check(self.template_cws.get())
        self.template_slices = slices
        self.template_message.set(message)
        self.template_entry.xview(len(self.template_cws.get()))
        self.evaluate_go()
        return True

    def image_validate(self):
        """Validates whether the image selected is acceptable for use. Called both as the input_image validator
        and as the command for the Replicate First checkbox."""
        self.image_ok, message, self.image_slices = self.cws.imstack_check(self.input_image.get())
        # Special case: If Replicate is set to True, we can be OK even if imstack_check returns False, as long
        # as we have at least one image_slice.
        if self.image_slices > 0 and self.replicate_first.get():
            self.image_ok = True
            self.image_message.set("This image will be used for all slices.")
        else:
            self.image_message.set(message)
        self.image_entry.xview(len(self.input_image.get()))
        self.evaluate_go()
        return True

    def output_validate(self):
        self.output_ok = self.cws.output_check(self.output_cws.get())
        if not self.output_ok:
            self.output_message.set("Invalid Output Filename")
        else:
            if self.template_ok and self.image_ok:
                if self.template_slices < self.image_slices:
                    self.output_message.set("Image stack is bigger than CWS template. %i slices will be lost" %
                                            (self.image_slices - self.template_slices))
                else:
                    self.output_message.set("OK")
            else:
                self.output_message.set("OK")
        self.output_entry.xview(len(self.output_cws.get()))
        self.evaluate_go()
        return True

    def threshold_validate(self):
        val = self.threshold_val.get()
        self.thresh_ok = False
        if val.strip().isdigit():
            i = int(val.strip())
            if 0 <= i <= 255:
                self.thresh_ok = True
        self.evaluate_go()
        return True

    def imagemagick_path_validate(self):
        dirname = self.imagemagick_path.get()
        if os.path.exists(os.path.join(dirname, "convert")) or os.path.exists(os.path.join(dirname, "convert.exe")):
            self.imagemagick_message.set("OK")
            self.imagemagick_ok = True
        elif dirname == "":
            self.imagemagick_message.set("No folder selected. Will use system PATH.")
            self.imagemagick_ok = True
        else:
            self.imagemagick_message.set("Couldn't find ImageMagick executables in this folder.")
            self.imagemagick_ok = False
        self.evaluate_go()
        return True

    def evaluate_go(self):
        if self.image_ok and self.imagemagick_ok and self.output_ok and self.template_ok and (not self.threshold.get()
                or self.thresh_ok):
            self.go_button.state(["!disabled"])
        else:
            self.go_button.state(["disabled"])

    def go(self):
        self.log("Args:\nTemplate %s\nImage %s\nOutput %s\nNegate %s\nThresh %s Val %i\nReplicate %s\nIMPath %s" %
              (self.template_cws.get(), self.input_image.get(), self.output_cws.get(),
               self.negate.get(), self.threshold.get(), int(self.threshold_val.get().strip()), self.replicate_first.get(),
               self.imagemagick_path.get()))
        thresh_val = 128
        if self.threshold.get():
            try:
                thresh_val = int(self.threshold_val.get().strip())
            except:
                self.log("Error parsing Threshold value. Using 128 as default.")

        # Load these settings into the CWS
        self.cws.negate = self.negate.get()
        self.cws.threshold = self.threshold.get()
        self.cws.threshold_val = int(self.threshold_val.get().strip())
        self.cws.replicate_first = self.replicate_first.get()
        self.cws.imagemagick_path = self.imagemagick_path.get()

        # Open the window and launch the job.
        self.tl.update()
        self.tl.deiconify()
        self.working_dialog.go(self.cws, self.template_cws.get(), self.input_image.get(), self.output_cws.get())
        self.wait_window(self.tl)

    def save_settings(self):
        config = cp.SafeConfigParser()
        config.add_section('Honeyguide')
        config.set('Honeyguide', 'TemplateCWS', self.template_cws.get())
        config.set('Honeyguide', 'InputImages', self.input_image.get())
        config.set('Honeyguide', 'OutputCWS', self.output_cws.get())
        config.set('Honeyguide', 'Negate', str(self.negate.get()))
        config.set('Honeyguide', 'Threshold', str(self.threshold.get()))
        config.set('Honeyguide', 'ThreshVal', self.threshold_val.get())
        config.set('Honeyguide', 'ReplicateFirst', str(self.replicate_first.get()))
        config.set('Honeyguide', 'ImageMagickPath', self.imagemagick_path.get())
        #config.set('Honeyguide', 'Window', self._root().winfo_geometry())

        with open("settings.ini", "wb") as outfile:
            config.write(outfile)

    def load_settings(self):
        config = cp.SafeConfigParser()
        try:
            config.read("settings.ini")

            self.template_cws.set(config.get('Honeyguide', 'TemplateCWS'))
            self.input_image.set(config.get('Honeyguide', 'InputImages'))
            self.output_cws.set(config.get('Honeyguide', 'OutputCWS'))
            self.negate.set(config.getboolean('Honeyguide', 'Negate'))
            self.threshold.set(config.getboolean('Honeyguide', 'Threshold'))
            self.threshold_val.set(config.get('Honeyguide', 'ThreshVal'))
            self.replicate_first.set(config.getboolean('Honeyguide', 'ReplicateFirst'))
            self.imagemagick_path.set(config.get('Honeyguide', 'ImageMagickPath'))
            #self._root().geometry(config.get('Honeyguide', 'Window'))
            self.log("Settings loaded successfully")

        except cp.Error:
            self.log("Default settings loaded.")

        # go validate the settings now.
        self.update()       # These two updates needed to make text alignment in validate* work correctly.
        self.update_idletasks()
        self.template_validate()
        self.image_validate()
        self.output_validate()
        self.imagemagick_path_validate()
        self.threshold_validate()

    def close(self):
        self.save_settings()
        self.working_dialog.quit()
        self.working_dialog.destroy()
        self.quit()
        self.destroy()

    def log(self, message):
        """Prints a message to the logfile"""
        print(message)
        try:
            if self.logfile is not None:
                self.logfile.write(message + "\n")
                self.logfile.flush()
        except:
            pass

def main():
    with open("app.log", "w") as logfile:
        app = Application(logfile=logfile)
        app.mainloop()


if __name__ == "__main__":
    main()
