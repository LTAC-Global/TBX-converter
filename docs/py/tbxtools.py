#!/usr/bin/env python3
"""
TBX Converter

This script defines a TBX class that can convert TBX-Basic, TBX-Min, and TBX-Default files
to the newest TBX standard. The TBX class can be used programmatically or invoked via
command-line:

Usage:
    python tbxtools.py [options] <input_file>

Options:
    -s, --silent       Run silently (no user prompts)
"""

import argparse
import io
import json
import re
import sys
from typing import List
import urllib.request
import xml.etree.ElementTree as ET

check_version_messages = {
    "not_xml":        "This file does not appear to be an XML or TBX file.",
    "bad_ext":        "This file does not appear to have the correct file extension.",
    "malformed_xml":  "File does not appear to be well-formed XML.",
    "malformed_tbx":  "File appears to be well-formed XML, but does not appear to be TBX.",
    "invalid_tbx":    "File claims to be TBX, but does not appear valid.",
    "v2":             "File appears to be a 2008 TBX (v2) file.",
    "bad_v3":         "File appears to be a 2019 TBX (v3) file, but has no valid dialect.",
    "v3":             "File appears to be a 2019 TBX (v3) file with dialect:",
}


class TBX:
    """
    A class that parses and transforms TBX XML strings to the latest standard.
    """

    def __init__(self, input_string: str):
        """
        Store the original XML/TBX string in this instance.
        :param input_string: The raw TBX (XML) content as a string.
        """
        self.orig_str = input_string

    @classmethod
    def from_file(cls, filepath: str) -> "TBX":
        """
        Create a TBX object by reading the contents of 'filepath'.
        :param filepath: Path to a TBX XML file.
        :return: A new TBX instance storing that file's text.
        """
        with open(filepath, encoding='utf-8') as f:
            data = f.read()
        return cls(data)

    @staticmethod
    def fetch_schemas(dialect: str) -> dict:
        """
        Fetch a dictionary of schema references from http://validate.tbxinfo.net/dialects/<dialect>.
        If 'dialect' is None or the call fails, returns an empty dict.

        :param dialect: e.g., "TBX-Basic" or "TBX-Min"
        :return: Dictionary with keys like 'dca_rng', 'dca_sch', 'dct_nvdl' if available.
        """
        # TBX -> TBX-Basic, per older logic
        if dialect == "TBX":
            dialect = "TBX-Basic"

        url = f"http://validate.tbxinfo.net/dialects/{dialect}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req) as response:
            data_str = response.read().decode("utf-8")
        data_list = json.loads(data_str)
        item = data_list[0]
        return {
            "dca_rng": item.get("dca_rng"),
            "dca_sch": item.get("dca_sch"),
            "dct_nvdl": item.get("dct_nvdl"),
        }

    @staticmethod
    def build_parent_map(root: ET.Element) -> dict:
        """
        Build a mapping of each element to its parent so that we can remove or reattach elements.

        :param root: Root of the parsed XML tree
        :return: Dictionary with {child_element: parent_element} relationships.
        """
        parent_map = {}
        for parent in root.iter():
            for child in list(parent):
                parent_map[child] = parent
        return parent_map

    @staticmethod
    def find_ancestor_with_tag(element: ET.Element, tag: str, parent_map: dict) -> ET.Element:
        """
        Traverse up 'parent_map' until we find an ancestor whose .tag == tag.
        Returns that ancestor element or None if not found.
        """
        current = element
        while current in parent_map:
            current = parent_map[current]
            if current.tag == tag:
                return current
        return None

    def transform_tree_2to3(self, root: ET.Element, parent_map: dict):
        """
        Transform the TBX XML to the latest standard by renaming/removing elements.
        This function recurses bottom-up, so child elements are transformed before parents.

        :param root: Current XML element to process
        :param parent_map: Dictionary mapping elements to their parents
        """
        for child in list(root):
            self.transform_tree_2to3(child, parent_map)

        old_tag = root.tag

        # Define tag renames
        rename_map = {
            "entry": "conceptEntry",
            "langGroup": "langSec",
            "termGroup": "termSec",
            "martifHeader": "tbxHeader",
            "bpt": "sc",
            "ept": "ec",
            "termEntry": "conceptEntry",
            "langSet": "langSec",
            "tig": "termSec",
            "termCompList": "termCompSec",
            "refObjectList": "refObjectSec",
            "termComptListSpec": "termCompSecSpec",
            "ntig": "termSec",
        }

        # 1) Remove <termGrp> entirely
        if old_tag == "termGrp":
            parent = parent_map.get(root)
            if parent is not None:
                parent.remove(root)
            return

        # 2) If <term> is inside <ntig>, lift <term> up one level
        if old_tag == "term":
            ntig_ancestor = self.find_ancestor_with_tag(root, "ntig", parent_map)
            if ntig_ancestor is not None:
                # Remove <term> from immediate parent
                immediate_parent = parent_map.get(root)
                if immediate_parent is not None:
                    immediate_parent.remove(root)
                # Insert as first child under <ntig>
                ntig_ancestor.insert(0, root)
            return

        # 3) If <TBX>, rename -> <tbx>, 'dialect' -> 'type', set style='dct'
        if old_tag == "TBX":
            root.tag = "tbx"
            if "dialect" in root.attrib:
                dialect_val = root.attrib.pop("dialect")
                root.set("type", dialect_val)
            root.set("style", "dct")
            return

        # 4) If <martif>, rename -> <tbx>, set style='dca', if type="TBX" => "TBX-Basic"
        if old_tag == "martif":
            root.tag = "tbx"
            if root.get("type") == "TBX":
                root.set("type", "TBX-Basic")
            root.set("style", "dca")
            return

        # 5) <tbxMin> is not renamed; original code tracks dialect, not used here.

        # 6) Rename from rename_map
        if old_tag in rename_map:
            root.tag = rename_map[old_tag]

    @staticmethod
    def elementtree_to_string(
        processing_instructions: List[str],
        tree: ET.ElementTree,
        encoding: str = "unicode",
        xml_declaration: bool = False,
    ) -> str:
        """
        Convert an ElementTree to a valid XML string, optionally adding an XML declaration,
        plus any leading processing instructions.
        """
        # Start with processing instructions
        output_xml = ""
        for pi in processing_instructions:
            output_xml += f"{pi}\n"

        # Use in-memory text buffer to get string of the XML tree
        buffer = io.StringIO()
        # pretty-print indentation (Python 3.9+)
        ET.indent(tree)
        tree.write(buffer, encoding=encoding, xml_declaration=xml_declaration)
        return output_xml + buffer.getvalue()

    def convert2to3(self, silent: bool = True, schemas_js=None) -> str:
        """
        1) Parse self.orig_str into XML.
        2) Transform to latest TBX standard.
        3) Optionally fetch or use existing schemas to insert processing instructions.
        4) Return final XML string.

        :param silent: If False, you'd do interactive prompts (omitted here).
        :param schemas_js: A structure from JS (Pyodide) or None
        :return: The converted TBX as a string
        """
        # Parse
        root = ET.fromstring(self.orig_str)
        tree = ET.ElementTree(root)

        # Build parent map
        parent_map = self.build_parent_map(root)

        # Transform
        self.transform_tree_2to3(root, parent_map)

        # Add namespace
        root.set("xmlns", "urn:iso:std:iso:30042:ed-2")

        # Possibly fetch schemas or use what's passed in
        if schemas_js is None:
            # Check dialect from root
            dialect = root.get("type")
            schemas = self.fetch_schemas(dialect)
        else:
            # If we assume schemas_js is a dict or a Pyodide JsProxy
            try:
                # If it's a Pyodide JsProxy, convert to a python dict
                schemas = schemas_js.to_py()
            except AttributeError:
                # Else, assume it's already a normal dict
                schemas = schemas_js

        # Build processing instructions
        processing_instructions = []
        if "dca_rng" in schemas and schemas["dca_rng"]:
            processing_instructions.append(
                f'<?xml-model href="{schemas["dca_rng"]}" '
                'type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>'
            )
        if "dca_sch" in schemas and schemas["dca_sch"]:
            processing_instructions.append(
                f'<?xml-model href="{schemas["dca_sch"]}" '
                'type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>'
            )
        # Additional references (dct_nvdl, etc.) can be added as needed.

        # Return final string
        return self.elementtree_to_string(processing_instructions, tree)

    def check_tbx_version(self, extension: str = "") -> str:
        """
        Attempt to replicate the logic and messages from main.pl as closely as possible.
        The original main.pl performed:
        1) Check file extension => "bad_ext" if not matching (xml|tbxm?)
        2) Check if first non-empty line has "<?xml" => "not_xml"
        3) Parse with XML::Twig => "malformed_xml" if parse fails
        4) If parse succeeds but root tag isn't recognized => "malformed_tbx" or "invalid_tbx"
        5) twig_handlers:
            - <TBX> => if dialect="TBX-Min" => "v2" else => "invalid_tbx"
            - <martif> => "v2"
            - <tbx> => if type starts with "TBX-" => "v3" (with dialect) else => "bad_v3"
            - <MARTIF> => "invalid_tbx"
        """


        # 1) Check the extension if provided. (In main.pl: exit $messages{'bad_ext'} if not match.)
        #    We approximate this by checking extension param, if present:
        if extension:
            if not re.search(r'\.(xml|tbxm?)$', extension, re.IGNORECASE):
                return check_version_messages["bad_ext"]

        # 2) Check if first non-empty line contains "<?xml". (main.pl reads the file and checks.)
        #    Since we only have self.orig_str, let's look at the first non-blank line:
        lines = self.orig_str.splitlines()
        for line in lines:
            if line.strip():  # first non-empty line
                if "<?xml" not in line:
                    return check_version_messages["not_xml"]
                break
        else:
            # If we never found a non-empty line, treat it as no content => not_xml
            return check_version_messages["not_xml"]

        # 3) Attempt to parse. If parse fails => "malformed_xml"
        try:
            root = ET.fromstring(self.orig_str)
        except ET.ParseError:
            return check_version_messages["malformed_xml"]
        root_tag = re.sub(r'^{[^}]*}', '', root.tag)

        # 4) Now replicate the twig_handlers:
        #    <TBX>, <martif>, <tbx>, <MARTIF>
        #    If none of these match => "malformed_tbx"
        # Because the original twig_handlers are case-sensitive, let's check exactly:
        # However, main.pl also had an uppercase 'MARTIF' => "invalid_tbx".
        # We'll do direct matches plus defaults if not recognized.
        if root_tag == "TBX":
            dialect = root.attrib.get("dialect", "")
            if dialect == "TBX-Min":
                return check_version_messages["v2"]
            else:
                return check_version_messages["invalid_tbx"]
        elif root_tag == "martif":
            return check_version_messages["v2"]

        elif root_tag == "tbx":
            # if type=~ /^TBX-.*?/ => v3 (with dialect), else => bad_v3
            tbx_type = root.attrib.get("type", "")
            print(f"{tbx_type= }")
            if re.match(r"^TBX-", tbx_type):
                # e.g. "File appears to be a 2019 TBX (v3) file with dialect: 'TBX-Basic'"
                return f"{check_version_messages['v3']} '{tbx_type}'"
            else:
                return check_version_messages["bad_v3"]

        elif root_tag == "MARTIF":
            return check_version_messages["invalid_tbx"]

        else:
            # If none of the recognized root tags matched => "malformed_tbx"
            return check_version_messages["malformed_tbx"]

if __name__ == "__main__":
    # Command-line interface
    parser = argparse.ArgumentParser(
        description="Convert TBX-Basic, TBX-Min, and TBX-Default files to the newest TBX standard."
    )
    parser.add_argument(
        "input_file", help="Path to the TBX file to convert."
    )
    parser.add_argument(
        "-s", "--silent", action="store_true",
        help="Run silently (no user prompts)."
    )
    args = parser.parse_args()

    print("Starting file analysis:")

    # Create TBX instance from file
    tbx_obj = TBX.from_file(args.input_file)
    output_string = tbx_obj.convert2to3(silent=args.silent)

    # If not silent, we can do a minimal prompt to replicate old logic
    if not args.silent:
        ans = input("Would you like to save the output to a file? Press (y/n).\n").strip().lower()
        if ans == "y":
            output_file = "converted_file.tbx"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output_string)
            print(f"Output saved to {output_file}", file=sys.stderr)
        else:
            print(output_string)
    else:
        # Silent mode -> print result to stdout
        print(output_string)

    print("\nThe conversion is complete!", file=sys.stderr)
