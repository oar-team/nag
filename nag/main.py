import re
from dataclasses import dataclass
from subprocess import check_output

import click


@dataclass
class GitLab:
    domain: str
    group: str
    owner: str
    repo: str
    rev: str
    sha256: str


@dataclass
class Github:
    domain: str
    group: str
    owner: str
    repo: str
    rev: str
    sha256: str

    def git_url(self) -> str:
        url = f"git@{self.domain}:{self.group}/{self.owner}/{self.repo}.git"
        print(f"git_url: {url}")
        return url

    def https_url(self) -> str:
        url = f"https://{self.domain}/{self.group}/{self.owner}/{self.repo}"
        print(f"git_url: {url}")
        return url


class Nag(object):
    def __init__(self, debug=False):
        self.debug = debug
        self.isGitLab = False
        self.isGithub = False
        self.isSrcPath = False
        self.src = ""
        self.gitlab = None
        self.github = None


def get_last_commit(git_url):
    commit_lst = check_output(["git", "ls-remote", git_url]).decode()
    return commit_lst.split()[0]


def nix_prefetch_git(https_url, commit):
    result = check_output(["nix-prefetch-git", https_url, commit]).decode()
    sha256 = re.search("sha256-.+=", result).group(0)
    print(sha256)
    return sha256


def get_attr_val(attr_val, filename):
    print(f">>> {attr_val}")

    attr = re.search(r"\w+", attr_val[0]).group(0)
    m = re.search('".+"', attr_val[1])
    if m:
        val = m.group(0)[1:-1]
    else:
        # need get a new attr's value
        subattr = re.search(r"\w+", attr_val[1]).group(0)
        val_raw = check_output(["nix-editor", filename, subattr])
        val = re.search('".+"', val_raw.decode()).group(0)[1:-1]
    return (attr, val)


def get_src_value(ctx, filename):
    src_raw = check_output(["nix-editor", filename, "src"])

    ctx.obj.src = src_raw.decode()

    attrset = {}
    # Function or not function
    src_value = re.split("{|}|;|\n", ctx.obj.src)

    v = src_value[0].split("=")
    if re.match(r"^\W*fetchFromGitLab\W*$", v[0]):
        ctx.obj.isGitLab = True
    if re.match(r"^\W*fetchFromGithub\W*$", v[0]):
        ctx.obj.isGithub = True
    elif re.match(".*/.*", v[0]):
        print("It's Path")
        ctx.obj.isSrcPath = True
        return

    for s in src_value[1:]:
        # print(f"v... {v}")
        # skip comment and blan lines
        v = s.split("=", 1)
        if v[0] and not re.match(r"^ *#.*|\W+$", v[0]):
            # if re.match('^\W*fetchFromGitLab\W*$', v[0]):
            #     print("Fetch from GitLab detected")
            #     isGitLab = True
            # else:
            key, val = get_attr_val(v, filename)
            attrset[key] = val

    if ctx.obj.isGitLab:
        ctx.obj.gitlab = GitLab(**attrset)
    elif ctx.obj.isGithub:
        ctx.obj.github = Github(**attrset)
    print(f"{attrset}")


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, debug):
    ctx.obj = Nag(debug)


@cli.command()
@click.argument("filename", type=click.Path(exists=True))
@click.pass_context
def update(ctx, filename):

    get_src_value(ctx, filename)

    if not ctx.obj.isSrcPath:
        if ctx.obj.isGitLab:
            git_url = ctx.obj.gitlab.git_url()
            https_url = ctx.obj.gitlab.https_url()
            commit_prev = ctx.obj.gitlab.rev
            sha256_prev = ctx.obj.gitlab.sha256
        else:
            print("Only Gitlab is supported (ATM)")
            exit(1)
        commit = get_last_commit(git_url)
        if commit == commit_prev:
            print("Nothing to do, no more recent commit")
            exit(0)
        sha256 = nix_prefetch_git(https_url, commit)
        print(f"New commit: {commit}, new sha256 {sha256}")
        new_src = ctx.obj.src.replace(commit_prev, commit).replace(sha256_prev, sha256)

        check_output(["nix-editor", "-i", "-f", "-v", new_src, filename, "src"])


@cli.command()
@click.argument("filename", type=click.Path(exists=True), nargs=1)
@click.argument("value", type=click.STRING, nargs=1)
@click.argument("attribute", type=click.STRING, default="src")
@click.pass_context
def set_stash(ctx, filename, attribute, value):
    # Retrieve attribute value
    prev_value_raw = check_output(["nix-editor", filename, attribute])
    # Save attribute for eventual revert action in nag_{attribute}
    check_output(
        [
            "nix-editor",
            "-i",
            "-f",
            "-v",
            prev_value_raw.decode(),
            filename,
            f"nag_{attribute}",
        ]
    )
    # Set attribute
    check_output(["nix-editor", "-i", "-f", "-v", value, filename, attribute])


@cli.command()
@click.argument("filename", type=click.Path(exists=True), nargs=1)
@click.argument("attribute", type=click.STRING, default="src")
@click.pass_context
def revert(ctx, filename, attribute):
    # Retrieve stashed value
    stashed_value_raw = check_output(["nix-editor", filename, f"nag_{attribute}"])

    # Reset attribue
    check_output(
        [
            "nix-editor",
            "-i",
            "-f",
            "-v",
            stashed_value_raw.decode(),
            filename,
            attribute,
        ]
    )

    # Remove nag_{attribute}
    check_output(["nix-editor", "-i", "-d", filename, f"nag_{attribute}"])


if __name__ == "__main__":
    cli()
