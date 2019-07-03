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

# This file contains the parser and internal data structures for holding the mapfile information.
# The memEntry class stores a mapfile-element.
# The MemoryManager class handles parsing, categorisation and overlap/containment flagging.


import sys

import pypiscout as sc

import shared_libs.emma_helper


class MemEntry:
    def __init__(self, tag, vasName, vasSectionName, section, moduleName, mapfileName, configID, memType, category, addressStart, addressLength=None, addressEnd=None):
        """
        Class storing one memory entry + meta data
        Chose addressLength or addressEnd (one and only one of those two must be given)

        Meta data arguments
        :param tag: [string] Arbitrary name (f.ex. IO_RAM, CM_RAM, ...) in order to distinguish not only by memType
        :param memType: [string] {int, ext} flash, {int, ext} RAM
        :param vasName: [string] name of the corresponding virtual address space (VAS)
        :param vasSectionName [string] name of the vasSection the address translation was done for this element with
        :param section: [string] section name; i.e.: `.text`, `.debug_abbrev`, `.rodata`, ...
        :param moduleName: [string] name of the module
        :param mapfileName: [string] name of the mapfile where we found this entry
        :param configID: [class/string(=members)] defining the micro system
        :param category: [string] = classifier (/ logical grouping of known modules)
        # dma: [bool] true if we can use physical addresses directly (false for address translation i.e. via monolith file)

        Address related arguments
        :param addressStart: [string(hex) or int(dec)] start address
        :param addressLength: [string(hex) or int(dec) or nothing(default = None)] address length
        :param addressEnd: [string(hex) or int(dec) or nothing(default = None)] end address
        """

        # Check if we got hex or dec addresses and decide how to convert those
        # Start address
        self.addressStartHex, self.addressStart = shared_libs.emma_helper.unifyAddress(addressStart)

        if addressLength is None and addressEnd is None:
            sc.error("Either addressLength or addressEnd must be given!")
            sys.exit(-10)
        elif addressLength is None:
            self.__setAddressesGivenEnd(addressEnd)
        elif addressEnd is None:
            self.__setAddressesGivenLength(addressLength)
        else:
            # TODO: Add verbose output here (MSc)
            # TODO: if self.args.verbosity <= 1:
            sc.warning("MemEntry: addressLength AND addressEnd were both given. The addressLength will be used and the addressEnd will be recalculated based on it.")
            self.__setAddressesGivenLength(addressLength)

        self.memTypeTag = tag  # Differentiate in more detail between memory sections/types
        self.vasName = vasName
        self.vasSectionName = vasSectionName
        if vasName is None:  # Probably we can just trust that a VAS name of `None` or "" is give; Anyway this seems more safe to me
            # Direct memory access
            self.dma = True
        else:
            self.dma = False

        self.section = section  # Section type; i.e.: `.text`, `.debug_abbrev`, `.rodata`, ...
        self.moduleName = moduleName  # Module name (obj files, ...)
        self.mapfile = mapfileName  # Shows mapfile association (belongs to mapfile `self.mapfile`)
        self.configID = configID
        self.memType = memType
        self.category = category  # = classifier (/grouping)

        # Flags for overlapping, containment and duplicate
        self.overlapFlag = None
        self.containmentFlag = None
        self.duplicateFlag = None
        self.containingOthersFlag = None
        self.overlappingOthersFlag = None

        # TODO Rename the members addressStartOriginal and addressEndOriginal to addressStartHexOriginal and addressEndHexOriginal respectively (AGK)
        # Original values. These are stored in case the element is moved later. Then the original values will be still accessible.
        self.addressStartOriginal = self.addressStartHex
        self.addressLengthOriginal = self.addressLength
        self.addressLengthHexOriginal = self.addressLengthHex
        self.addressEndOriginal = self.addressEndHex

    def __setAddressesGivenEnd(self, addressEnd):
        # Set addressEnd and addressEndHex
        self.addressEndHex, self.addressEnd = shared_libs.emma_helper.unifyAddress(addressEnd)
        # Calculate addressLength
        self.addressLength = self.addressEnd - self.addressStart + 1
        self.addressLengthHex = hex(self.addressLength)

    def __setAddressesGivenLength(self, addressLength):
        # Set addressLength
        self.addressLengthHex, self.addressLength = shared_libs.emma_helper.unifyAddress(addressLength)
        # Calculate addressEnd
        self.addressEnd = (self.addressStart + self.addressLength - 1) if 0 < self.addressLength else self.addressStart
        self.addressEndHex = hex(self.addressEnd)

    def equalConfigID(self, other):
        """
        Function to evaluate whether two sections have the same config ID
        :return:
        """
        return self.configID == other.configID

    def __lt__(self, other):
        """
        We only want the `<` operator to compare the address start element (dec); nothing else
        Reimplementation of `<` due to bisect comparison (`.insort` uses this operator for insertions;
        can cause errors (TypeError: '<' not supported between instances of 'dict' and 'dict') for same addresses)
        :param other:  x<other calls x.__lt__(other)
        :return: boolean evaluation
        """
        # TODO: Do we want to compare the length (shortest first) when address ist the same? (MSc)
        return self.addressStart < other.addressStart


# TODO : Evaluate, whether we could delete this class and only have the MemEntry (AGK)
class SectionEntry(MemEntry):
    def __init__(self, tag, vasName, vasSectionName, section, moduleName, mapfileName, configID, memType, category, addressStart, addressLength=None, addressEnd=None):
        super().__init__(tag, vasName, vasSectionName, section, moduleName, mapfileName, configID, memType, category, addressStart, addressLength, addressEnd)

    def __eq__(self, other):
        if isinstance(other, MemEntry):
            return ((self.addressStart == other.addressStart) and
                    (self.addressEnd == other.addressEnd)     and
                    (self.section == other.section)           and
                    (self.configID == other.configID)         and
                    (self.mapfile == other.mapfile)           and
                    (self.vasName == other.vasName))
        else:
            raise NotImplementedError("Operator __eq__ not defined between " + type(self).__name__ + " and " + type(other).__name__)

    def __hash__(self):
        return hash((self.addressStart, self.addressEnd, self.section, self.configID, self.mapfile, self.vasName))


# TODO : Evaluate, whether we could delete this class and only have the MemEntry (AGK)
class ObjectEntry(MemEntry):
    def __init__(self, tag, vasName, vasSectionName, section, moduleName, mapfileName, configID, memType, category, addressStart, addressLength=None, addressEnd=None):
        super().__init__(tag, vasName, vasSectionName, section, moduleName, mapfileName, configID, memType, category, addressStart, addressLength, addressEnd)

    def __eq__(self, other):
        if isinstance(other, MemEntry):
            return ((self.addressStart == other.addressStart)      and
                    (self.addressEnd == other.addressEnd)          and
                    (self.section == other.section)                and
                    (self.moduleName == other.moduleName)          and
                    (self.configID == other.configID)              and
                    (self.mapfile == other.mapfile)                and
                    (self.vasName == other.vasName)                and
                    (self.vasSectionName == other.vasSectionName))
        else:
            raise NotImplementedError("Operator __eq__ not defined between " + type(self).__name__ + " and " + type(other).__name__)

    def __hash__(self):
        return hash((self.addressStart, self.addressEnd, self.section, self.moduleName, self.configID, self.mapfile, self.vasName, self.vasSectionName))
