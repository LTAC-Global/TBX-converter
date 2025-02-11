import io
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pytest

from tbxtools import convert_tbx
from tbxtools import elementtree_to_string

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
    return all(are_element_trees_equal(child1, child2)
               for child1, child2 in zip(element1, element2))


def filename_from_path(fixture_value):
    return fixture_value.name


@pytest.fixture(params=tbx2_paths, ids=filename_from_path)
def example_conversions(request):
    """Return tuple of paths (src, correctly_converted) from example tbx files."""
    tbx2_path = request.param
    tbx3_path = tbx2_path.parent / 'converted-by-pl' / tbx2_path.name
    return (tbx2_path, tbx3_path)


def test_compare_with_perl_output_for_example_tbx_files(example_conversions):
    tbx2_path, tbx3_path = example_conversions
    canonical_tbx3_gold_string_from_pl = ET.canonicalize(from_file=str(tbx3_path))
    with tbx2_path.open() as f:
        tbx2_string = f.read()
    tbx3_string_from_py = convert_tbx(tbx2_string)
    canonical_tbx3_string_from_py = ET.canonicalize(tbx3_string_from_py)
    with open(f"/tmp/pytest/gold-{tbx2_path.name}", 'w') as f:
        f.write(canonical_tbx3_gold_string_from_pl)
    with open(f"/tmp/pytest/pred-{tbx2_path.name}", 'w') as f:
        f.write(canonical_tbx3_string_from_py)

    # assert are_element_trees_equal(ET.parse(str(tbx3_path)).getroot(), tbx3_from_py.getroot())
    assert canonical_tbx3_gold_string_from_pl == canonical_tbx3_string_from_py
