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


import os
import re
import bisect
import collections

from pypiscout.SCout_Logger import Logger as sc

from shared_libs.stringConstants import *
import shared_libs.emma_helper
import emma_libs.mapfileProcessor
import emma_libs.ghsMapfileRegexes
import emma_libs.memoryEntry


class GhsMapfileProcessor(emma_libs.mapfileProcessor.MapfileProcessor):
    def __init__(self):
        self.analyseDebug = None

    def processMapfiles(self, configId, configuration, analyseDebug):
        self.analyseDebug = analyseDebug

        sectionCollection = self.__importData(configId, configuration, emma_libs.ghsMapfileRegexes.ImageSummaryPattern())
        objectCollection = self.__importData(configId, configuration, emma_libs.ghsMapfileRegexes.ModuleSummaryPattern())

        return sectionCollection, objectCollection

    def __importData(self, configId, configuration, defaultRegexPattern):
        """
        Processes all input data and adds it to our container (`consumerCollection`)
        :return: number of configIDs
        """

        result = []
        memoryRegionsToExcludeFromMapfiles = {}

        # Reading the hexadecimal offset value from the addresSpaces*.json. This value is optional, in case it is not defined, we will assume that it is 0.
        offset = int(configuration["addressSpaces"]["offset"], 16) if "offset" in configuration["addressSpaces"].keys() else 0
        # Defining a list of sections that will be excluded (including the objects residing in it) from the analysis based on the value that was loaded from the arguments
        listOfExcludedSections = [".unused_ram"] if self.analyseDebug else SECTIONS_TO_EXCLUDE

        # Importing every mapfile that was found
        for mapfile in configuration["patterns"]["mapfiles"]:
            # Opening the mapfile and reading in its content
            with open(configuration["patterns"]["mapfiles"][mapfile]["associatedFilename"], "r") as mapfile_file_object:
                mapfileContent = mapfile_file_object.readlines()

            # Storing the name of the mapfile
            mapfileName = os.path.split(configuration["patterns"]["mapfiles"][mapfile]["associatedFilename"])[-1]

            # Storing the list of ignored memory areas to this mapfile
            # This will be a necessary parameter for the MapfileProcessor::fillOutMemoryRegionsAndMemoryTypes()
            if "memRegionExcludes" in configuration["patterns"]["mapfiles"][mapfile]:
                memoryRegionsToExcludeFromMapfiles[mapfileName] = configuration["patterns"]["mapfiles"][mapfile]["memRegionExcludes"]

            # If there is a VAS defined for the mapfile, then the addresses found in it are virtual addresses, otherwise they are physical addresses
            mapfileContainsVirtualAddresses = True if "VAS" in configuration["patterns"]["mapfiles"][mapfile] else False
            # Loading the regex pattern that will be used for this mapfile
            regexPatternData = self.__getRegexPattern(defaultRegexPattern, configuration["patterns"]["mapfiles"][mapfile])

            # Analysing the mapfile with the loaded regex line-by-line
            lineNumber = 0
            for line in mapfileContent:
                lineNumber += 1

                # Extracting the components from the line with the regex, if there was no match, we will continue with the next line
                lineComponents = re.search(regexPatternData.pattern, line)
                if lineComponents:
                    # If the section name of this element is in the list that we want to exclude then we can continue with the next line
                    if lineComponents.group(regexPatternData.Groups.section).rstrip() in listOfExcludedSections:
                        continue
                    # If this mapfile contains virtual addresses then we need to translate the address of this element
                    vasName = None
                    vasSectionName = None
                    if mapfileContainsVirtualAddresses:
                        # Name of the Virtual address space to which the elements of this mapfile belongs
                        vasName = configuration["patterns"]["mapfiles"][mapfile]["VAS"]
                        # List of the virtual sections that were belong to this mapfile. The address translation is done with the help of these sections.
                        virtualSectionsOfThisMapfile = configuration["virtualSections"][vasName]
                        # The part of the monolith file that contains the address translation data
                        monolithFileContent = configuration["sortMonolithTabularised"]
                        # Calculating the physical address and getting the name of the virtual section based on which the translation was done
                        physicalAddress, vasSectionName = self.__translateAddress(lineComponents.group(regexPatternData.Groups.origin),
                                                                                  lineComponents.group(regexPatternData.Groups.size),
                                                                                  virtualSectionsOfThisMapfile,
                                                                                  monolithFileContent)
                        # Check whether the address translation failed
                        if physicalAddress is None:
                            warning_section_name = lineComponents.group(regexPatternData.Groups.section).rstrip()
                            warning_object_name = ("::" + lineComponents.group(regexPatternData.Groups.module).rstrip()) if hasattr(regexPatternData.Groups, "module") else ""
                            sc().warning("The address translation failed for the element: \"" + mapfile + "(line " + str(lineNumber) + ")::" +
                                         warning_section_name + warning_object_name + " (size: " + str(int(lineComponents.group(regexPatternData.Groups.size), 16)) + " B)\" of the configID \"" +
                                         configId + "\"!")
                            # We will not store this element and continue with the next one
                            continue
                    # In case the mapfile contains phyisical addresses, no translation is needed, we are just reading the address that is in the mapfile
                    else:
                        physicalAddress = int(lineComponents.group(regexPatternData.Groups.origin), 16) - offset

                    # Determining the addressLength
                    addressLength = int(lineComponents.group(regexPatternData.Groups.size), 16)
                    # Check whether the address is valid
                    if 0 > addressLength:
                        sc().warning("Negative addressLength found.")

                    # Creating the compiler specific data that we will store in the memEntry
                    # This will be a collections.OrderedDict as the MemEntry requires it
                    compilerSpecificData = collections.OrderedDict()
                    compilerSpecificData["DMA"] = (vasName is None)
                    compilerSpecificData["vasName"] = vasName
                    compilerSpecificData["vasSectionName"] = vasSectionName

                    # Creating a MemEntry object from the data that we got from the mapfile
                    memEntry = emma_libs.memoryEntry.MemEntry(configID=configId,
                                                              mapfileName=mapfileName,
                                                              addressStart=physicalAddress,
                                                              addressLength=addressLength,
                                                              sectionName=lineComponents.group(regexPatternData.Groups.section).rstrip(),
                                                              objectName=regexPatternData.getModuleName(lineComponents),
                                                              compilerSpecificData=compilerSpecificData)

                    # Finding the index, where we need to insert the memEntry
                    index = bisect.bisect_right(result, memEntry)
                    # Inserts at index, elements to right will be pushed "one index up"
                    result.insert(index, memEntry)

        # Filling out the memory regions and memory types and ignoring the entries that did not have a match
        super().fillOutMemoryRegionsAndMemoryTypes(result, configuration, True, memoryRegionsToExcludeFromMapfiles)

        return result

    def __getRegexPattern(self, defaultPattern: emma_libs.ghsMapfileRegexes.RegexPatternBase, mapfileEntry):
        """
        Method to determine if the default pattern can be used or if a unique patter is configured
        :param configID: Needed to navigate to the correct configID entry
        :param entry: See param configID
        :return: regex pattern object
        """
        regexPattern = defaultPattern

        if isinstance(defaultPattern, emma_libs.ghsMapfileRegexes.ImageSummaryPattern):
            if UNIQUE_PATTERN_SECTIONS in mapfileEntry.keys():
                sectionPattern = emma_libs.ghsMapfileRegexes.ImageSummaryPattern()  # Create new instance of pattern class when a unique pattern is needed
                # If a unique regex pattern is needed, e.g. when the mapfile has a different format and cannot be parsed with the default pattern
                sectionPattern.pattern = mapfileEntry[UNIQUE_PATTERN_SECTIONS]  # Overwrite default pattern with unique one
                regexPattern = sectionPattern
        elif isinstance(defaultPattern, emma_libs.ghsMapfileRegexes.ModuleSummaryPattern):
            if UNIQUE_PATTERN_OBJECTS in mapfileEntry.keys():
                objectPattern = emma_libs.ghsMapfileRegexes.ModuleSummaryPattern()  # Create new instance of pattern class when a unique pattern is needed
                # If a unique regex pattern is needed, e.g. when the mapfile has a different format and cannot be parsed with the default pattern
                objectPattern.pattern = mapfileEntry[UNIQUE_PATTERN_OBJECTS]    # Overwrite default pattern with unique one
                regexPattern = objectPattern
        else:
            sc().error("Unexpected default regex pattern (" + type(defaultPattern).__name__ + ")!")

        return regexPattern

    def __translateAddress(self, elementVirtualStartAddress, elementSize, virtualSectionsOfThisMapfile, monolithFileContent):
        """
        Calculates the physical address for an element (= section or object).
        The patterns config file can assign a VAS to a mapfile. Every VAS has VAS sections that are defined in the
        virtualSections file. The monolith file contains all the virtual sections of all the VAS-es with data
        based on which the address translation can be done.
        In order to do the translation we loop trough the entries in the monolith file and see whether the entry belongs
        to the VAS of this element. If so, when we need to make sure that the element resides within the virtual section.
        If that is also true, the address translation can be easily done with the data found in the monolith file.
        :param elementVirtualStartAddress: The start address of the element in the VAS
        :param elementSize: The size of the element in bytes
        :param virtualSectionsOfThisMapfile: List of virtual sections that belong to the VAS of the element
        :param monolithFileContent: List of all the virtual sections from the monolith file.
        :return: Physical start address of the element and the name of the virtual section the translation was done with.
        """
        # This are indexes used for accessing the elements of one monolith file entry
        monolithIndexVirtual = 0
        monolithIndexOffset = 2
        monolithIndexSize = 3
        monolithIndexSectionName = 4
        # Converting the received start address and size to decimal
        _, elementVirtualStartAddress = shared_libs.emma_helper.unifyAddress(elementVirtualStartAddress)
        _, elementSize = shared_libs.emma_helper.unifyAddress(elementSize)
        # Setting up the return values with default values
        elementPhysicalStartAddress = None
        virtualSectionName = None

        # We will go trough all the entries in the monolith file to find the virtual section this element belongs to
        for entry in monolithFileContent:
            # If the element belongs to this virtual section we will try to do the address translation
            virtualSectionName = entry[monolithIndexSectionName]
            if virtualSectionName in virtualSectionsOfThisMapfile:
                # Setting up data for the translation (for the end addresses we need to be careful in case we have zero lengths)
                virtualSectionStartAddress = entry[monolithIndexVirtual]
                virtualSectionEndAddress = virtualSectionStartAddress + (entry[monolithIndexSize] - 1) if 0 < entry[monolithIndexSize] else virtualSectionStartAddress
                elementVirtualEndAddress = elementVirtualStartAddress + (elementSize - 1) if 0 < elementSize else elementVirtualStartAddress
                # If the element is contained by this virtual section then we will use this one for the translation
                if virtualSectionStartAddress <= elementVirtualStartAddress <= elementVirtualEndAddress <= virtualSectionEndAddress:
                    addressTranslationOffset = entry[monolithIndexOffset]
                    elementPhysicalStartAddress = elementVirtualStartAddress + addressTranslationOffset
                    # FIXME: maybe it should be displayed/captured if we got more than one matches! (It should never happen but still...) (MSc)
                    break
        return elementPhysicalStartAddress, virtualSectionName
