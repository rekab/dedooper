#!/usr/bin/python

import argparse
import hashlib
import json
import logging
import os
import sys


READ_SIZE = 1024 * 4


class CacheItem(object):
    """Represents a file on disk with properties evaluated lazily."""

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
        logging.debug('statting %s', self.abspath)
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


class CacheItemEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, CacheItem):
            # Return the serialized item, and avoid evaluation of properties.
            return [obj.abspath, obj._mtime, obj._size, obj._checksum]
        return json.JSONEncoder.default(self, obj)


def hashwalk(root, cache=None):
    """Walk a tree and create CacheItems for files.

    Args:
        cache: optional dict keyed by abspath, containing CacheItems. Will be
               modified.
    Yields:
        CacheItems found.
    """
    for (dirpath, dirnames, filenames) in os.walk(root):
        for filename in filenames:
            abspath = os.path.join(dirpath, filename)
            if os.path.islink(abspath):
                continue
            # If the item is in the cache and it hasn't changed.
            if cache is not None:
                if abspath in cache and cache[abspath].verify():
                    logging.debug('cache hit for %s', abspath)
                    yield cache[abspath]
                else:
                    logging.debug('cache miss for %s', abspath)
                    cache[abspath] = CacheItem(abspath)
                    yield cache[abspath]
            else:
                yield CacheItem(abspath)


def get_tree_filesizes(root, cache, show_source_dupes=True):
    """Walk a tree, get CacheItems.

    Args:
        cache: optional dict keyed by abspath, containing CacheItems. Will be
               modified.
    Returns:
        Dictionary keyed by file size, containing lists of CacheItem objects.
    """
    logging.info('walking %s...', root)
    sizes = {}
    num_items = 0
    for cacheitem in hashwalk(root, cache=cache):
        num_items += 1
        if show_source_dupes and cacheitem.size in sizes:
            for other in sizes[cacheitem.size]:
                logging.debug('found files with same size: %s and %s',
                        cacheitem.abspath, other.abspath)
                if cacheitem.checksum == other.checksum:
                    # Print collisions in the tree
                    logging.warning('%s: %s == %s',
                            root,
                            cacheitem.abspath.replace(root, '', 1).lstrip('/'),
                            other.abspath.replace(root, '', 1).lstrip('/'))
        sizes.setdefault(cacheitem.size, []).append(cacheitem)

    logging.info('saw %d files and %d sizes in %s.', num_items, len(sizes), root)
    return sizes


def print_cleanup_command(other, cleanup):
    print 'ln -sf %s %s' % (other, cleanup)


def create_symlink(other, cleanup):
    logging.info('creating link %s -> %s', cleanup, other)
    os.unlink(cleanup)
    os.symlink(other, cleanup)


def prompt_before_symlinking(other, cleanup):
    sys.stdout.write('Create symlink %s -> %s? [Y/n] ' % (cleanup, other))
    choice = raw_input().lower()
    if choice.startswith('n'):
        logging.info('Not creating symlink for %s', cleanup)
    else:
        create_symlink(other, cleanup)


def cleanup_tree(root, sizes, callback):
    num_deduped = 0

    for cacheitem in hashwalk(root):
        if cacheitem.size not in sizes:
            return
        for other in sizes[cacheitem.size]:
            if other.checksum != cacheitem.checksum:
                continue
            if os.path.realpath(other.abspath) == os.path.realpath(cacheitem.abspath):
                logging.error("not symlinking %s to %s: they're the same file",
                        other.abspath, cacheitem.abspath)
            else:
                callback(other.abspath, cacheitem.abspath)
                num_deduped += 1
                break

    logging.info('deduped %d files', num_deduped)


def load_cache(cache_path):
    """Read a dict of CacheItems from a JSON-encoded file.

    Args:
        cache_path: file to write
    Returns:
        dictionary keyed by abspath of CacheItems.
    """
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            for line in f:
                values = json.loads(line)
                cache_item = CacheItem(
                        values[0], mtime=values[1], size=values[2],
                        checksum=values[3])
                cache[cache_item.abspath] = cache_item
    else:
        logging.warning('cache file %s does not exist' % cache_path)
    return cache


def write_cache(cache_path, cache):
    """Write a dictionary of CacheItems to a JSON-encoded file.

    Args:
        cache_path: file to write
        cache: dictionary of CacheItems
    """
    # Write to a temp file, then swap to the final destination.
    tmp_output = cache_path + '.tmp'
    with open(tmp_output, 'w') as f:
        for cache_key in cache:
            assert cache[cache_key].abspath == cache_key
            print >>f, json.dumps(cache[cache_key], cls=CacheItemEncoder)
    os.rename(tmp_output, cache_path)
    logging.info('wrote cache to %s', cache_path)


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
            default=os.path.expanduser('~/.dedooper.cache'),
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
            help='Execute commands')
    parser.set_defaults(dry_run=True)

    parser.add_argument(
            '--prompt',
            dest='prompt',
            action='store_true',
            help='Prompt before creating symlinks')
    parser.add_argument(
            '--noprompt',
            dest='prompt',
            action='store_false',
            help="Don't prompt before creating symlinks")
    parser.set_defaults(prompt=True)

    parser.add_argument(
            '--log_level',
            dest='log_level',
            default=logging.INFO,
            help='log level (higher is quieter)')

    args = parser.parse_args()

    logging.basicConfig(
            level=args.log_level,
            format='%(levelname)-8s: %(message)s')

    if os.path.realpath(args.source) == os.path.realpath(args.cleanup):
        logging.critical('source dir is the same as cleanup dir')
        sys.exit(1)

    # Find out what's in the source tree.
    cache = load_cache(args.cache_file)
    src_filesizes = get_tree_filesizes(
            os.path.abspath(args.source),
            cache,
            show_source_dupes=args.show_source_dupes)
    write_cache(args.cache_file, cache)

    # Pick a cleanup strategy.
    callback = print_cleanup_command
    if not args.dry_run:
        if args.prompt:
            callback = prompt_before_symlinking
        else:
            callback = create_symlink

    # Clean up the cleanup tree.
    cleanup_tree(os.path.abspath(args.cleanup), src_filesizes, callback=callback)


if __name__ == '__main__':
    main()
