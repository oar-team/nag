from subprocess import run

import pytest
from click.testing import CliRunner

from nag.main import Nag, cli, get_src_value


@pytest.fixture(scope="function", autouse=True)
def copy_data(tmp_path):
    print(f"Copy data tp {tmp_path}")
    cmd = f"cp -r data {tmp_path}/"
    run(cmd, shell=True)


def test_src_value(tmp_path):
    ctx = Nag()
    get_src_value(ctx, f"{tmp_path}/data/default-prrte.nix")
    assert ctx.gitlab.git_url() == "git@gitlab.inria.fr:dynres/dyn-procs/prrte.git"


def _test_update(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["update" f"{tmp_path}/data/default.nix"],
        catch_exceptions=False,
    )

    print(result.output)


def test_set(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["update" f"{tmp_path}/data/default.nix"],
        catch_exceptions=False,
    )
    print(result.output)
