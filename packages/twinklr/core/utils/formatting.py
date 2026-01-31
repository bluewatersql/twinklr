import re
import unicodedata


def clean_audio_filename(name: str, replacement_char="_"):
    """
    Cleans an MP3 filename by removing invalid characters, standardizing
    spacing, and ensuring it is a valid filename.
    """
    # 1. Convert to ASCII and lowercase (optional, but good for standardization)
    # Normalize unicode data, encode to ascii and then decode back to string
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()

    # 2. Remove characters that aren't letters, numbers, spaces, or hyphens
    # This keeps characters safe for most file systems
    name = re.sub(r"[^a-z0-9\s-]", "", name)

    # 3. Replace spaces and hyphens with the chosen replacement character
    # Use re.sub to handle multiple consecutive spaces/hyphens as one
    name = re.sub(r"[-\s]+", replacement_char, name).strip(replacement_char)

    return name
