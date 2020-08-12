import os
from click.testing import CliRunner
from hls_browse_imagery_creator.granule_to_gibs import granule_to_gibs
from hls_browse_imagery_creator.create_gibs_tile import create_gibs_tile
from hls_browse_imagery_creator.create_gibs_metadata import create_gibs_metadata


current_dir = os.path.dirname(__file__)
data_dir = os.path.join(current_dir, "data")
output_dir = os.path.join(current_dir, "output")
merge_dir = os.path.join(current_dir, "merge")
os.mkdir(output_dir)
os.mkdir(merge_dir)
basename = "HLS.S30.T01LAH.2020097T222759.v1.5"
gibsid = "320071"
gibstile = os.path.join(merge_dir, "HLS.S30.2020097.320071.v1.5.tif")


def test_granule_to_gibs():
    runner = CliRunner()
    result = runner.invoke(granule_to_gibs, [data_dir, output_dir, basename])
    print(result.exception)
    assert result.exit_code == 0


def test_create_gibs_tile():
    runner = CliRunner()
    result = runner.invoke(create_gibs_tile, [output_dir, gibstile, gibsid])
    print(result.exception)
    assert result.exit_code == 0


def test_create_gibs_metadata():
    gibsmetadata = os.path.join(data_dir, "HLS.S30.2020097.320071.v1.5.xml")
    runner = CliRunner()
    result = runner.invoke(create_gibs_metadata, [
        output_dir,
        gibsmetadata,
        gibsid,
        gibstile,
        "2020097"
    ])
    print(result.exception)
    assert result.exit_code == 0
