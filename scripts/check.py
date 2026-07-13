"""Check ReactOS apps.

This script checks rapps-db repo containing app spec files with the schema:
    https://reactos.org/wiki/RAPPS#File_Schema

This script will check the file specified in [Section] group (for now).
- Files absent or have mismatched size and hash are writen to a 'urls' file,
  which can be used for aria2 to download them.
- Files have only one mismatch between size and hash are considered to have
  suspiciously wrong size and hash. Please check the spec files.
"""
import configparser
import enum
import hashlib
import os
import sys
import urllib.parse


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


def check_section(section):
    """Check app specified in ini_file under given section."""
    if section.get('URLDownload') is None:
        return E.PASS, None

    url, file, sha1, size = extract_info(section)
    if not sha1 or not size:
        return E.INFO, section.name

    dest_path = os.path.join(os.getcwd(), 'apps', file)

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


def check_apps():
    """Check apps in rapps-db repo."""
    apps_dir = os.path.join(os.getcwd(), 'apps')
    os.makedirs(apps_dir, exist_ok=True)

    files = sys.argv[1:] if len(sys.argv) > 1 else os.listdir(os.getcwd())
    errors = { E.INFO: [], E.MISSING: [], E.SHA1: [], E.SIZE: [], E.BOTH: [] }

    config = configparser.ConfigParser(interpolation=None)
    sections = ["Section", "Section.amd64"]

    for file in files:
        if not file.endswith('.txt'):
            continue
        config.read(os.path.join(os.getcwd(), file))
        for section in config.sections():
            if section not in sections:
                continue
            err, args = check_section(config[section])
            if err == E.PASS:
                continue
            if err == E.INFO:
                errors[err].append(f"{file}[{args}]")
            else:
                errors[err].append(args)
        config.clear()
        print('.', end='', flush=True)

    print("\nMissing SHA1 or SizeBytes:\n- " + "\n- ".join(errors[E.INFO]))
    print("Missing files:\n- " + "\n- ".join(errors[E.MISSING]))
    print("SHA1 mismatch:\n- " + "\n- ".join(errors[E.SHA1]))
    print("Size mismatch:\n- " + "\n- ".join(errors[E.SIZE]))
    print("Both SHA1 and Size mismatch:\n- " + "\n- ".join(errors[E.BOTH]))

    if len(errors[E.MISSING]) > 0:
        with open('urls', 'w') as f:
            for url, file in errors[E.MISSING]:
                f.writelines([f"{url}\n", f"  out=apps/{file}\n"])
        print("Missing files URLs written to 'urls' file. "
              "You can use it with aria2 to download them.")

if __name__ == "__main__":
    check_apps()
