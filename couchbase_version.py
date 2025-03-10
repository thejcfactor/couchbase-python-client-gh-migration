#!/usr/bin/env python

#  Copyright 2016-2022. Couchbase, Inc.
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License")
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from __future__ import print_function

import datetime
import os.path
import re
import subprocess
import warnings


class CantInvokeGit(Exception):
    pass


class VersionNotFound(Exception):
    pass


class MalformedGitTag(Exception):
    pass


RE_XYZ = re.compile(r'(\d+)\.(\d+)\.(\d+)(?:-(.*))?')

VERSION_FILE = os.path.join(os.path.dirname(__file__), 'couchbase', '_version.py')


class VersionInfo(object):
    def __init__(self, rawtext):
        self.rawtext = rawtext
        t = self.rawtext.rsplit('-', 2)
        if len(t) != 3:
            raise MalformedGitTag(self.rawtext)

        vinfo, self.ncommits, self.sha = t
        self.ncommits = int(self.ncommits)

        # Split up the X.Y.Z
        match = RE_XYZ.match(vinfo)
        (self.ver_maj, self.ver_min, self.ver_patch, self.ver_extra) =\
            match.groups()

        # Per PEP-440, replace any 'DP' with an 'a', and any beta with 'b'
        if self.ver_extra:
            self.ver_extra = re.sub(r'^dp', 'a', self.ver_extra, count=1)
            self.ver_extra = re.sub(r'^alpha', 'a', self.ver_extra, count=1)
            self.ver_extra = re.sub(r'^beta', 'b', self.ver_extra, count=1)
            m = re.search(r'^([ab]|dev|rc|post)(\.{0,1}\d+)?', self.ver_extra)
            if m.group(1) in ["dev", "post"]:
                self.ver_extra = "." + self.ver_extra
            if m.group(2) is None:
                # No suffix, then add the number
                first = self.ver_extra[0]
                self.ver_extra = first + '0' + self.ver_extra[1:]

    @property
    def is_final(self):
        return self.ncommits == 0

    @property
    def is_prerelease(self):
        return self.ver_extra

    @property
    def xyz_version(self):
        return '.'.join((self.ver_maj, self.ver_min, self.ver_patch))

    @property
    def base_version(self):
        """Returns the actual upstream version (without dev info)"""
        components = [self.xyz_version]
        if self.ver_extra:
            components.append(self.ver_extra)
        return ''.join(components)

    @property
    def package_version(self):
        """Returns the well formed PEP-440 version"""
        vbase = self.base_version
        if self.ncommits:
            vbase += '.dev{0}+{1}'.format(self.ncommits, self.sha)
        return vbase


def get_version():
    """
    Returns the version from the generated version file without actually
    loading it (and thus trying to load the extension module).
    """
    if not os.path.exists(VERSION_FILE):
        raise VersionNotFound(VERSION_FILE + " does not exist")
    fp = open(VERSION_FILE, "r")
    vline = None
    for x in fp.readlines():
        x = x.rstrip()
        if not x:
            continue
        if not x.startswith("__version__"):
            continue

        vline = x.split('=')[1]
        break
    if not vline:
        raise VersionNotFound("version file present but has no contents")

    return vline.strip().rstrip().replace("'", '')


def get_git_describe():
    if not os.path.exists(os.path.join(os.path.dirname(__file__), ".git")):
        raise CantInvokeGit("Not a git build")

    try:
        po = subprocess.Popen(
            ("git", "describe", "--tags", "--long", "--always"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        raise CantInvokeGit(e)

    stdout, stderr = po.communicate()
    if po.returncode != 0:
        raise CantInvokeGit("Couldn't invoke git describe", stderr)

    return stdout.decode('utf-8').rstrip()


def gen_version(do_write=True, txt=None):
    """
    Generate a version based on git tag info. This will write the
    couchbase/_version.py file. If not inside a git tree it will
    raise a CantInvokeGit exception - which is normal
    (and squashed by setup.py) if we are running from a tarball
    """

    if txt is None:
        txt = get_git_describe()

    t = txt.rsplit('-', 2)
    if len(t) != 3:
        only_sha = re.match('[a-z0-9]+', txt)
        if only_sha is not None and only_sha.group():
            txt = f'0.0.1-0-{txt}'

    try:
        info = VersionInfo(txt)
        vstr = info.package_version
    except MalformedGitTag:
        warnings.warn("Malformed input '{0}'".format(txt))
        vstr = '0.0.0' + txt

    if not do_write:
        print(vstr)
        return

    lines = (
        '# This file automatically generated by',
        '#    {0}'.format(__file__),
        '# at',
        '#    {0}'.format(datetime.datetime.now().isoformat(' ')),
        "__version__ = '{0}'".format(vstr)
    )
    with open(VERSION_FILE, "w") as fp:
        fp.write("\n".join(lines))


if __name__ == '__main__':
    from argparse import ArgumentParser
    ap = ArgumentParser(description='Parse git version to PEP-440 version')
    ap.add_argument('-c', '--mode', choices=('show', 'make', 'parse'))
    ap.add_argument('-i', '--input',
                    help='Sample input string (instead of git)')
    options = ap.parse_args()

    cmd = options.mode
    if cmd == 'show':
        print(get_version())
    elif cmd == 'make':
        gen_version(do_write=True, txt=options.input)
        print(get_version())
    elif cmd == 'parse':
        gen_version(do_write=False, txt=options.input)

    else:
        raise Exception("Command must be 'show' or 'make'")
