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


def get_from_gerrit(query, gerrit_user, ssh_key, server):
    changes = []

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    while True:
        try:
            client.connect(server, port=29418,
                           key_filename=ssh_key, username=gerrit_user)
        except paramiko.SSHException:
            # retry with allow_agent=False if initial connect fails.
            client.connect(server, port=29418,
                           key_filename=ssh_key, username=gerrit_user,
                           allow_agent=False)
        cmd = ('gerrit query --all-approvals --patch-sets '
               '--format JSON %s' % query)
        if changes:
            cmd += ' resume_sortkey:%s' % changes[-2]['sortKey']
        stdin, stdout, stderr = client.exec_command(cmd)
        for l in stdout:
            changes += [json.loads(l)]
        if changes[-1]['rowCount'] == 0:
            break

    return changes


def projects_q(projects):
    return ('(' +
            ' OR '.join(['project:' + p for p in projects]) +
            ')')


def get_changes(project, all_from, gerrit_user, ssh_key, server):
    changes = []

    query = '%s status:open reviewer:%s' % (
            ('project:%s' % project) if project else '', gerrit_user)
    changes.extend(get_from_gerrit(query, gerrit_user, ssh_key, server))

    if all_from:
        query = '%s status:open' % (projects_q(all_from))
        changes.extend(get_from_gerrit(query, gerrit_user, ssh_key, server))

    return changes


def patch_set_approved(patch_set):
    approvals = patch_set.get('approvals', [])
    for review in approvals:
        if review['type'] == 'APRV':
            return True
    return False


def print_change(change):
    print ' --> %s (%s)' % (change['subject'], change.get('topic'))
    print ' ------> %s' % change['url']


def print_review_todo(options):
    all_from_projects = options.all_from.split(',')
    if len(all_from_projects) == 1 and all_from_projects[0] == '':
        all_from_projects = []

    changes = get_changes(options.project, all_from_projects, options.user,
                          options.key, options.server)

    backburner = {}
    todo = {}

    for change in changes:
        if 'rowCount' in change:
            continue
        if change['status'] != 'NEW':
            # Filter out WORKINPROGRESS
            continue
        if change['owner']['username'] == options.user:
            # Ignore your own changes
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
        if not reviewed and change['project'] not in all_from_projects:
            # Ignore changes where this user has not actually reviewed it.
            # This catches the case where someone else adds you to a review.
            # Just anyone shouldn't be able to put stuff on your todo list.
            # The exception is projects you have specifically listed to see all
            # changes from that you haven't reviewed.
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
            backburner[change['number']] = change
        else:
            todo[change['number']] = change

    print 'Reviews to-do:'
    for change in todo.itervalues():
        print_change(change)

    if options.full:
        print
        print 'Active reviews that do not need attention:'
        for change in backburner.itervalues():
            print_change(change)


def main(argv=None):
    if argv is None:
        argv = sys.argv

    optparser = optparse.OptionParser()
    optparser.add_option(
        '-p', '--project', default='',
        help='Only show reviews for a specific project')
    optparser.add_option(
        '-a', '--all-from', default='',
        help='A comma separated list of projects. List all changes from '
             'these projects that you have not voted on. Useful for '
             'smaller projects you want to see all changes for.')
    optparser.add_option(
        '-u', '--user', default=getpass.getuser(), help='gerrit user')
    optparser.add_option(
        '-k', '--key', default=None, help='ssh key for gerrit')
    optparser.add_option(
        '--server', default='review.openstack.org',
        help='Gerrit server to connect to')
    optparser.add_option(
        '-f', '--full', action='store_true',
        help='Show full output, including list of reviews that do not '
             'currently need any attention.')

    options, args = optparser.parse_args()

    logging.basicConfig(level=logging.ERROR)

    print_review_todo(options)
