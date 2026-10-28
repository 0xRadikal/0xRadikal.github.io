#!/usr/bin/env python3
"""Validate the host-root files of https://0xradikal.github.io/ (stdlib only).

    python tools/check.py          # local files
    python tools/check.py --live   # also fetch the deployed site and compare
"""
import datetime as dt
import json
import re
import struct
import sys
import urllib.request
import urllib.robotparser
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "https://0xradikal.github.io"
PROJECTS = ["/Free-Telegram-Proxy/", "/Free-v2ray-Configs/", "/profile-card/"]
CRAWLERS = ["*", "Googlebot", "Googlebot-Image", "Bingbot", "Applebot", "OAI-SearchBot", "GPTBot",
            "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User", "PerplexityBot",
            "Perplexity-User", "Google-Extended", "Applebot-Extended", "DuckDuckBot", "YandexBot", "CCBot"]
errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)
    return cond


def text(name):
    return (ROOT / name).read_text(encoding="utf-8")


def png_size(b):
    return struct.unpack(">II", b[16:24]) if b[:8] == b"\x89PNG\r\n\x1a\n" else None


def check_robots(src):
    check(not src.startswith("\ufeff") and "\r" not in src, "robots.txt: no BOM, LF line endings")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(src.splitlines())
    urls = [HOST + "/", HOST + "/llms.txt", HOST + "/favicon.ico", HOST + "/.well-known/security.txt"] + \
           [HOST + p for p in PROJECTS] + [HOST + p + "sitemap.xml" for p in PROJECTS[:2]]
    for ua in CRAWLERS:
        for u in urls:
            check(rp.can_fetch(ua, u), f"robots.txt blocks {ua} from {u}")
    check(not re.search(r"(?im)^\s*disallow\s*:\s*\S", src), "robots.txt: unexpected non-empty Disallow")
    groups = re.findall(r"(?im)^\s*user-agent\s*:\s*(\S+)", src)
    check(groups == ["*"], f"robots.txt: expected a single '*' group, got {groups}")
    # Only the fields every major parser accepts. Google supports exactly these
    # four; google/robotstxt lists content-signal, crawl-delay, host, noindex...
    # as kUnsupportedTags (reported in Search Console), Lighthouse <= 12.x fails
    # its robots-txt audit on them and Bing's tester flags them as errors.
    for n, line in enumerate(src.splitlines(), 1):
        body = line.split("#", 1)[0].strip()
        if body:
            field = body.split(":", 1)[0].strip().lower() if ":" in body else None
            check(field in {"user-agent", "allow", "disallow", "sitemap"},
                  f"robots.txt line {n}: non-standard directive {body!r}")
    maps = rp.site_maps() or []
    check(f"{HOST}/sitemap.xml" in maps, "robots.txt: root sitemap index not listed")
    return maps


def check_sitemaps():
    idx = xml.dom.minidom.parseString(text("sitemap.xml").encode())
    check(idx.documentElement.tagName == "sitemapindex", "sitemap.xml must be a <sitemapindex>")
    children = [n.firstChild.data.strip() for n in idx.getElementsByTagName("loc")]
    root = xml.dom.minidom.parseString(text("sitemap-root.xml").encode())
    check(root.documentElement.tagName == "urlset", "sitemap-root.xml must be a <urlset>")
    pages = [n.firstChild.data.strip() for n in root.getElementsByTagName("loc")]
    for u in children + pages:
        check(u.startswith(HOST + "/"), f"sitemap: {u} is not on {HOST}")
    check(f"{HOST}/sitemap-root.xml" in children, "sitemap index must list sitemap-root.xml")
    return children, pages


def check_security(now):
    src = text(".well-known/security.txt")
    fields = [(k.lower(), v.strip()) for k, v in re.findall(r"(?m)^([A-Za-z-]+):\s*(.+)$", src)]
    names = [k for k, _ in fields]
    check("contact" in names, "security.txt: Contact is required")
    check(names.count("expires") == 1, "security.txt: exactly one Expires")
    check(names.count("preferred-languages") <= 1, "security.txt: at most one Preferred-Languages")
    for k, v in fields:
        if k in ("contact", "policy", "canonical", "encryption", "acknowledgments", "hiring"):
            check(v.startswith("https://") or v.startswith(("mailto:", "tel:")), f"security.txt: {k} must be https/mailto/tel")
    exp = dict(fields).get("expires", "")
    try:
        when = dt.datetime.fromisoformat(exp.replace("Z", "+00:00"))
        check(when - now > dt.timedelta(days=30), f"security.txt: Expires {exp} is within 30 days - renew it")
        check(when - now < dt.timedelta(days=366), f"security.txt: Expires {exp} is more than a year away (RFC 9116)")
    except ValueError:
        check(False, f"security.txt: Expires {exp!r} is not RFC 3339")
    check(f"Canonical: {HOST}/.well-known/security.txt" in src, "security.txt: Canonical must point to itself")
    return [v for k, v in fields if k in ("contact", "policy")]


