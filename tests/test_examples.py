import io
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pytest
from tbxtools import TBX

# Gather all *.tbx files for parametric testing
tbx2_paths = list((Path(__file__).parent / 'resources').glob('*.tbx'))


def prettify(xml_string):
    return minidom.parseString(xml_string).toprettyxml()


def are_element_trees_equal(element1, element2):
    """
    Recursively compares two ElementTree elements for equality, including their
    tags, attributes, text, and children.
    """
    if element1.tag != element2.tag:
        return False
    if element1.attrib != element2.attrib:
        return False
    if element1.text != element2.text:
        return False
    if len(element1) != len(element2):
        return False
    return all(
        are_element_trees_equal(c1, c2)
        for c1, c2 in zip(element1, element2)
    )


def filename_from_path(fixture_value):
    return fixture_value.name


@pytest.fixture(params=tbx2_paths, ids=filename_from_path)
def example_conversions(request):
    """
    Return a tuple of:
      - The path to the original *.tbx file
      - The path to the corresponding "correctly converted" file
        (same name, but in 'converted-by-pl' subfolder).
    """
    tbx2_path = request.param
    tbx3_path = tbx2_path.parent / 'converted-by-pl' / tbx2_path.name
    return (tbx2_path, tbx3_path)


def test_compare_with_perl_output_for_example_tbx_files(example_conversions):
    """
    Test that the Python conversion matches the known good conversion.
    """
    tbx2_path, tbx3_path = example_conversions

    # Canonicalize the "correct" TBX output (from the 'converted-by-pl' directory)
    canonical_tbx3_gold_string_from_pl = ET.canonicalize(from_file=str(tbx3_path))

    # Parse and convert the original TBX using TBX class
    tbx2 = TBX.from_file(str(tbx2_path))
    tbx3_string_from_py = tbx2.convert2to3()

    # Canonicalize the resulting string
    canonical_tbx3_string_from_py = ET.canonicalize(tbx3_string_from_py)

    # Check for equality
    assert canonical_tbx3_gold_string_from_pl == canonical_tbx3_string_from_py
