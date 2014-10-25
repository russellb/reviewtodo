===============================
reviewtodo
===============================

Review to-do list generator.

* Free software: Apache license
* https://github.com/russellb/reviewtodo

Features
--------

This tool generates a code review to-do list for you.  It's not intended to help
you figure out which new patches to review.  Its purpose is to help you manage
tracking which reviews you are due to follow up on.

Reviews on your to-do list fit the following criteria:

* You have previously reviewed it at some point.
* You have not reviewed the latest revision.
* The latest revision has no -1 or -2 votes.

Note that one of the key things *not* included in your to-do list are reviews
where someone added you to the review, but you haven't actually touched it yet.
This is one of the key things that makes your review list in gerrit less useful.

Examples
--------

Get a review to-do list across all projects::

  $ reviewtodo -u russellb

Get a review to-do list for a single project::

  $ reviewtodo -u russellb -p openstack/nova

Get a to-do list across all projects, but list every review you have not voted
in for a subset of projects::

  $ reviewtodo -u russellb -a openstack/governance,openstack-infra/reviewstats
