import re
import requests
import json
import subprocess
from enum import Enum

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

    def __init__(self, hash_: str, sub_cat_: str):
        self.hash_ = hash_.strip()
        cat_sub_split = sub_cat_.split(":", 1)
        self.subject_ = cat_sub_split[1].strip()
        self.categories_ = cat_sub_split[0].split("/")
        self.pr_ = self.get_pr_link()

    def get_pr_link(self):
        regex = r"\(\#\\d*\)"
        if not re.search(regex, self.subject_):
            response = requests.get(
                f"https://api.github.com/search/issues?q={self.hash_}"
            )
            for item in response.json().get("items", []):
                if item.get("state", "open") == "closed":
                    return item.get("pull_request", {}).get("html_url")
        return

    def __str__(self):
        if self.pr_:
            pr_nr = self.pr_.split("/")[-1]
            self.pr_ = f" ([#{pr_nr}]({self.pr_}))"
        return f"{self.subject_}{self.pr_}"


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


def create_changelog(version, change_dict):
    body = ""

    for key in change_dict:
        body += "### " + key.capitalize() + "\n"
        for item in change_dict[key]:
            body += "- " + item + "\n"
        body += "\n"

    return f"## {version}\n{body}"


if __name__ == "__main__":
    ref1 = "v1.4.5"
    ref2 = "v1.4.6"
    log_hist = git_log(ref1, ref2)
    change_log = {}

    commits = log_hist.split(sep)
    for commit_input in commits:
        if commit_input:
            splits = commit_input.split(delim)
            commit = Commit(splits[0], splits[1])
            for category in commit.categories_:
                change_log.setdefault(category, []).append(str(commit))

    print(create_changelog(ref2, change_log))
