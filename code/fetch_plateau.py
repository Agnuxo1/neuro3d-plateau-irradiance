"""Selective download of one PLATEAU CityGML tile via HTTP range requests.

Project PLATEAU city packages are single large ZIPs (Hiroshima 2022 v3 is ~1 GB).
Only a couple of members are needed for a district pilot, so this reads the ZIP
central directory over HTTP range requests and extracts just those members.

The downloaded data stays local: it is never republished (PLATEAU site policy).
"""

from __future__ import annotations

import argparse
import io
import os
import urllib.request
import zipfile

UA = "plateau-award-pilot/1.0 (+local research use)"


class HttpFile(io.RawIOBase):
    """Minimal seekable read-only file over HTTP range requests."""

    def __init__(self, url: str, chunk: int = 1 << 20):
        self.url = url
        self.chunk = chunk
        self._pos = 0
        self._cache: dict[int, bytes] = {}
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            self.size = int(r.headers["Content-Length"])
            if r.headers.get("Accept-Ranges", "").lower() != "bytes":
                # Many S3/CDN hosts omit the header but still honour ranges.
                pass
        self.bytes_fetched = 0

    # --- io plumbing -----------------------------------------------------
    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_SET:
            self._pos = offset
        elif whence == os.SEEK_CUR:
            self._pos += offset
        else:
            self._pos = self.size + offset
        return self._pos

    def _fetch(self, index: int) -> bytes:
        if index in self._cache:
            return self._cache[index]
        start = index * self.chunk
        end = min(start + self.chunk, self.size) - 1
        req = urllib.request.Request(
            self.url, headers={"User-Agent": UA, "Range": f"bytes={start}-{end}"}
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        self.bytes_fetched += len(data)
        if len(self._cache) > 512:
            self._cache.clear()
        self._cache[index] = data
        return data

    def read(self, n: int = -1) -> bytes:  # type: ignore[override]
        if n is None or n < 0:
            n = self.size - self._pos
        n = min(n, self.size - self._pos)
        out = bytearray()
        while n > 0:
            idx = self._pos // self.chunk
            off = self._pos - idx * self.chunk
            buf = self._fetch(idx)[off : off + n]
            if not buf:
                break
            out += buf
            self._pos += len(buf)
            n -= len(buf)
        return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--grep", default="")
    ap.add_argument("--extract", nargs="*", default=[])
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    hf = HttpFile(a.url)
    zf = zipfile.ZipFile(hf)
    if a.list:
        for i in zf.infolist():
            if a.grep and a.grep not in i.filename:
                continue
            print(f"{i.file_size:>12} {i.filename}")
    for name in a.extract:
        dest = os.path.join(a.out, os.path.basename(name))
        os.makedirs(a.out, exist_ok=True)
        with zf.open(name) as src, open(dest, "wb") as dst:
            dst.write(src.read())
        print("extracted", dest, os.path.getsize(dest))
    print(f"# bytes fetched over HTTP: {hf.bytes_fetched/1e6:.1f} MB of {hf.size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
