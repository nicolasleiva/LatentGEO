#!/usr/bin/env python3
# fetch_and_save.py
import asyncio, aiohttp, base64, re, argparse, logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fetch_and_save")


async def fetch(session, url, is_binary=False, timeout=30):
    try:
        async with session.get(url, timeout=timeout) as r:
            if r.status == 200:
                if is_binary:
                    data = await r.read()
                    ct = r.headers.get("Content-Type", "application/octet-stream")
                    return f"data:{ct};base64,{base64.b64encode(data).decode('utf-8')}"
                else:
                    return await r.text()
    except Exception:
        return None


async def inline_css(session, link, base_url):
    href = urljoin(base_url, link.get("href", ""))
    css = await fetch(session, href)
    if not css:
        return None
    resolved = re.sub(
        r'url\((?!["\']?(?:data:|https?:|ftp:))["\']?([^"\')]+)["\']?\)',
        lambda m: f"url({urljoin(href,m.group(1))})",
        css,
    )
    return f"<style>{resolved}</style>"


async def inline_images(session, soup, base_url):
    imgs = soup.find_all("img")
    tasks = []
    for img in imgs:
        src = img.get("src")
        if not src:
            continue
        url = urljoin(base_url, src)
        tasks.append((img, asyncio.create_task(fetch(session, url, is_binary=True))))
    for img, t in tasks:
        datauri = await t
        if datauri:
            img["src"] = datauri


async def inline_scripts(session, soup, base_url):
    scripts = soup.find_all("script", src=True)
    for s in scripts:
        src = urljoin(base_url, s["src"])
        txt = await fetch(session, src)
        if txt:
            new = soup.new_tag("script")
            new.string = txt
            s.replace_with(new)


async def download(url, out="page_offline.html"):
    if not urlparse(url).scheme:
        url = "https://" + url
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            html = await r.text(errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("link", rel="stylesheet")
        inlined = await asyncio.gather(*[inline_css(session, l, url) for l in links])
        for l, st in zip(links, inlined):
            if st:
                l.replace_with(BeautifulSoup(st, "html.parser"))
        await inline_images(session, soup, url)
        await inline_scripts(session, soup, url)
        if soup.head:
            base = soup.new_tag("base", href=url)
            soup.head.insert(0, base)
        with open(out, "w", encoding="utf-8") as f:
            f.write(str(soup))
        return out


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print("Usage: fetch_and_save.py <url> [-o outfile]")
    else:
        out = "page_offline.html"
        if len(sys.argv) > 2:
            out = sys.argv[2]
        asyncio.run(download(url, out))
        print("Saved", out)
