#!/usr/bin/python

import dedoop
import os
import tempfile
import unittest


class TestCache(unittest.TestCase):

  def setUp(self):
    self.testdata_dir = os.path.join(os.path.realpath(__file__), 'testdata')
    self.source_dir = os.path.join(self.testdata_dir, 'source')
    self.cleanup_dir = os.path.join(self.testdata_dir, 'cleanup')

  def test_init_cache(self):
    test_cache = {
        'no_checksum': dedoop.CacheItem('no_checksum'),
        'has_checksum': dedoop.CacheItem('has_checksum', checksum='foo')
    }
    with tempfile.NamedTemporaryFile() as cache_file:
      dedoop.write_cache(cache_file.name, test_cache)
      cache = dedoop.load_cache(cache_file.name)
      self.assertEqual(2, len(cache))
      self.assertEqual('has_checksum', cache['has_checksum'].abspath)
      self.assertEqual('foo', cache['has_checksum']._checksum)
      # Verify the checksum isn't ever computed.
      self.assertEqual('no_checksum', cache['no_checksum'].abspath)
      self.assertEqual(None, cache['no_checksum']._checksum)


if __name__ == '__main__':
  unittest.main()
