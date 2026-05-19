"""Download ReactOS apps.

This folder has files specifying app download information like this:

    [Section]
    Name = QEMU
    Version = 1.5.50
    License = GPL v2
    Category = 12
    URLSite = https://www.qemu.org/
    URLDownload = https://qemu.weilnetz.de/w32/2013/qemu-w32-setup-20130627.exe
    SHA1 = d5c45b5220951a2abbb3340d368c36d3140da83f
    SizeBytes = 13938504

    [Section.amd64]
    URLDownload = https://qemu.weilnetz.de/w64/2013/qemu-w64-setup-20130619.exe
    SHA1 = cfc87ee81c5943761182260ebb07afe60d32804a
    SizeBytes = 16281897

This script will download the file specified in [Section] group. Before
download, check for existing file and its hash value, skip if already exist.

For every txt file in this folder, download the app specified in [Section].
"""
import configparser
import hashlib
import logging
import os
import urllib.request

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("main")


def download_file(url, dest_path):
    """Download file from url to dest_path.

    Skips SSLError or URLError.
    """
    try:
        with urllib.request.urlopen(url) as response, \
                open(dest_path, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
    except (urllib.error.URLError, urllib.error.HTTPError):
        logger.exception("Error downloading %s", url)
        return False
    return True


def calculate_sha1(file_path):
    """Calculate SHA1 hash of the file at file_path."""
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        while True:
            data = f.read(65536)  # Read in 64KB chunks
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def extract_info(ini_file, section='Section'):
    """Extract URLDownload, SHA1, and SizeBytes from ini_file."""
    config = configparser.ConfigParser(interpolation=None)
    config.read(ini_file)

    if section not in config:
        logger.error("Section '%s' not found in %s.", section, ini_file)
        return None, None, None

    url_download = config[section].get('URLDownload')
    sha1 = config[section].get('SHA1')
    size_bytes = config[section].get('SizeBytes')

    if not url_download or not sha1 or not size_bytes:
        logger.error("URLDownload or SHA1 or SizeBytes missing in %s.", ini_file)
        return None, None, None

    return url_download, sha1.lower(), int(size_bytes)


def check_path(file_path):
    """Check if file at file_path exists."""
    if not os.path.exists(file_path):
        logger.debug("File %s does not exist.", file_path)
        return False
    return True


def check_hash(file_path, expected_sha1):
    """Check if file at file_path matches expected SHA1."""
    actual_sha1 = calculate_sha1(file_path)
    if actual_sha1 != expected_sha1:
        logger.error("SHA1 mismatch for %s.", file_path)
        logger.error("  Expected: %s, actual: %s.", expected_sha1, actual_sha1)
        return False
    return True


def check_size(file_path, expected_size):
    """Check if file at file_path matches expected size."""
    actual_size = os.path.getsize(file_path)
    if actual_size != expected_size:
        logger.error("Size mismatch for %s.", file_path)
        logger.error("  Expected: %d, actual: %d.", expected_size, actual_size)
        return False
    return True


def download_app(ini_file, section='Section'):
    """Download app specified in ini_file under given section."""
    url, sha1, size = extract_info(ini_file, section)
    if not url or not sha1 or not size:
        return

    file_name = os.path.basename(url)
    dest_path = os.path.join(os.getcwd(), 'apps', file_name)

    # Check if file already exists and verify size and SHA1
    if not check_path(dest_path, sha1, size):
        logger.info("Downloading '%s' from %s...", file_name, url)
        if download_file(url, dest_path) is False:
            return

    if not check_hash(dest_path, sha1) or not check_size(dest_path, size):
        return

    logger.info("Successfully downloaded and verified '%s'.", file_name)


if __name__ == "__main__":
    apps_dir = os.path.join(os.getcwd(), 'apps')
    os.makedirs(apps_dir, exist_ok=True)

    for file in os.listdir(os.getcwd()):
        if file.endswith('.txt'):
            ini_file_path = os.path.join(os.getcwd(), file)
            download_app(ini_file_path, section='Section')
