#!/usr/bin/python

import argparse
import hashlib
import os
import sys


READ_SIZE = 1024 * 4


class CacheItem(object):
    def __init__(self, abspath, mtime=None, size=None, checksum=None):
        self.abspath = abspath
        self._mtime = mtime
        self._size = size
        self._checksum = checksum

    def __str__(self):
        return '%(abspath)s: mtime=%(_mtime)s size=%(_size)s checksum=%(_checksum)s' % (self.__dict__)

    def __repr__(self):
        return str(self)

    @property
    def checksum(self):
        if self._checksum:
            return self._checksum

        m = hashlib.sha1()
        with open(self.abspath, 'r') as f:
            while True:
                b = f.read(READ_SIZE)
                if b == '':
                    break
                m.update(b)
        self._checksum = m.hexdigest()
        return self._checksum

    def _stat(self):
        stat = os.stat(self.abspath)
        print 'statting %s ' % self.abspath
        self._size = stat.st_size
        self._mtime = int(stat.st_mtime)

    def verify(self):
        """Verify the cache item hasn't changed.
        
        For speed, only looks at mtime and size."""
        if self._size is None or self._mtime is None:
            return False
        stat = os.stat(self.abspath)
        return self._size == stat.st_size and self._mtime == int(stat.st_mtime)

    @property
    def size(self):
        if self._size is not None:
            return self._size
        self._stat()
        return self._size

    @property
    def mtime(self):
        if self._mtime is not None:
            return self._mtime
        self._stat()
        return self._mtime


def hashwalk(root, cache=None):
    for (dirpath, dirnames, filenames) in os.walk(root):
        for filename in filenames:
            abspath = os.path.join(dirpath, filename)
            if os.path.islink(abspath):
                continue
            # If the item is in the cache and it hasn't changed.
            if cache is not None:
                if abspath in cache and cache[abspath].verify():
                    yield cache[abspath]
                cache[abspath] = CacheItem(abspath)
                yield cache[abspath]
            else:
                yield CacheItem(abspath)


def get_tree_filesizes(root, cache, show_source_dupes=True):
    print 'Walking %s...' % root
    sizes = {}

    for cacheitem in hashwalk(root, cache=cache):
        if show_source_dupes and cacheitem.size in sizes:
            for other in sizes[cacheitem.size]:
                if cachitem.checksum == other.checksum:
                    # Print collisions in the tree
                    print '%s: %s == %s' % (
                            root,
                            cacheitem.abspath.replace(root, '', 1).lstrip('/'),
                            other.abspath.replace(root, '', 1).lstrip('/'))
        sizes.setdefault(cacheitem.size, []).append(cacheitem)

    print 'Saw %d files in %s.' % (len(sizes), root)
    return sizes


def cleanup_tree(root, sizes, dry_run=True):
    num_deduped = 0

    for cacheitem in hashwalk(root):
        if cacheitem.size not in sizes:
            return
        for other in sizes[cacheitem.size]:
            if other.checksum != cacheitem.checksum:
                continue
            if dry_run:
                print 'ln -sf %s %s' % (other.abspath, cacheitem.abspath)
            else:
                print 'creating link %s -> %s' % (abspath, checksums[checksum].abspath)
                os.unlink(abspath)
                os.symlink(other.abspath, cacheitem.abspath)
            num_deduped += 1
            break

    print 'deduped %d files' % num_deduped


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
            '--cache_file',
            help='where to store the cache')

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

    # TODO: back the cache to disk
    cache = {}
    src_filesizes = get_tree_filesizes(
            os.path.abspath(args.source),
            cache,
            show_source_dupes=args.show_source_dupes)
    print 'cache=%s' % cache
    cleanup_tree(os.path.abspath(args.cleanup), src_filesizes, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
