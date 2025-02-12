from tbxtools import TBX


def test_fetch_schemas():
    schemas = TBX.fetch_schemas('TBX')
    assert schemas == {'dca_rng': 'https://raw.githubusercontent.com/LTAC-Global/TBX-Basic_dialect/master/DCA/TBXcoreStructV03_TBX-Basic_integrated.rng',
                       'dca_sch': 'https://raw.githubusercontent.com/LTAC-Global/TBX-Basic_dialect/master/DCA/TBX-Basic_DCA.sch',
                       'dct_nvdl': 'https://raw.githubusercontent.com/LTAC-Global/TBX-Basic_dialect/master/DCT/TBX-Basic.nvdl'}
