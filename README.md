# Grenier

## What it is

**Grenier** is a python3 wrapper around [bup](https://github.com/bup/bup),
[rsync](https://rsync.samba.org/) and [rclone](http://rclone.org/), using
a configuration file to manage repositories.


**Grenier** can create new archives in these repositories, and also copy them to
external drives or to cloud storage (see rclone manpage to see which are
supported).
Files are encrypted with [encfs](https://github.com/vgough/encfs) before being
sent over the Internets.

It can do other things too, probably. You'll just have to read on.

Please note this is not stable yet, as in: **You may lose data.** To be honest
(something I generally avoid): you probably will.

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Example Commands](#example-commands)
- [Configuration](#configuration)
- [grenier.yaml example](#grenieryaml-example)

### Requirements

**Grenier** runs on Linux (tested in Archlinux only).

Current requirements:
- python (3.4+)
- python-yaml
- python-notify2

External binaries required:
- [bup](https://github.com/bup/bup)
- [rsync](https://rsync.samba.org/) (for external drives backup)
- [rclone](http://rclone.org/) (for google drive and hubic backup)
- [encfs](https://github.com/vgough/encfs) (for encryption before saving to cloud)

### Installation


After cloning this repository, run:

    $ sudo python setup.py install

To uninstall (not sure why one would want to do such a thing), run:

    $ sudo pip uninstall grenier

The configuration file *grenier.yaml* is expected to be in
`$XDG_CONFIG_HOME/grenier/`. You might want to `ln -s` your actual configuration
file there, because let's face it, `$XDG_CONFIG_HOME` is a sad and lonely place
you never visit.

Logs are in `$XDG_DATA_HOME/grenier`, along with another yaml file that keeps
track of when you last backed up you repositories to another hard drive or to
the cloud (see `--last-synced`).

### Usage


    $ grenier -h

    # # # G R E N I E R # # #
    usage: grenier [-h] [--config CONFIG_FILE] [-l]
                   [-n BACKUP_NAME [BACKUP_NAME ...]] [-b]
                   [-s REMOTE [REMOTE ...]] [-c] [-f MOUNT_POINT]
                   [-r RESTORE_DIRECTORY] [--last-synced]
                   [--recover REMOTE TARGET]

    Grenier. A wrapper around bup, rclone, rsync, encfs to back stuff up.

    optional arguments:
      -h, --help            show this help message and exit

    Configuration:
      Manage configuration files.

      --config CONFIG_FILE  Use an alternative configuration file.
      -l, --list            List defined repositories.

    Repositories:
      Manage repositories.

      -n BACKUP_NAME [BACKUP_NAME ...], --name BACKUP_NAME [BACKUP_NAME ...]
                            specify backup names, or "all".
      -b, --backup          backup selected repositories.
      -s REMOTE [REMOTE ...], --sync REMOTE [REMOTE ...]
                            backup selected repositories to the cloud or usb
                            drives, or to "all".
      -c, --check           check and repair selected repositories.
      -f MOUNT_POINT, --fuse MOUNT_POINT
                            Mount/unmount a specified repository to a mountpoint.
      -r RESTORE_DIRECTORY, --restore RESTORE_DIRECTORY
                            Restore latest to this directory.
      --last-synced         list when you last backed up repositories.
      --recover REMOTE TARGET
                            recover repository from remote to target.



### Example commands

The following commands assume the configuration file is as
[described here](#grenieryaml-example).

This creates timestamped archives of all sources for the `documents` repository
(something like `2015-04-09_22h48_work` and `2015-04-09_22h53_notes`), as
described in the configuration file. If the repository does not exist, it will
be created.
Also, par2 files are automatically generated.

    grenier -n documents -b

This copies the `documents` repository to the external hard drive `disk1`. The
hard drive is assumed to be mounted on `/run/media/user/disk1`.

    grenier -n documents -s disk1

This does the same things, but for all repositories having `disk1` as backup
drive:

    grenier -n all -s disk1

This sends `documents` to both google drive and hubic, provided "google" and
"hubic" are previously configured rclone remotes:

    grenier -n documents -s google hubic

This sends `documents` to all defined and available backup remotes (`disk1`,
google drive, hubic):

    grenier -n documents -s all

This predictably does pretty much everything:

    grenier -n all -s all

This checks the `documents` repository for errors:

    grenier -n documents -c

This mounts the `documents` repository in a directory:

    grenier -n documents -f /mnt/repo

Restoring the latest version of the `documents` repository to a directory:

    grenier -n documents -r /home/user/hope_this_works/

Recovering a repository from the cloud to a directory:

    grenier -n documents --recover hubic /home/user/hope_this_works/

When did you last update the copies of your repositories on that hard drive
you dropped off at your cousin's home?

    grenier --last-synced

### Configuration

**Grenier** uses a yaml file to describe
- repositories,
- what to back up in each,
- where to keep extra copies
- sensitive information such as passphrases, to keep things simple.

**The user is responsible for keeping this file safe**.

Encfs uses xml files to describe how a repository is encoded.
You probably should keep them around.

Here is the general structure of how to describe a repository for **grenier**:

    repository_name:
        backup_dir: /path/to/repository
        passphrase: clear_passphrase
        sources:
            source1_name:
                dir: /path/to/source
                excluded: ["extension1", "extension2"]
        temp_dir: /path/to/temp/folder/with/enough/disk/space/available
        rclone_config_file: /optional/path/to/rclone/config
        backups:
            - disk_name
            - /absolute/path/to/backup/folder
            - rclone_remote_name

**Grenier** will automatically create a subdirectory
`grenier_[repository_name]` in backup_dir.

`rclone_config_file` defaults to ~/.rclone.conf if not specified.
**Grenier** does not configure rclone backends for you.
You'll have to do this on your lonesome, before running **grenier**.

### grenier.yaml example

For example, this is a file defining two repositories:

    documents:
        backup_dir: /home/user/backup
        passphrase: CRxoKuMUpxpokpkpk5FF-hgookokok36wc7H
        sources:
            work:
                dir: /home/user/work
                excluded: ["log", "pdf", "epub", "azw3", "html", "zip"]
            notes:
                dir: /home/user/documents/Notes
        temp_dir: /tmp/documents
        backups:
            - disk1
            - disk2
            - google
            - hubic
    music:
        backup_dir: /home/user/backup
        passphrase: vqrlkjmohmohiuhç_hç_hçàhlmhmj_jmlkj
        sources:
            flac_music:
                dir: /home/user/music/flac
        temp_dir: /tmp/music
        backups:
            - disk1
            - hubic
