# Honeyguide - a program for injecting image stack data into CreationWorkshop CWS files.
# Working.py - shows and manages the working dialog.
#
# Ben Weiss at the University of Washington
#
# Source: Sample code borrowed from the folowing places:
# http://infohost.nmt.edu/tcc/help/pubs/tkinter/web/minimal-app.html
#
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

__author__ = 'Ben Weiss'

import sys
import ttk
import cws_scripts as cws

import Tkinter as tk, tkMessageBox


class Working(ttk.Frame):
    def __init__(self, master, logfile):
        # non-GUI variables
        self.cws = None
        self.cancelled = False
        self.logfile = logfile

        ttk.Frame.__init__(self, master, padding="5 5 12 12")
        self.master.title('Working')
        # self.winfo_toplevel().rowconfigure(0, weight=1)
        self.winfo_toplevel().columnconfigure(0, weight=1)
        self._root().resizable(True, False)     # very bad hack, adapted from http://sebsauvage.net/python/gui/#add_constraint
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.grid(column=0, row=0, sticky=tk.N+tk.S+tk.W+tk.E)
        #self.pack(fill=tk.BOTH, expand=1)

        # install closing handler
        self.winfo_toplevel().protocol("WM_DELETE_WINDOW", self.close)

        # TK variables
        self.v_progress = tk.IntVar()
        self.v_progress.set(0)
        self.v_info = tk.StringVar()
        self.v_info.set("Working...")
        self.v_cancel_text = tk.StringVar()
        self.v_cancel_text.set("Cancel")

        # Create the widgets
        pb = ttk.Progressbar(self, mode="determinate", variable=self.v_progress, length=300)
        pb.grid(column=0, row=1, sticky=tk.W+tk.E, padx=6, pady=8)

        ttk.Label(self, textvariable=self.v_info).grid(column=0, row=2, sticky=tk.W+tk.E, padx=6, pady=8)
        ttk.Button(self, textvariable=self.v_cancel_text, command=self.cancel).grid(column=0, row=3, padx=6, pady=8)

    def cancel(self):
        if self.cws is None:
            self.close()
        else:
            self.cws.cancel()
            self.cancelled = True

    def go(self, cws_obj, template_cws, input_image, output_cws):
        """Runs the Honeyguide operation on a background thread, updating the progressbar and the status every 100 ms.
        """
        self.cws = cws_obj
        self.cancelled = False
        self.v_cancel_text.set("Cancel")
        self.v_info.set("Working...")
        self.v_progress.set(0)
        cws_obj.do_honeyguide_background(template_cws, input_image, output_cws)

        self.after(100, self.check)

    def check(self):
        """Checks on the background task and updates the UI as needed"""
        if self.cws is None:
            return      # we're done.

        # honeyguide stores its messages in a queue, returing the oldest. We'll drain the queue each time so we
        # get the most current one.
        last_message = new_message = self.cws.status_message()
        while new_message != "":
            last_message = new_message
            new_message = self.cws.status_message()
        if last_message != "":
            self.v_info.set(last_message)

        # get the status and update the progress bar
        done, success, message, percent = self.cws.status_check()
        self.v_progress.set(int(percent))

        if done:
            self.cws = None
            self.v_info.set(message)
            if success or self.cancelled:
                self.v_cancel_text.set("Close")
            else:
                tkMessageBox.showerror("Error", "Conversion failed with the following error:\n%s" % message,
                                       parent=self.winfo_toplevel())
                self.close()
        else:
            self.after(100, self.check)

    def close(self):
        # Just hide this window. It will get destroyed when we close down the program.
        if self.cws is not None:
            self.cancel()
        self.cws = None
        self.master.withdraw()

# only run this file for testing/layout purposes!!!
if __name__ == "__main__":
    app = Working(None)
    app.mainloop()

