"""Generates samples/faq.pdf — a minimal, valid, zero-dependency PDF so the
smoke test exercises the PDF extraction path. Run once; the output is
committed. Usage: python scripts/make_sample_pdf.py
"""

from pathlib import Path

FAQ_LINES = [
    "Harper's Bike Hire - Frequently Asked Questions (2026)",
    "",
    "Where are you?",
    "Unit 4, Riverside Yard, Ashford Lane, Marlow SL7 1DD - two minutes",
    "from the Thames Path. Free customer parking on site.",
    "",
    "What are your opening hours?",
    "April to September: 9am to 6pm, seven days a week.",
    "October to March: 9am to 4:30pm, closed Mondays.",
    "Last hire leaves 2 hours before closing.",
    "",
    "Do I need to book in advance?",
    "Weekends and school holidays usually sell out, so booking ahead is",
    "strongly recommended. Midweek walk-ins are normally fine.",
    "",
    "Is there a minimum age?",
    "Riders must be 14 or over to hire their own bike. Under-14s ride",
    "child bikes booked by an accompanying adult. E-bike riders must be",
    "18 or over with photo ID.",
    "",
    "Are helmets included?",
    "Yes - every hire includes a helmet, lock and puncture repair kit at",
    "no extra charge. You are welcome to bring your own helmet.",
    "",
    "Can you suggest routes?",
    "Yes. We keep free laminated route cards for three loops: the 12 km",
    "family towpath loop, the 28 km Chilterns gravel loop, and the 45 km",
    "road circuit. Staff will happily mark up quieter alternatives.",
    "",
    "What if I get a puncture or breakdown?",
    "Every bike carries a repair kit. If you cannot fix it, call the",
    "shop - within 10 km we come to you free of charge during opening",
    "hours; beyond that a £15 recovery fee applies.",
    "",
    "Can I take the bikes on the train?",
    "Standard bikes, yes (subject to the operator's cycle policy).",
    "E-bikes are not permitted on rail replacement buses.",
]


def _escape(line: str) -> str:
    return line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf(lines: list[str]) -> bytes:
    stream = "BT\n/F1 11 Tf\n14 TL\n72 780 Td\n"
    for line in lines:
        stream += f"({_escape(line)}) Tj T*\n"
    stream += "ET"
    stream_bytes = stream.encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream_bytes), stream_bytes),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()
    return bytes(out)


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "samples" / "faq.pdf"
    target.write_bytes(build_pdf(FAQ_LINES))
    print(f"wrote {target} ({target.stat().st_size} bytes)")
