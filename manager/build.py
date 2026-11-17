"""Wrap page.html (the publishable page body) in a document skeleton -> index.html for local / PWA use."""
from pathlib import Path
here = Path(__file__).parent
body = (here / "page.html").read_text("utf-8")
head = ('<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}[hidden]{display:none!important}</style></head><body>\n')
(here / "index.html").write_text(head + body + "\n</body></html>\n", "utf-8")
print("index.html written", len(body))
