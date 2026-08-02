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


def calculate_sha1(file_path: str) -> str:
    """Calculate SHA1 hash of the file at file_path."""
    with open(file_path, 'rb') as f:
        return hashlib.file_digest(f, 'sha1').hexdigest()


def extract_info(section: configparser.SectionProxy) -> dict | None:
    """Extract URLDownload, SHA1, and SizeBytes from one section in ini_file."""
    url_download = section.get('URLDownload')
    # Invalid section if URLDownload not present
    if url_download is None:
        return None

    filename = os.path.basename(url_download).split('?')[0]
    filename = urllib.parse.unquote(filename)
    filename = section.get('SaveAs', filename)

    sha1 = section.get('SHA1')
    size_bytes = section.get('SizeBytes')

    return {
        'url': url_download,
        'file': filename,
        'sha1': sha1,
        'size': size_bytes,
    }


def check_info(info: dict, apps_dir: str, *, sha1: bool = True):
    """Check app specified in ini_file under given section."""
    dest_path = os.path.join(apps_dir, info['file'])

    # Check complete info
    if not info['sha1'] or not info['size']:
        return E.INFO

    # Check file existence
    if not os.path.exists(dest_path):
        return E.MISSING

    # Check size and SHA1
    sha1_match = calculate_sha1(dest_path) == info['sha1'].lower() if sha1 else True
    size_match = os.path.getsize(dest_path) == int(info['size'])
    if not sha1_match and not size_match:
        return E.BOTH
    if not sha1_match and size_match:
        return E.SHA1
    if not size_match and sha1_match:
        return E.SIZE

    return E.PASS


def report(errors: dict, apps_dir: str):
    """Report errors found during check_apps."""
    error_messages = {
        E.INFO: "Missing SHA1 or SizeBytes",
        E.MISSING: "Missing files",
        E.SHA1: "SHA1 mismatch",
        E.SIZE: "Size mismatch",
        E.BOTH: "Both SHA1 and Size mismatch",
    }

    for error_type, message in error_messages.items():
        if len(errors[error_type]) > 0:
            print(f"{message}:\n- " + "\n- ".join([
                e['location'] + ': ' + e['info']['file'] for e in errors[error_type]
            ]))

    if len(errors[E.MISSING]) > 0:
        with open('urls', 'w') as f:
            for e in errors[E.MISSING]:
                f.writelines([f"{e['info']['url']}\n",
                              f"  dir={apps_dir}\n",
                              f"  out={e['info']['file']}\n"])
        print("Missing files URLs written to 'urls' file. "
              "You can use it with aria2 to download them.")

    if all(len(errors[e]) == 0 for e in errors):
        print("All files are present and correct.")


def check_apps(txt_files: list[str], apps_dir: str, *, dump: bool, sha1: bool):
    """Check apps in rapps-db repo."""
    files = txt_files or os.listdir(os.getcwd())
    files = [f for f in files if f.endswith('.txt')]
    errors = { E.INFO: [], E.MISSING: [], E.SHA1: [], E.SIZE: [], E.BOTH: [] }

    config = configparser.ConfigParser(interpolation=None)

    for file in files:
        config.clear()
        config.read(os.path.join(os.getcwd(), file))
        sections = [s for s in config.sections() if s in SECTIONS]
        for section in sections:
            info = extract_info(config[section])
            if info is None:
                continue

            if dump:
                print(info['file'])
            else:
                print('.', end='', flush=True)
                ret = check_info(info, apps_dir, sha1=sha1)
                if ret == E.PASS:
                    continue
                errors[ret].append({
                    'location': f"{file}[{section}]",
                    'info': info,
                })

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
                        help="Skip all checking. Only dump the list of all apps.")
    parser.add_argument('--no-sha1', action='store_true',
                        help="Skip SHA1 check. Only check file size.")
    args = parser.parse_args()

    apps_dir = os.path.abspath(args.apps_dir)
    os.makedirs(apps_dir, exist_ok=True)
    check_apps(txt_files=args.txt_file,
               apps_dir=apps_dir,
               dump=args.dump,
               sha1=not args.no_sha1)
