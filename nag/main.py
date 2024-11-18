import json
import re
from subprocess import check_output

import click


class GitLab:
    domain: str
    group: str
    owner: str
    repo: str
    rev: str
    hash: str

    def __init__(self, attrset):
        self.domain = attrset["domain"]
        if "group" in attrset:
            self.group = attrset["group"]
        else:
            self.group = None
        self.owner = attrset["owner"]
        self.repo = attrset["repo"]
        self.rev = attrset["rev"]
        self.hash = attrset["hash"] if "hash" in attrset else attrset["sha256"]

    def git_url(self) -> str:
        if self.group:
            url = f"git@{self.domain}:{self.group}/{self.owner}/{self.repo}.git"
        else:
            url = f"git@{self.domain}:{self.owner}/{self.repo}.git"
        print(f"git_url: {url}")
        return url

    def https_url(self) -> str:
        if self.group:
            url = f"https://{self.domain}/{self.group}/{self.owner}/{self.repo}"
        else:
            url = f"https://{self.domain}/{self.owner}/{self.repo}"
        print(f"git_url: {url}")
        return url


class Github:
    owner: str
    repo: str
    rev: str
    hash: str

    def __init__(self, attrset):
        self.owner = attrset["owner"]
        self.repo = attrset["repo"]
        self.rev = attrset["rev"]
        self.hash = attrset["hash"] if "hash" in attrset else attrset["sha256"]

    def git_url(self) -> str:
        url = f"git@github.com:{self.owner}/{self.repo}.git"
        print(f"git_url: {url}")
        return url

    def https_url(self) -> str:
        url = f"https://github.com/{self.owner}/{self.repo}"
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


def get_last_commit(git_url, head=None):
    commit_lst = check_output(["git", "ls-remote", git_url]).decode()
    if head:
        for line in commit_lst.split("\n"):
            col = line.split()
            if col[1] == f"refs/heads/{head}":
                return col[0]
        raise Exception(f"Head: {head} not found")
    else:
        return commit_lst.split()[0]


def nix_prefetch_git(https_url, commit):
    result = check_output(["nix-prefetch-git", "--quiet", https_url, commit]).decode()
    if result:
        res = json.loads(result)
        if "hash" in res:
            print(res["hash"])
            return res["hash"]

    click.echo("Failed to obtain hash", err=True)
    exit(1)
    return


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
    if re.match(r"^\W*fetchFromGitHub\W*$", v[0]):
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
        ctx.obj.gitlab = GitLab(attrset)
    elif ctx.obj.isGithub:
        ctx.obj.github = Github(attrset)
    print(f"{attrset}")


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, debug):
    ctx.obj = Nag(debug)


@cli.command()
@click.option(
    "--head",
    type=click.STRING,
    default=None,
    help="specify git head to consider (ex branch)",
)
@click.argument("filename", type=click.Path(exists=True))
@click.pass_context
def update(ctx, filename, head):

    get_src_value(ctx, filename)

    if not ctx.obj.isSrcPath:
        if ctx.obj.isGitLab:
            # git_url = ctx.obj.gitlab.git_url()
            https_url = ctx.obj.gitlab.https_url()
            commit_prev = ctx.obj.gitlab.rev
            hash_prev = ctx.obj.gitlab.hash
        elif ctx.obj.isGithub:
            # git_url = ctx.obj.github.git_url()
            https_url = ctx.obj.github.https_url()
            commit_prev = ctx.obj.github.rev
            hash_prev = ctx.obj.github.hash
        else:
            print("Only Gitlab and Gihub are supported (ATM)")
            exit(1)
        # TODO add fallback to git_url if https_url use failed
        # commit = get_last_commit(git_url, head)
        commit = get_last_commit(https_url, head)
        if commit == commit_prev:
            print("Nothing to do, no more recent commit")
            exit(0)
        hash = nix_prefetch_git(https_url, commit)
        print(f"New commit: {commit}, new hash {hash}")
        new_src = ctx.obj.src.replace(commit_prev, commit).replace(hash_prev, hash)

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
