"""
Emma - Emma Memory and Mapfile Analyser
Copyright (C) 2019 The Emma authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>
"""

# Emma Memory and Mapfile Analyser Visualiser - helpers

import os
import sys

from pypiscout.SCout_Logger import Logger as sc

import Emma.shared_libs.emma_helper
import Emma.shared_libs.stringConstants


def getLastModFileOrPrompt(subStringIdentifier: str, inOutPath: str, quiet: bool, append: bool, noprompt: bool) -> str:
    """
    If quiet: Evaluates the file to use listing all files in "<projectPath>/MemStats", then matching
    the substring given in summaryTypes and returns the newest file matching the substring
    :param subStringIdentifier: Substring the list of files in the memStats directory is matched
    :param inOutPath: [string]
    :param quiet: [bool]
    :param append: [bool]
    :param noprompt: [bool]
    :return: file name to use
    """
    fileToUse = None
    path = Emma.shared_libs.emma_helper.joinPath(inOutPath, Emma.shared_libs.stringConstants.OUTPUT_DIR)
    lastModifiedFiles = Emma.shared_libs.emma_helper.lastModifiedFilesInDir(path, ".csv")            # Newest file is last element

    # Check if no files were found
    if len(lastModifiedFiles) < 1:
        sc().error("No files in the specified directory:", os.path.abspath(path))

    # Get last modified file (we NOT ONLY need this for the quiet mode)
    # Backwards iterate over file list (so newest file will be first)
    for i in range(len(lastModifiedFiles) - 1, -1, -1):
        # Select module/image summary .csv file
        if subStringIdentifier in lastModifiedFiles[i]:
            fileToUse = lastModifiedFiles[i]
            # Exit in first match which is the newest file as we are backwards iterating
            break

    if quiet:
        # Just use the last found file (we did this before)
        pass
    elif noprompt:
        sc().wwarning("No prompt is active. Using last modified file named:", fileToUse)
        pass
    elif not append:
        # If nothing specified AND append mode is OFF ask which file to use
        sc().info("Last modified file:")
        print("\t" + fileToUse)
        sc().info("`y` to accept; otherwise specify an absolute path (without quotes)")
        while True:
            text = input("> ")

            if text == "y":
                break
            if text is not None and text != "" and os.path.isfile(text) and text.endswith(".csv"):
                fileToUse = text
                break
            else:
                sc().warning("Invalid input.")

        # Check if the fixed file name portions are within the found file name
        if Emma.shared_libs.stringConstants.FILE_IDENTIFIER_OBJECT_SUMMARY is Emma.shared_libs.emma_helper.evalSummary(lastModifiedFiles[-1]):
            sc().warning("Last modified file is a " + Emma.shared_libs.stringConstants.FILE_IDENTIFIER_OBJECT_SUMMARY + "\n")

    if fileToUse is None:
        sc().error("No file containing '" + subStringIdentifier + "' found in " + path)

    return fileToUse
