#!/usr/bin/env python3
"""Generate upi-qr.svg for the "Pay via UPI" dialog.

Usage: pip install qrcode && python3 scripts/make_upi_qr.py <upi-id> "<payee name>"
Keep UPI_ID / UPI_NAME in index.html in sync with the values used here.
"""
import sys
import urllib.parse
from pathlib import Path

import qrcode
import qrcode.image.svg

upi_id = sys.argv[1] if len(sys.argv) > 1 else "aromalponmana@oksbi"
name = sys.argv[2] if len(sys.argv) > 2 else "Aromal Santhosh"
uri = "upi://pay?" + urllib.parse.urlencode({"pa": upi_id, "pn": name, "cu": "INR"}, safe="@", quote_via=urllib.parse.quote)

qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
qr.add_data(uri)
qr.make(fit=True)
out = Path(__file__).resolve().parent.parent / "upi-qr.svg"
qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(out)
print(f"{out}  <-  {uri}")
