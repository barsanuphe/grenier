# Grenier


## What it is

**Grenier** is a python3 wrapper around [attic](https://github.com/jborg/attic),
[rsync](https://rsync.samba.org/) and [duplicity](http://duplicity.nongnu.org/),
using a configuration file to manage repositories.

**Grenier** create new archives in these repositories, and also copy them to
external drives or to [google drive](https://www.google.com/drive/) and
[hubic](https://hubic.com).

Please note this is not stable yet, ie: **You may lose data.**

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
- python-crypto
- python2-pyrax (hubic backend for duplicity)

External dependancies:
- [attic](https://github.com/jborg/attic)
- [duplicity](http://duplicity.nongnu.org/) (for google drive and hubic backup)
- [rsync](https://rsync.samba.org/) (for external drives backup)

### Installation


After cloning this repository, run:

    $ sudo python setup.py install

To uninstall, run:

    $ sudo pip uninstall grenier

The configuration file *grenier.yaml* is expected to be in
`$XDG_CONFIG_HOME/grenier/`.

Logs are in `$XDG_DATA_HOME/grenier/logs`.

### Usage

Note: if python2 is the default version on your Linux distribution, launch with
`python3 grenier.py`.


    $ python grenier.py -h

    # # # G R E N I E R # # #

    usage: grenier.py [-h] [--config CONFIG_FILE] [--encrypt]
                    [-n BACKUP_NAME [BACKUP_NAME ...]] [-b]
                    [-s BACKUP_TARGET_NAME [BACKUP_TARGET_NAME ...]] [-c]
                    [-f MOUNT_POINT] [-r RESTORE_DIRECTORY]

    Grenier. A wrapper around attic and duplicity to back stuff up.

    optional arguments:
    -h, --help            show this help message and exit

    Configuration:
    Manage configuration files.

    --config CONFIG_FILE  Use an alternative configuration file.
    --encrypt             Toggle encryption on the configuration file.

    Backups:
    Manage backups.

    -n BACKUP_NAME [BACKUP_NAME ...], --name BACKUP_NAME [BACKUP_NAME ...]
                            specify backup names, or "all".
    -b, --backup          backup selected projects.
    -s BACKUP_TARGET_NAME [BACKUP_TARGET_NAME ...], --sync BACKUP_TARGET_NAME [BACKUP_TARGET_NAME ...]
                            backup selected projects to the cloud orusb drives, or
                            to "all".
    -c, --check           check and repair selected backups.
    -f MOUNT_POINT, --fuse MOUNT_POINT
                            Mount/unmount a specified backup to a mountpoint.
    -r RESTORE_DIRECTORY, --restore RESTORE_DIRECTORY
                            Restore latest to this directory.

### Example commands

The following commands assume the configuration file is as
[described here](#grenieryaml-example).

This creates a timestamped archive of `documents` (something like
`2015-04-09_22h48_documents`) in the repository described in the configuration
file. If the repository does not exist, it will be created.

    grenier -n documents -b

This copies the `documents` repository to the external hard drive `disk1`. The
hard drive is assumed to be mounted on `/run/media/user/disk1`.

    grenier -n documents -s disk1

This does the same things, but for all repositories having `disk1` as backup
drive:

    grenier -n all -s disk1

This sends `documents` to both google drive and hubic:

    grenier -n documents -s google hubic

This sends `documents` to all defined and available backup remotes (`disk1`,
google drive, hubic):

    grenier -n documents -s all

This checks the `documents` repository for errors:

    grenier -n documents -c

This mounts the `documents` repository in a directory:

    grenier -n documents -f /mnt/repo


### Configuration

**Grenier** uses a yaml file to describe repositories, what to back up in each,
and sensitive information such as passphrases or passwords to keep things
simple.

The user is responsible for keeping this file safe.

Optionnally, **Grenier** can encrypt this configuration file, decrypting it only
when needed (use `--encrypt` to toggle between encrypted and plaintext).

Here is the general structure of how to describe a repository for grenier:

    repository_name:
        backup_dir: /path/to/repository
        passphrase: clear_passphrase
        sources:
            source1_name:
                dir: /path/to/source
                excluded: ["extension1", "extension2"]
        backups:
            disks: ["disk1_name", "disk2_name"]
            googledrive: address:password@gmail.com
            hubic: /path/to/credentials_file


### grenier.yaml example

For example, this is a file defining two repositories:

    documents:
        backup_dir: /home/user/backup/attic_complots
        passphrase: CRxoKuMUpxpokpkpk5FF-hgookokok36wc7H
        sources:
            work:
                dir: /home/user/work
                excluded: ["log", "pdf", "epub", "azw3", "html", "zip"]
            notes:
                dir: /home/user/documents/Notes
        backups:
            disks: ["disk1", "disk2"]
            googledrive: obviouslyfake:123password@gmail.com
            hubic: /path/to/credentials_file
    music:
        backup_dir: /home/user/backup/attic_music
        passphrase: vqrlkjmohmohiuhç_hç_hçàhlmhmj_jmlkj
        sources:
            flac_music:
                dir: /home/user/music/flac
        backups:
            disks: ["disk1"]
