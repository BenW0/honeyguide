__author__ = 'Ben'

from distutils.core import setup
import py2exe

setup(
    version="0.1",
    description="Honeyguide: CWS image stack replacement program.",
    name="Honeyguide",

    # targets to build
    windows=[{"script": "honeyguide.py", "icon_resources": [(1, "icon.ico")]}],
    console=[{"script": "honeyguide_console.py", "icon_resources": [(1, "icon.ico")]}],
    scripts=["cws_scripts.py", "workingDialog.py"],
    # extra files
    data_files=[(".", ["instructions.html", "LICENSE.txt"])]
    )
