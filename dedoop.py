#!/usr/bin/python

import argparse
import hashlib
import os
import sys


def hashwalk(root, callback):
    for (dirpath, dirnames, filenames) in os.walk(root):
        for filename in filenames:
            abspath = os.path.join(dirpath, filename)
            if os.path.islink(abspath):
                continue
            with open(abspath, 'r') as f:
                m = hashlib.sha1()
                m.update(f.read())
                checksum = m.hexdigest()
                callback(abspath, checksum)


def get_tree_checksums(root, show_source_dupes=True):
    print 'Checksumming %s...' % root
    checksums = {}

    def callback(abspath, checksum):
        if checksum in checksums and show_source_dupes:
            # Print collisions in the tree
            print '%s: %s == %s' % (
                    root, 
                    abspath.replace(root, '', 1).lstrip('/'), 
                    checksums[checksum].replace(root, '', 1).lstrip('/'))
        checksums[checksum] = abspath

    hashwalk(root, callback)

    print 'Checksummed %d files in %s.' % (len(checksums), root)
    return checksums


def cleanup_tree(root, checksums, dry_run=True):
    num_deduped = [0]
    def callback(abspath, checksum):
        if checksum not in checksums:
            return
        if dry_run:
            print 'ln -sf %s %s' % (checksums[checksum], abspath)
        else:
            print 'removing duplicate file %s' % abspath
            os.unlink(abspath)
            print 'creating link %s -> %s' % (abspath, checksums[checksum])
            os.symlink(checksums[checksum], abspath)
        num_deduped[0] += 1

    hashwalk(root, callback)
    print 'deduped %d files' % num_deduped[0]


def main():
    parser = argparse.ArgumentParser(
            'Find duplicate files and turn half of them into symlinks.')
    parser.add_argument(
            'source', help='Directory root containing original files.')
    parser.add_argument(
            'cleanup', 
            help='Directory root containing duplicate files '
                 'to be turned into symlinks.')

    parser.add_argument(
            '--show_source_dupes',
            dest='show_source_dupes',
            action='store_true',
            help='Show duplicate files in the source directory')
    parser.add_argument(
            '--noshow_source_dupes',
            dest='show_source_dupes',
            action='store_false',
            help="Don't show duplicate files in the source directory")
    parser.set_defaults(show_source_dupes=True)

    parser.add_argument(
            '--dry_run',
            dest='dry_run',
            action='store_true',
            help="Print commands, don't execute them")
    parser.add_argument(
            '--nodry_run',
            dest='dry_run',
            action='store_false',
            help="Execute commands.")
    parser.set_defaults(dry_run=True)

    args = parser.parse_args()
    src_checksums = get_tree_checksums(
            os.path.abspath(args.source),
            show_source_dupes=args.show_source_dupes)
    cleanup_tree(os.path.abspath(args.cleanup), src_checksums, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
