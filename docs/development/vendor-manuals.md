# Vendor programming manuals

`tests/wire_forms.py` cites these documents by page. They are **not committed** —
redistribution terms are unclear, so `.git/info/exclude` keeps them local. Download
them into `docs/` with these exact filenames to check a citation.

## Citation convention — read this before checking a page number

A citation like `p.749` is the **PDF file page position** — i.e. "go to page 749" in
your PDF viewer (equivalently, `fitz`/pypdf 0-based index 748). It is **not** the number
printed in the page footer. These manuals carry front matter (title, contents, install
notes), so the footer number runs *behind* the file position by a fixed per-document
amount:

| Guide | footer = file position + | e.g. cited `p.N` shows footer |
|---|---|---|
| Legacy `RC01020-E01C` | 0 (they coincide) | `p.88` → footer `88` |
| Modern `SDS800XHD` / `SDS5000X` | −1 | `p.749` → footer `748` |
| SPD3303X `QS0503X-E01B` | −8 | `p.38` → footer `30` |
| SDG `PG02-E05B` | −12 | `p.27` → footer `15` |

So if you open a cited page and the footer shows a slightly lower number, that is
expected — you are on the right page (the content is what matters, and it will match).
File position is used because it is the one number a reader can jump to deterministically
in any viewer without knowing the offset. The offsets above let you cross-check against
the footer if you prefer.

| Filename | Document | Source |
|---|---|---|
| `SDS_DigitalOscilloscopes_ProgrammingGuide_RC01020-E01C.pdf` | Siglent Digital Oscilloscopes Programming Guide (legacy dialect) | siglentna.com/wp-content/uploads/dlm_uploads/2017/10/ProgrammingGuide_forSDS-1-1.pdf |
| `SPD3303X_QuickStart_QS0503X-E01B.pdf` | Siglent SPD3303X/-E Quick Start | batronix.com/pdf/Siglent/SPD3303X/SPD3303X_QuickStart.pdf |
| `SDG_ProgrammingGuide_PG02-E05B.pdf` | Siglent SDG Series Programming Guide | siglentna.com/wp-content/uploads/dlm_uploads/2023/08/SDG_Programming-Guide_PG02-E05B.pdf |
| `34970A-34972A_CommandReference.pdf` | Agilent/Keysight 34970A/72A Command Reference | documentation.help/Keysight-34970A-34972A/documentation.pdf |
| `SDS800XHD_Series_ProgrammingGuide_EN11G.pdf` | Siglent SDS800X HD Programming Guide (modern dialect) | committed in `docs/` |
| `SDS5000X_ProgrammingGuide_EN11G.pdf` | Siglent SDS5000X Programming Guide (modern dialect) | committed in `docs/` |
| `4-5-6-MSO-6-LPD-Programmer-Manual-Tek.pdf` | Tektronix MSO 4/5/6 Programmer Manual | local only |

No manual is available for **LeCroy** or **TBS1102C**. Commands for those surfaces are
recorded `UNCITED` in the corpus and are not asserted.

**CI cannot verify a citation** — only a human with the PDF can. Treat a corpus entry
in review as a claim to be checked, not as a passing test.
