#!/usr/bin/env python3
"""Check ReactOS apps.

This script checks rapps-db repo containing app spec files with the schema:
    https://reactos.org/wiki/RAPPS#File_Schema

This script will check the file specified in [Section] group (for now).
- Files absent or have mismatched size and hash are writen to a 'urls' file,
  which can be used for aria2 to download them.
- Files have only one mismatch between size and hash are considered to have
  suspiciously wrong size and hash. Please check the spec files.
"""
import argparse
import configparser
import enum
import hashlib
import os
import urllib.parse

SECTIONS = ["Section", "Section.amd64"]


class E(enum.Enum):
    """Return codes for check_apps."""

    PASS = 0
    INFO = 1
    MISSING = 2
    SHA1 = 3
    SIZE = 4
    BOTH = 5


def calculate_sha1(file_path):
    """Calculate SHA1 hash of the file at file_path."""
    with open(file_path, 'rb') as f:
        return hashlib.file_digest(f, 'sha1').hexdigest()


def extract_info(section):
    """Extract URLDownload, SHA1, and SizeBytes from one section in ini_file."""
    url_download = section.get('URLDownload')
    filename = os.path.basename(url_download).split('?')[0]
    filename = urllib.parse.unquote(filename)
    filename = section.get('SaveAs', filename)

    sha1 = section.get('SHA1')
    size_bytes = section.get('SizeBytes')

    return url_download, filename, sha1, size_bytes


def check_section(section, apps_dir, dump):
    """Check app specified in ini_file under given section."""
    if section.get('URLDownload') is None:
        return E.PASS, None

    url, file, sha1, size = extract_info(section)
    dest_path = os.path.join(apps_dir, file)

    if dump:
        print(file)
        return E.PASS, None
    if not sha1 or not size:
        return E.INFO, section.name

    # Check if file already exists
    if not os.path.exists(dest_path):
        return E.MISSING, url, file

    # Check size and SHA1
    sha1_match = calculate_sha1(dest_path) == sha1.lower()
    size_match = os.path.getsize(dest_path) == int(size)
    if not sha1_match and not size_match:
        return E.BOTH, file
    if not sha1_match and size_match:
        return E.SHA1, file
    if not size_match and sha1_match:
        return E.SIZE, file
    return E.PASS, None


def report(errors, apps_dir):
    """Report errors found during check_apps."""
    if len(errors[E.INFO]) > 0:
        print("Missing SHA1 or SizeBytes:\n- " + "\n- ".join(errors[E.INFO]))
    if len(errors[E.MISSING]) > 0:
        print("Missing files:\n- " + "\n- ".join(errors[E.MISSING]))
    if len(errors[E.SHA1]) > 0:
        print("SHA1 mismatch:\n- " + "\n- ".join(errors[E.SHA1]))
    if len(errors[E.SIZE]) > 0:
        print("Size mismatch:\n- " + "\n- ".join(errors[E.SIZE]))
    if len(errors[E.BOTH]) > 0:
        print("Both SHA1 and Size mismatch:\n- " + "\n- ".join(errors[E.BOTH]))

    if len(errors[E.MISSING]) > 0:
        with open('urls', 'w') as f:
            for url, file in errors[E.MISSING]:
                f.writelines([f"{url}\n", f"  out={apps_dir}/{file}\n"])
        print("Missing files URLs written to 'urls' file. "
              "You can use it with aria2 to download them.")


def check_apps(txt_files, apps_dir, dump):
    """Check apps in rapps-db repo."""
    files = txt_files or os.listdir(os.getcwd())
    files = [f for f in files if f.endswith('.txt')]
    errors = { E.INFO: [], E.MISSING: [], E.SHA1: [], E.SIZE: [], E.BOTH: [] }

    config = configparser.ConfigParser(interpolation=None)

    for file in files:
        config.read(os.path.join(os.getcwd(), file))
        sections = [s for s in config.sections() if s in SECTIONS]
        for section in sections:
            err, args = check_section(config[section], apps_dir, dump)
            if err == E.PASS:
                continue
            if err == E.INFO:
                errors[err].append(f"{file}[{args}]")
            else:
                errors[err].append(args)
        config.clear()
        if not dump:
            print('.', end='', flush=True)

    if not dump:
        print()
        report(errors, apps_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check ReactOS apps "
                                     "for sha1 and size mismatches.")
    parser.add_argument('txt_file', nargs='*',
                        help="INI files to check. If not specified, all .txt "
                        "files in the current directory will be checked.")
    parser.add_argument('-d', '--apps-dir', default='./apps',
                        help="Directory to check for downloaded apps. "
                        "Default is 'apps' in the current directory.")
    parser.add_argument('-D', '--dump', action='store_true',
                        help="Dump athe list of all apps without checking.")
    args = parser.parse_args()

    apps_dir = os.path.abspath(args.apps_dir)
    os.makedirs(apps_dir, exist_ok=True)
    check_apps(txt_files=args.txt_file, apps_dir=apps_dir, dump=args.dump)
