import requests
import subprocess
import time
import argparse
import base64
import logging

sep = "@@__CHGLOG__@@"
delim = "@@__CHGLOG_DELIMITER__@@"
# ha = "HASH:%H\t%h"
ha = "%H"
au = "AUTHOR:%an\t%ae\t%at"
co = "COMMITER:%cn\t%ce\t%ct"
# su = "SUBJECT:%s"
su = "%s"
bo = "BODY:%b"


class Commit:

    hash_: str
    subject_: str
    categories_: list
    pr_: str = ""
    token: str

    def __init__(self, hash_: str, sub_cat_: str, token: str = None):
        self.hash_ = hash_.strip()
        cat_sub_split = sub_cat_.split(":", 1)
        try:
            self.subject_ = ":".join(cat_sub_split[1:]).strip()
            self.categories_ = cat_sub_split[0].split("/")
        except IndexError:
            logging.warn("Non semantic commit")
            self.subject_ = cat_sub_split[0]
            self.categories_ = ["none"]
        self.token = token
        self.pr_ = self.get_pr_link()

    def get_pr_link(self):
        header = None
        if self.token:
            auth = base64.b64encode(bytearray(self.token, "utf-8")).decode("utf-8")
            header = {"Authorization": f"Basic {auth}"}
        response = requests.get(
            f"https://api.github.com/search/issues?q={self.hash_}", headers=header
        )
        for item in response.json().get("items", []):
            if item.get("state", "open") == "closed":
                return item.get("pull_request", {}).get("html_url")

    def __str__(self):
        return f"{self.subject_} {self.pr_}"


def git_log(ref1, ref2):
    out = subprocess.run(
        [
            "git",
            "log",
            f"{ref1}..{ref2}",
            "--no-decorate",
            "--pretty={}{}".format(sep, delim.join([ha, su])),
        ],
        stdout=subprocess.PIPE,
    ).stdout.decode("UTF-8")
    return out


def git_latest_two_tags():
    out = subprocess.run(
        ["git", "tag", "--sort=version:refname"],
        stdout=subprocess.PIPE,
    ).stdout.decode("UTF-8")
    tags = [tag for tag in out.split("\n") if tag]
    if len(tags) < 2:
        raise Exception("Needs at least two tags for changelog")
    logging.warn(f"Generating changelog from {tags[-2]} to {tags[-1]}")
    return tags[-2:]


def create_changelog(version, change_dict):
    body = ""

    for key in change_dict:
        body += "### " + key.capitalize() + "\n"
        for item in change_dict[key]:
            body += "- " + item + "\n"
        body += "\n"

    return f"## {version}\n{body}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ref1",
        metavar="ref1",
        type=str,
        help="source version from which to create the changelog",
    )
    parser.add_argument(
        "--ref2",
        metavar="ref2",
        type=str,
        help="target version to which to create the changelog",
    )
    parser.add_argument(
        "--token",
        metavar="token",
        type=str,
        help="API token in the form of `<username>:<personal-access-token>`",
    )
    args = parser.parse_args()

    if args.ref1 and args.ref2:
        log_hist = git_log(args.ref1, args.ref2)
        headerVersion = args.ref2
    elif not args.ref1 and not args.ref2:
        latest_tags = git_latest_two_tags()
        log_hist = git_log(*latest_tags)
        headerVersion = latest_tags[-1]
    else:
        raise Exception(
            "Either provide both --ref1 and --ref2 or neither (defaulting to two commits tagged with the highest version numbers)"
        )
    change_log = {}
    token = args.token

    commits = log_hist.split(sep)
    for index, commit_input in enumerate(commits):
        if commit_input:
            splits = commit_input.split(delim)
            commit = Commit(splits[0], splits[1], token)
            for category in commit.categories_:
                change_log.setdefault(category, []).append(str(commit))
        print(f"{index+1}/{len(commits)} done.", end="\r")
        if len(commits) > 9:
            if args.token:
                time.sleep(2)
            else:
                time.sleep(7)
    print("", end="\r")
    print(create_changelog(headerVersion, change_log))
