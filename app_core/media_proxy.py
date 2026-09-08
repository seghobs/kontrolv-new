"""Bounded CDN media fetching with DNS pinning and TLS verification."""
import ipaddress
import socket
import time
from urllib.parse import urlsplit

import urllib3

MAX_BYTES = 32 * 1024 * 1024
MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif", "video/mp4"}


class InvalidMedia(ValueError):
    pass


def resolve_target(url):
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        allowed = any(host == suffix or host.endswith("." + suffix)
                      for suffix in ("cdninstagram.com", "fbcdn.net"))
        if (parsed.scheme != "https" or not allowed or parsed.port not in (None, 443)
                or parsed.username is not None or parsed.password is not None
                or parsed.fragment or any(ord(c) < 33 for c in url)):
            raise InvalidMedia()
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ips = [entry[4][0] for entry in addresses]
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise InvalidMedia()
        return host, ips[0], (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
    except (ValueError, OSError) as error:
        raise InvalidMedia() from error


def fetch_media(url):
    host, ip, target = resolve_target(url)
    # Connect to the validated IP; retain the CDN hostname for SNI and certificate checks.
    pool = urllib3.HTTPSConnectionPool(
        ip, port=443, server_hostname=host, assert_hostname=host,
        cert_reqs="CERT_REQUIRED", timeout=urllib3.Timeout(connect=5, read=8),
    )
    response = None
    try:
        response = pool.urlopen("GET", target, headers={
            "Host": host, "User-Agent": "Instagram 275.0.0.27.98 Android",
            "Accept-Encoding": "identity",
        }, redirect=False, retries=False, preload_content=False)
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if response.status != 200 or content_type not in MEDIA_TYPES:
            raise InvalidMedia()
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise InvalidMedia()
        try:
            size = int(response.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise InvalidMedia() from error
        if size < 0 or size > MAX_BYTES:
            raise InvalidMedia()
        chunks, total = [], 0
        deadline = time.monotonic() + 20
        while True:
            chunk = response.read1(65536, decode_content=False)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES or time.monotonic() > deadline:
                raise InvalidMedia()
            chunks.append(chunk)
        return b"".join(chunks), content_type
    finally:
        if response is not None:
            response.close()
        pool.close()
