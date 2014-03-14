# -*- coding: utf-8 -*-

#
# Copyright (C) 2014, Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import getpass
import json
import logging
import optparse
import sys

import paramiko


def get_changes(projects, gerrit_user, ssh_key, server):
    all_changes = []

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for project in projects:
        changes = []

        if not changes:
            while True:
                client.connect(server, port=29418,
                               key_filename=ssh_key, username=gerrit_user)
                cmd = ('gerrit query %s --all-approvals --patch-sets '
                       '--format JSON status:open reviewer:%s' %
                       (('project:%s' % project) if project else '',
                        gerrit_user))
                if changes:
                    cmd += ' resume_sortkey:%s' % changes[-2]['sortKey']
                stdin, stdout, stderr = client.exec_command(cmd)
                for l in stdout:
                    changes += [json.loads(l)]
                if changes[-1]['rowCount'] == 0:
                    break

        all_changes.extend(changes)

    return all_changes


def patch_set_approved(patch_set):
    approvals = patch_set.get('approvals', [])
    for review in approvals:
        if review['type'] == 'APRV':
            return True
    return False


def print_change(change):
    print ' --> %s (%s)' % (change['url'], change.get('topic'))


def print_review_todo(options):
    changes = get_changes([options.project], options.user, options.key,
            options.server)

    backburner = []
    todo = []

    for change in changes:
        if 'rowCount' in change:
            continue
        if change['status'] != 'NEW':
            # Filter out WORKINPROGRESS
            continue
        latest_patch = change['patchSets'][-1]
        if patch_set_approved(latest_patch):
            # Ignore patches already approved and just waiting to merge
            continue

        reviewed = False
        for patch in change['patchSets']:
            for review in patch.get('approvals', []):
                if review['by']['username'] == options.user:
                    reviewed = True
                    break
            if reviewed:
                break
        if not reviewed:
            # Ignore changes where this user has not actually reviewed it.
            # This catches the case where someone else adds you to a review.
            # Just anyone shouldn't be able to put stuff on your todo list.
            continue

        waiting_for_review = True
        approvals = latest_patch.get('approvals', [])
        approvals.sort(key=lambda a: a['grantedOn'])
        already_reviewed_latest = False
        for review in approvals:
            if review['type'] not in ('CRVW', 'VRIF',
                                      'Code-Review', 'Verified'):
                continue
            if review['by']['username'] == options.user:
                already_reviewed_latest = True
                break
            if review['value'] in ('-1', '-2'):
                waiting_for_review = False
                break
        if not waiting_for_review or already_reviewed_latest:
            backburner.append(change)
        else:
            todo.append(change)

    print 'Reviews to-do:'
    for change in todo:
        print_change(change)

    print
    print 'Active reviews that do not need attention:'
    for change in backburner:
        print_change(change)


def main(argv=None):
    if argv is None:
        argv = sys.argv

    optparser = optparse.OptionParser()
    optparser.add_option(
        '-p', '--project', default='',
        help='Only show reviews for a specific project')
    optparser.add_option(
        '-u', '--user', default=getpass.getuser(), help='gerrit user')
    optparser.add_option(
        '-k', '--key', default=None, help='ssh key for gerrit')
    optparser.add_option(
        '-s', '--starred', action='store_true',
        help='Include starred changes that have not been reviewed yet.')
    optparser.add_option(
        '--server', default='review.openstack.org',
        help='Gerrit server to connect to')

    options, args = optparser.parse_args()

    logging.basicConfig(level=logging.ERROR)

    print_review_todo(options)
