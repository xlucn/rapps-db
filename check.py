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
import hashlib
import logging
import os
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


def calculate_sha1(file_path):
    """Calculate SHA1 hash of the file at file_path."""
    with open(file_path, 'rb') as f:
        digest = hashlib.file_digest(f, 'sha1')
    return digest.hexdigest()

def extract_info(section):
    """Extract URLDownload, SHA1, and SizeBytes from one section in ini_file."""
    url_download = section.get('URLDownload')
    if url_download is None:
        return None, None, None, None
    filename = urllib.parse.unquote(os.path.basename(url_download).split('?')[0])
    filename = section.get('SaveAs', filename)

    sha1 = section.get('SHA1')
    size_bytes = section.get('SizeBytes')
    if not sha1 or not size_bytes:
        return url_download, filename, None, None

    return url_download, filename, sha1.lower(), int(size_bytes)


def check_hash(file_path, expected_sha1):
    """Check if file at file_path matches expected SHA1."""
    actual_sha1 = calculate_sha1(file_path)
    if actual_sha1 != expected_sha1:
        logger.debug("SHA1 mismatch for %s.", file_path)
        logger.debug("  Expected: %s, actual: %s.", expected_sha1, actual_sha1)
        return False
    return True


def check_size(file_path, expected_size):
    """Check if file at file_path matches expected size."""
    actual_size = os.path.getsize(file_path)
    if actual_size != expected_size:
        logger.debug("Size mismatch for %s.", file_path)
        logger.debug("  Expected: %d, actual: %d.", expected_size, actual_size)
        return False
    return True


def check_section(section, dump):
    """Check app specified in ini_file under given section."""
    url, file, sha1, size = extract_info(section)
    if not sha1 or not size:
        if url and file:
            logger.error("SHA1 or SizeBytes missing for %s.", file)
        return

    dest_path = os.path.join(os.getcwd(), 'apps', file)

    # Check if file already exists and verify size and SHA1
    if not os.path.exists(dest_path):
        logger.error("Missing %s", file)
        dump.writelines([f"{url}\n", f"  out=apps/{file}\n"])
        return

    # always check both
    sha1_checked = check_hash(dest_path, sha1)
    size_checked = check_size(dest_path, size)
    if not sha1_checked:
        if not size_checked:
            logger.error("Both sha1 and size mismatch for %s", file)
            dump.writelines([f"{url}\n", f"  out=apps/{file}\n"])
        else:
            logger.error("Sha1 mismatch but size match for %s", file)
    else:
        if not size_checked:
            logger.error("Size mismatch but sha1 match for %s", file)
        else:
            logger.debug("Found and checked '%s'.", file)


def check_apps(ini_file, dump, sections):
    """Check app for all sections specified in ini_file."""
    config = configparser.ConfigParser(interpolation=None)
    config.read(ini_file)
    for section in config.sections():
        if section not in sections:
            continue
        check_section(config[section], dump)


if __name__ == "__main__":
    apps_dir = os.path.join(os.getcwd(), 'apps')
    os.makedirs(apps_dir, exist_ok=True)

    sections = ["Section", "Section.amd64"]
    with open('urls', 'w') as dump:
        for file in os.listdir(os.getcwd()):
            if file.endswith('.txt'):
                ini_file_path = os.path.join(os.getcwd(), file)
                check_apps(ini_file_path, dump=dump, sections=sections)
    logger.info("Files needed re-download are exported to 'urls' file.")
    logger.info("The file can be used as input file for aria2.")
