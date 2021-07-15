import os
from click.testing import CliRunner
from hls_browse_imagery_creator.granule_to_gibs import granule_to_gibs


current_dir = os.path.dirname(__file__)
data_dir = os.path.join(current_dir, "data")
basename = "HLS.S30.T01LAC.2021183T221941.v1.5"
gibsid = "320066"


def test_granule_to_gibs(tmpdir):
    runner = CliRunner()
    result = runner.invoke(granule_to_gibs, [data_dir, tmpdir.strpath, basename])
    print(result.exception)
    assert result.exit_code == 0
    assert os.path.isfile(os.path.join(
        tmpdir.strpath, gibsid, "{}_{}.tif".format(basename, gibsid))
    )

    assert os.path.isfile(os.path.join(
        tmpdir.strpath, gibsid, "{}_{}.xml".format(basename, gibsid))
    )
