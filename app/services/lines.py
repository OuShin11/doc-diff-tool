import fitz

PDF_PATH = "data/before.pdf"
doc = fitz.open(PDF_PATH)
page = doc[0]
rd = page.get_text("rawdict")

lines = []
for b in rd.get("blocks", []):
    for ln in b.get("lines", []):
        buf = []
        for sp in ln.get("spans", []):
            for ch in sp.get("chars", []):
                buf.append(ch.get("c", ""))
        text = "".join(buf).strip()
        if text:
            lines.append(text)

print("lines =", len(lines))
for i, t in enumerate(lines[:20]):
    print(i, len(t), t)
