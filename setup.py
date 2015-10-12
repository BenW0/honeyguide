__author__ = 'Ben'

# Requires the module py2exe: http://www.py2exe.org
# To build the program into exe's, use "python setup.py py2exe"

from distutils.core import setup
import py2exe

setup(
    version="0.11",
    description="Honeyguide: CWS image stack replacement program.",
    name="Honeyguide",

    # targets to build
    windows=[{"script": "honeyguide.py", "icon_resources": [(1, "icon.ico")]}],
    console=[{"script": "honeyguide_console.py", "icon_resources": [(1, "icon.ico")]}],
    scripts=["cws_scripts.py", "workingDialog.py"],
    # extra files
    data_files=[(".", ["instructions.html", "LICENSE.txt"])]
    )