def check_llms():
    src = text("llms.txt")
    lines = src.splitlines()
    check(lines and lines[0].startswith("# "), "llms.txt: must start with an H1")
    check(any(l.startswith("> ") for l in lines[1:4]), "llms.txt: blockquote summary right after the H1")
    links = re.findall(r"^- \[[^\]]+\]\((https://[^)]+)\)", src, re.M)
    check(len(links) >= 3, "llms.txt: expected a file list of links")
    return links


def check_home():
    src = text("index.html")
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', src, re.S)
    data = json.loads(m.group(1)) if check(m, "index.html: JSON-LD missing") else {"@graph": []}
    site = next((g for g in data["@graph"] if g.get("@type") == "WebSite"), {})
    check(site.get("url") == HOST + "/" and site.get("name"), "index.html: WebSite name/url")
    check(f'<link rel="canonical" href="{HOST}/">' in src, "index.html: canonical")
    icons = re.findall(r'<link rel="(?:icon|apple-touch-icon)" href="/([^"]+)"', src)
    check(icons, "index.html: no icon links")
    for f in icons:
        check((ROOT / f).is_file(), f"index.html: icon {f} missing")
    for want, f in [((48, 48), "favicon-48.png"), ((192, 192), "icon-192.png"), ((512, 512), "icon-512.png"), ((180, 180), "apple-touch-icon.png")]:
        check(png_size((ROOT / f).read_bytes()) == want, f"{f}: expected {want[0]}x{want[1]} PNG")
    ico = (ROOT / "favicon.ico").read_bytes()
    check(ico[:4] == b"\x00\x00\x01\x00" and struct.unpack("<H", ico[4:6])[0] >= 1, "favicon.ico: not an ICO")
    hrefs = re.findall(r'href="(/[^"]*)"', src)
    check(all(h.split("#")[0] in [p for p in PROJECTS] or (ROOT / h.lstrip("/")).is_file() for h in hrefs),
          f"index.html: local link to a missing target in {hrefs}")
    check(not (ROOT / "404.html").exists(), "404.html must not exist (it would override project 404s)")
    return icons


def check_indexnow():
    keys = [p for p in ROOT.glob("*.txt") if re.fullmatch(r"[A-Za-z0-9-]{8,128}", p.stem) and p.stem not in ("robots", "llms")]
    check(len(keys) == 1, f"expected exactly one IndexNow key file, found {[k.name for k in keys]}")
    for k in keys:
        check(k.read_text(encoding="utf-8").strip() == k.stem, f"{k.name}: content must equal the key")
    return [k.name for k in keys]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "0xradikal-root-check/1 (+https://github.com/0xRadikal/0xRadikal.github.io)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), b""


def live(files, external):
    for name, ctype in files:
        status, got, body = fetch(f"{HOST}/{name}")
        if check(status == 200, f"live /{name}: HTTP {status}"):
            check(body == (ROOT / name).read_bytes(), f"live /{name}: differs from the repository (not deployed yet?)")
            check(got.split(";")[0].strip() == ctype, f"live /{name}: Content-Type {got!r}, want {ctype}")
    for u in external:
        status, _, _ = fetch(u)
        check(status == 200, f"live: {u} -> HTTP {status}")
    status, _, _ = fetch(f"{HOST}/this-path-should-not-exist-{dt.date.today():%Y%m%d}/")
    check(status == 404, f"live: unknown path returns {status}, want 404")


def main():
    now = dt.datetime.now(dt.timezone.utc)
    maps = check_robots(text("robots.txt"))
    children, pages = check_sitemaps()
    contacts = check_security(now)
    links = check_llms()
    icons = check_home()
    keys = check_indexnow()
    check(set(maps) >= set(children) - {f"{HOST}/sitemap-root.xml"}, "robots.txt must list every project sitemap")
    if "--live" in sys.argv:
        files = [("robots.txt", "text/plain"), ("llms.txt", "text/plain"), ("sitemap.xml", "application/xml"),
                 ("sitemap-root.xml", "application/xml"), (".well-known/security.txt", "text/plain"),
                 ("index.html", "text/html"), ("favicon.ico", "image/vnd.microsoft.icon")] + \
                [(i, "image/png") for i in icons if i.endswith(".png")] + [(k, "text/plain") for k in keys]
        ext = sorted(set(children + pages + links + [c for c in contacts if c.startswith("https://")] +
                         [HOST + p for p in PROJECTS]) - {HOST + "/sitemap-root.xml", HOST + "/"})
        live(files, ext)
    for e in errors:
        print("FAIL:", e)
    print(f"{'OK' if not errors else 'FAILED'} - {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
