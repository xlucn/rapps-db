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
from collections import defaultdict

SECTIONS = ["Section", "Section.amd64"]


class E(enum.Enum):
    """Return codes for check_apps."""

    PASS = 0
    INFO = 1
    MISS = 2
    SHA1 = 3
    SIZE = 4
    BOTH = 5


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


def extract_all_info(txt_files: list[str]):
    """Extract info from all .txt files in rapps-db repo."""
    files = txt_files or os.listdir(os.getcwd())
    files = [f for f in files if f.endswith('.txt')]

    config = configparser.ConfigParser(interpolation=None)

    all_info = []
    for file in files:
        config.clear()
        config.read(os.path.join(os.getcwd(), file))
        sections = [s for s in config.sections() if s in SECTIONS]
        for section in sections:
            info = extract_info(config[section])
            if info is not None:
                info['app_file'] = file
                info['section'] = section
                all_info.append(info)

    return all_info


def calc_sha1(file_path: str) -> str:
    """Calculate SHA1 hash of the file at file_path."""
    with open(file_path, 'rb') as f:
        return hashlib.file_digest(f, 'sha1').hexdigest()


def check_info(info: dict, apps_dir: str, *, skip_sha1: bool):
    """Check app specified in ini_file under given section."""
    dest_path = os.path.join(apps_dir, info['file'])

    # Check complete info
    if not info['sha1'] or not info['size']:
        return E.INFO

    # Check file existence
    if not os.path.exists(dest_path):
        return E.MISS

    # Check size and SHA1
    # Use `or` to short-circuit the SHA1 check if skip_sha1 is True
    sha1_match = skip_sha1 or (calc_sha1(dest_path) == info['sha1'].lower())
    size_match = os.path.getsize(dest_path) == int(info['size'])
    if not sha1_match and not size_match:
        return E.BOTH
    if not sha1_match and size_match:
        return E.SHA1
    if not size_match and sha1_match:
        return E.SIZE

    return E.PASS


def check_all_info(all_info: list[dict], apps_dir: str, *, skip_sha1: bool):
    """Check apps in rapps-db repo."""
    errors = { E.INFO: [], E.MISS: [], E.SHA1: [], E.SIZE: [], E.BOTH: [] }
    error_messages = {
        E.INFO: "Missing SHA1 or SizeBytes",
        E.MISS: "Missing files",
        E.SHA1: "SHA1 mismatch",
        E.SIZE: "Size mismatch",
        E.BOTH: "Both SHA1 and Size mismatch",
    }

    for info in all_info:
        print('.', end='', flush=True)
        ret = check_info(info, apps_dir, skip_sha1=skip_sha1)
        if ret == E.PASS:
            continue
        errors[ret].append({
            'location': "{app_file}[{section}]".format_map(info),
            'info': info,
        })

    for error_type, message in error_messages.items():
        if len(errors[error_type]) > 0:
            print(f"\n{message}:\n- " + "\n- ".join([
                e['location'] + ': ' + e['info']['file'] for e in errors[error_type]
            ]))

    if len(errors[E.MISS]) > 0:
        with open('urls', 'w') as f:
            for e in errors[E.MISS]:
                f.writelines([f"{e['info']['url']}\n",
                              f"  dir={apps_dir}\n",
                              f"  out={e['info']['file']}\n"])
        print("Missing files URLs written to 'urls' file. "
              "You can use it with aria2 to download them.")

    if all(len(errors[e]) == 0 for e in errors):
        print("All files are present and correct.")


def check_duplicates(all_info: list[dict]):
    """Check if app filenames collides."""
    # Build a filename -> indices mapping
    positions = defaultdict(list)
    for index, info in enumerate(all_info):
        positions[info['file'].lower()].append(index)

    # Collect duplicated filenames and indices
    dups = {}
    for indices in positions.values():
        if len(indices) > 1:
            # flase positive if the url is the same
            if len({all_info[i]['url'] for i in indices}) == 1:
                continue
            dups[all_info[indices[0]]['file']] = indices

    if dups:
        print("\nDuplicate app filenames (case insensitive):")
        for filename, indices in dups.items():
            print(f"- {filename}")
            for i in indices:
                info = all_info[i]
                print(f"  - {info['app_file']}[{info['section']}]")


def check_unneeded(all_info: list[dict], apps_dir: str):
    """Check if any app file is not in the info specifications."""
    local_apps = set(os.listdir(apps_dir))
    info_apps = {info['file'] for info in all_info}
    unneeded_apps = local_apps.difference(info_apps)

    if unneeded_apps:
        print("\nUnneeded app files:")
        for filename in unneeded_apps:
            print(f"- {filename}")


def main():
    """Parse arguments and initiate the check."""
    parser = argparse.ArgumentParser(description="Check ReactOS apps "
                                     "for sha1 and size mismatches.")
    parser.add_argument('txt_file', nargs='*',
                        help="INI files to check. If not specified, all .txt "
                        "files in the current directory will be checked.")
    parser.add_argument('-d', '--apps-dir', default='./apps',
                        help="Directory to check for downloaded apps. "
                        "Default is 'apps' in the current directory.")
    parser.add_argument('-S', '--no-sha1', action='store_true',
                        help="Skip SHA1 check. Only check file size.")
    args = parser.parse_args()

    apps_dir = os.path.abspath(args.apps_dir)
    if not os.path.isdir(apps_dir):
        print(f"Error: '{apps_dir}' is not a valid directory.")
        print("Please create the directory or specify a valid one using -d.")
        exit(1)

    apps_info = extract_all_info(txt_files=args.txt_file)
    check_all_info(apps_info, apps_dir=apps_dir, skip_sha1=args.no_sha1)
    check_duplicates(apps_info)
    check_unneeded(apps_info, apps_dir)


if __name__ == "__main__":
    main()
