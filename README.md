## dedooper

Given two directory trees with some files that have the exact same checksum,
replace the files in one tree with symlinks to the files in the other tree.

### Usage

`python dedoop.py [--[no]show_source_dupes] [--[no]dry_run] [--[no]prompt] <source> <cleanup>`

* `--[no]show_source_dupes`: Prints duplicates in the source tree (default: true)
* `--[no]dry_run`: Print commands rather than executing them (default: true)
* `--[no]prompt`: Prompt before creating symlinks (default: true)
* `<source>`: Directory containing original files.
* `<cleanup>`: Directory containing duplicate files to be turned into symlinks to `<source>`.
