"""Prepare the exact public tokenizer asset for reproducible offline image startup."""
import hashlib
import os
from pathlib import Path
import urllib.request

URL = "https://raw.githubusercontent.com/zurawiki/tiktoken-rs/main/tiktoken-rs/assets/cl100k_base.tiktoken"
ORIGINAL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
EXPECTED = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"


def prepare():
    cache = Path(os.environ["TIKTOKEN_CACHE_DIR"])
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / hashlib.sha1(ORIGINAL.encode()).hexdigest()
    data = target.read_bytes() if target.exists() else None
    if data is None or hashlib.sha256(data).hexdigest() != EXPECTED:
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != EXPECTED:
            raise RuntimeError("Public tokenizer data checksum mismatch")
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.chmod(0o644)
        temporary.replace(target)
    import tiktoken
    assert tiktoken.get_encoding("cl100k_base").encode("Verified tokenizer")
    print("Checksum-verified tokenizer cache ready")


if __name__ == "__main__":
    prepare()
