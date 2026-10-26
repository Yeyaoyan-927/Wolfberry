"""从 Wikimedia Commons 下载枸杞实拍图（CC 授权，来源与授权可追溯）。

按「精确文件名」拉取，保证可复现（搜索结果顺序不稳定）。

用法：python scripts/fetch_images.py

输出：
    scripts/seed_assets/web/goji-web-N.jpg
    scripts/seed_assets/web/SOURCES.json   # 来源 / 作者 / 授权 / 原始地址

用途：演示数据。商用需遵守对应 CC 协议（署名等）。
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "seed_assets" / "web"
API = "https://commons.wikimedia.org/w/api.php"
UA = "wolfberry-demo/0.1 (contact: dev@example.com)"
THUMB_WIDTH = 1600

# 精确文件名（Wikimedia Commons）。需新增图片时在这里加一行。
FILES = [
    "File:Goji bessen.JPG",                                   # 干枸杞特写（满幅）
    "File:Goji dried berries.jpg",                            # 麻袋 + 铲勺
    "File:Lycium barbarum at Wolfberry Farm Berries Closeup Ningxia.jpg",  # 宁夏枸杞园特写（公有领域）
    "File:5656-Linxia-City-dried-Ningxia-gouji-berries.jpg",  # 临夏市场枸杞
]


def fetch_meta() -> list[dict]:
    titles = "|".join(FILES)
    params = {
        "action": "query",
        "format": "json",
        "titles": titles,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": str(THUMB_WIDTH),
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    out = []
    for page in (data.get("query") or {}).get("pages", {}).values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        meta = info.get("extmetadata") or {}
        out.append(
            {
                "title": page.get("title", ""),
                "thumb": info.get("thumburl") or info.get("url"),
                "width": info.get("thumbwidth") or info.get("width"),
                "height": info.get("thumbheight") or info.get("height"),
                "page": "https://commons.wikimedia.org/wiki/"
                + urllib.parse.quote(page.get("title", "").replace(" ", "_")),
                "license": (meta.get("LicenseShortName") or {}).get("value", ""),
                "artist": re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip(),
            }
        )
    return out


def download(item: dict, save_as: Path) -> bool:
    try:
        req = urllib.request.Request(item["thumb"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = resp.read()
    except Exception as exc:
        print(f"  [跳过] 下载失败 {item['title']}: {exc}")
        return False

    if len(data) < 30_000 or not data.startswith(b"\xff\xd8"):
        print(f"  [跳过] 非 JPEG 或文件过小：{item['title']}")
        return False

    save_as.write_bytes(data)
    print(f"  [下载] {save_as.name}  {len(data)//1024}KB  {item['license'] or '授权见来源页'}")
    return True


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    accepted = []

    for item in fetch_meta():
        if len(accepted) >= 4:
            break
        save_as = OUT_DIR / f"goji-web-{len(accepted) + 1}.jpg"
        if download(item, save_as):
            item["saved_as"] = save_as.name
            accepted.append(item)

    sources = [
        {
            "file": item["saved_as"],
            "title": item["title"],
            "source_page": item["page"],
            "license": item["license"] or "见来源页",
            "artist": item["artist"],
            "original_size": f'{item.get("width")}x{item.get("height")}',
            "usage": "演示数据。商用需遵守对应 CC 协议（CC BY-SA 需署名并以相同方式共享）",
        }
        for item in accepted
    ]
    (OUT_DIR / "SOURCES.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n成功 {len(sources)} 张，来源已写入 {OUT_DIR / 'SOURCES.json'}")

    if len(sources) < 2:
        print("下载不足 2 张，请检查网络后重试", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
