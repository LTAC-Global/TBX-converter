#!/usr/bin/env python3
"""
TBX Converter

This script converts TBX-Basic, TBX-Min, and TBX-Default files
to the newest TBX standard. It can be run in an interactive mode
or silently with no user prompts.

Usage:
    python tbx_converter.py [options] <input_file>

Options:
    -s, --silent       Run silently with no user prompts
"""

import argparse
import io
import json
import sys
from typing import List
import urllib.request
import xml.etree.ElementTree as ET


def fetch_schemas(dialect: str) -> dict:
    """
    Fetch a dictionary of schema references from http://validate.tbxinfo.net/dialects/<dialect>.
    If 'dialect' is None or the call fails, returns an empty dict.

    :param dialect: TBX dialect to look up (e.g., "TBX-Basic", "TBX-Min", etc.)
    :return: Dictionary with keys like 'dca_rng', 'dca_sch', 'dct_nvdl' if available.
    """
    # TBX → TBX-Basic, per the older logic
    if dialect == "TBX":
        dialect = "TBX-Basic"

    url = f"http://validate.tbxinfo.net/dialects/{dialect}"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"})
    with urllib.request.urlopen(req) as response:
        data_str = response.read().decode("utf-8")
    data_list = json.loads(data_str)
    print('TEST', data_list)

    if data_list and isinstance(data_list, list):
        item = data_list[0]
        return {
            "dca_rng": item.get("dca_rng"),
            "dca_sch": item.get("dca_sch"),
            "dct_nvdl": item.get("dct_nvdl"),
        }


def build_parent_map(root: ET.Element) -> dict:
    """
    Build a mapping of each element to its parent so that we can remove or reattach elements.

    :param root: Root of the parsed XML tree.
    :return: Dictionary with {child_element: parent_element} relationships.
    """
    parent_map = {}
    for parent in root.iter():
        for child in list(parent):
            parent_map[child] = parent
    return parent_map


def find_ancestor_with_tag(element, tag, parent_map):
    """
    Traverse up parent_map until we find an ancestor whose .tag == tag.
    Returns that ancestor element or None if not found.
    """
    current = element
    while current in parent_map:
        current = parent_map[current]
        if current.tag == tag:
            return current
    return None


def transform_tbx(root: ET.Element, parent_map: dict):
    """
    Transform the TBX XML to the latest standard by renaming and removing elements.
    This function recurses bottom-up, so child elements are transformed before parents.

    :param root: Current XML element to process.
    :param parent_map: Dictionary mapping elements to their parents.
    """
    for child in list(root):
        transform_tbx(child, parent_map)

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

    # 2) If <term> is inside <ntig> (which may become <termSec>), lift <term> up one level
    if old_tag == "term":
        ntig_ancestor = find_ancestor_with_tag(root, "ntig", parent_map)
        if ntig_ancestor is not None:
            # First remove <term> from its immediate parent
            immediate_parent = parent_map.get(root)
            if immediate_parent is not None:
                immediate_parent.remove(root)
            # Then re-append it directly under the <ntig> ancestor
            ntig_ancestor.insert(0, root)
        return

    # 3) If <TBX>, rename to <tbx>, rename 'dialect' -> 'type', set style='dct'
    if old_tag == "TBX":
        root.tag = "tbx"
        if "dialect" in root.attrib:
            dialect_val = root.attrib.pop("dialect")
            root.set("type", dialect_val)
        root.set("style", "dct")
        return

    # 4) If <martif>, rename to <tbx>, set style='dca', and if type="TBX", make it "TBX-Basic"
    if old_tag == "martif":
        root.tag = "tbx"
        if root.get("type") == "TBX":
            root.set("type", "TBX-Basic")
        root.set("style", "dca")
        return

    # 5) <tbxMin> doesn't get renamed; original code tracks its dialect, but we don't do anything else.

    # 6) Rename any other tags in rename_map
    if old_tag in rename_map:
        root.tag = rename_map[old_tag]


def convert_tbx(input_string: str, silent: bool = True, schemas_js=None) -> str:
    """
    Main routine that:
      1) Parses the TBX string.
      2) Transforms tags/attributes to the latest TBX standard.
      3) Optionally prompts user to save or prints to stdout.
      4) Inserts schema references (xml-model processing instructions) if found.

    :param input_file: Path to the TBX file to convert.
    :param silent: If True, runs without user prompts.
    """
    # Parse the XML
    root = ET.fromstring(input_string)
    tree = ET.ElementTree(root)

    # Build the parent map so we can remove or reattach elements
    parent_map = build_parent_map(root)

    # Perform transformations
    transform_tbx(root, parent_map)

    # Add namespace to the root (as per new TBX standard)
    root.set("xmlns", "urn:iso:std:iso:30042:ed-2")

    if schemas_js is None:
        # Fetch dialect from the new <tbx> root, if present
        dialect = root.get("type", None)
        schemas = fetch_schemas(dialect)
    else:
        # Assuming 'schemas' is a pyodide.ffi.JsProxy
        schemas = schemas_js.to_py()  # Convert JsProxy to python dictionary

    # We'll hold processing instructions in a list
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
    # If you wanted to insert dct_nvdl or other references, do so here similarly.

    output_string = elementtree_to_string(processing_instructions, tree)
    return output_string


def elementtree_to_string(processing_instructions: List[str], tree: ET.ElementTree, encoding='unicode', xml_declaration=False) -> str:
    """
    Convert an ElementTree to a valid XML string with an XML declaration.
    """
    # Start with processing instructions
    output_xml = ''
    for pi in processing_instructions:
        output_xml += f'{pi}\n'

    # Use in-memory text buffer to get string of XML tree
    buffer = io.StringIO()
    ET.indent(tree)
    tree.write(buffer, encoding=encoding, xml_declaration=xml_declaration)

    return output_xml + buffer.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert TBX-Basic, TBX-Min, and TBX-Default files to the newest TBX standard."
    )
    parser.add_argument(
        "input_file",
        help="Path to the TBX file to convert."
    )
    parser.add_argument(
        "-s", "--silent",
        action="store_true",
        help="Run silently (no user prompts)."
    )
    args = parser.parse_args()

    print("Starting file analysis:")
    with open(args.input_file, encoding='utf8') as f:
        input_str = f.read()
    output_string = convert_tbx(input_str, silent=args.silent)
    # Non-silent mode: prompt the user
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
        # Silent mode: just output to stdout
        print(output_string)
    print("\nThe conversion is complete!", file=sys.stderr)
