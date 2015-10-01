## dedooper

Given two directory trees with some files that have the exact same checksum,
replace the files in one tree with symlinks to the files in the other tree.

Intended for use with lots of large files. Does preliminary comparisons based
on file size, then uses SHA-1 checksum, and stores details of files in the
source directory in a cache file.

### Usage

`python dedoop.py [--[no]show_source_dupes] [--[no]dry_run] [--[no]prompt] [--cache_file=<filename>] <source> <cleanup>`

* `--[no]show_source_dupes`: Prints duplicates in the source tree. (default: true)
* `--cache_file`: Location of the cache file. (default: ~/.dedooper.cache)
* `--min_filesize`: Minimum filesize (in bytes) to examine. (default: 1GB)
* `--[no]dry_run`: Print commands rather than executing them. (default: true)
* `--[no]prompt`: Prompt before creating symlinks. (default: true)
* `<source>`: Directory containing original files.
* `<cleanup>`: Directory containing duplicate files to be turned into symlinks to `<source>`.
