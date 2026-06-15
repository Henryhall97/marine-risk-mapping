"""Generate a formatted Excel version of the survey-data manual action tracker.

One-off helper for the IWC survey-data sourcing workstream. Run with:
    uv run --with openpyxl python scripts/gen_survey_action_tracker_xlsx.py

Writes docs/survey_data_action_tracker.xlsx (mirrors §7 of
docs/survey_data_status.md). Re-run to regenerate from the data below.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

OUT = Path(__file__).resolve().parents[1] / "docs" / "survey_data_action_tracker.xlsx"

# Palette (navy / teal theme, matching the project reports).
NAVY = "1F3A5F"
TEAL = "2A9D8F"
LIGHT = "EAF2F1"
AMBER = "F4A261"
GREY = "6C757D"
WHITE = "FFFFFF"
LINKBLUE = "0563C1"

THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

STATUS_OPTIONS = [
    "Not started",
    "Drafted",
    "Submitted",
    "Partial data received",
    "Complete",
]

# Shared body reused by the science-center distance/effort requests. {program},
# {region}, {center} are substituted per row; {extra} adds program-specific asks.
_REQUEST_TEMPLATE = (
    "Subject: Data request - {program} line-transect perpendicular distances & "
    "effort for a non-commercial whale ship-strike risk model\n"
    "\n"
    "Dear {recipient},\n"
    "\n"
    "I am developing a non-commercial, open-methodology whale-vessel "
    "collision-risk model for US waters that aligns with the IWC ship-strike "
    "reporting standard (Leaper et al. 2026) and IWC model-based abundance "
    "guidance (Miller & Kelly 2023). To estimate absolute whale density with a "
    "distance-sampling / density-surface model (R Distance/mrds/dsm), I would "
    "like to request the underlying {program} survey data for {region}.\n"
    "\n"
    "Specifically, in whatever tabular form you can share:\n"
    "1. On-effort tracklines / effort segments (segment geometry + length, "
    "platform, date).\n"
    "2. Sightings with perpendicular distances (or the raw angle/reticle or "
    "bearing+range needed to derive them) and group size per sighting.\n"
    "3. Detection covariates - Beaufort/sea state, observer, platform "
    "(ship/aerial), and any double-platform / independent-observer flags that "
    "support a perception-bias (MRDS) g(0) correction.\n"
    "\n"
    "Three quick questions so I represent the data honestly:\n"
    "- Are double-platform / independent-observer data available (can "
    "perception g(0) be estimated), or should I treat g(0)=1 and flag deep "
    "divers as biased-low?\n"
    "- What are the redistribution / citation / storage terms? I will comply "
    "fully - I can keep raw data private and publish only derived density "
    "surfaces + code, and will cite the program and any required "
    "acknowledgements.\n"
    "- Is any of this already public via OBIS-SEAMAP / InPort at this "
    "resolution, so I avoid asking for something already released?\n"
    "{extra}"
    "\n"
    "This is unfunded / non-commercial research; results and code will be "
    "openly available and intended to support ship-strike risk reduction. "
    "Happy to sign a data-use agreement and to share methods or outputs back "
    "with your team.\n"
    "\n"
    "Thank you very much for your time.\n"
    "\n"
    "[Your name, affiliation if any, contact]"
)


def _request(
    program: str, region: str, center: str, extra: str = "", recipient: str = "[name]"
) -> str:
    extra_block = f"\n{extra}\n" if extra else ""
    return _REQUEST_TEMPLATE.format(
        program=program,
        region=region,
        center=center,
        extra=extra_block,
        recipient=recipient,
    )


_AMAPPS_MSG = _request(
    "AMAPPS",
    "the US Atlantic, ideally covering North Atlantic right whale and the "
    "other large whales (fin, humpback, sei, sperm, minke). I can see the "
    "AMAPPS Northeast + Southeast aerial and shipboard cruises (2010-2023) "
    "hosted on OBIS-SEAMAP under your provider page, so I am asking for the "
    "on-effort tracklines + per-sighting perpendicular distances behind those "
    "observation layers",
    "NEFSC/SEFSC",
    recipient="Beth Josephson",
)

_GOMMAPPS_MSG = _request(
    "GoMMAPPS",
    "the Gulf of Mexico (Rice's whale, sperm, and other large whales)",
    "SEFSC",
    extra=(
        "Because Rice's whale is so rare, could you also indicate the "
        "approximate number of on-effort Rice's whale sightings in the "
        "GoMMAPPS dataset? I need this to decide whether a seasonal density "
        "surface is feasible or whether to pool years/seasons into a single "
        "annual surface with appropriately wide confidence intervals."
    ),
)

_SWFSC_MSG = _request(
    "SWFSC California Current (CCE / CalCurCEAS / ORCAWALE / CSCAPE)",
    "the US Pacific / California Current (blue, fin, humpback, sperm, gray, minke)",
    "SWFSC",
    extra=(
        "I will check the SWFSC ERDDAP server first for already-published "
        "line-transect data; this request is mainly for the detection-covariate "
        "and double-platform tables that may not be on ERDDAP."
    ),
)

_AFSC_PIFSC_MSG = _request(
    "[AFSC Gulf of Alaska/Bering/Aleutian | PIFSC HICEAS]",
    "[Alaska | Hawaii / central Pacific]",
    "[AFSC | PIFSC]",
)

_NARWC_MSG = (
    "NARWC is a formal application + data-use agreement, NOT an email request:\n"
    "1. Go to narwc.org -> NARWC Databases -> Sightings Database; read the User "
    "Guide and Kenney (2015) review first.\n"
    "2. Submit the data-request / DUA application (account login required).\n"
    "3. Contact hpettis@neaq.org (Heather Pettis) for access questions.\n"
    "4. State the intended use EXPLICITLY: validation / presence layer only for "
    "an independent NARW DSM - NARWC is NOT used to fit absolute density (it "
    "lacks uniform perpendicular distances). This matches their data-sharing "
    "norms and is the truthful description of our use."
)

_DIVE_MSG = (
    "No external request - literature search. Compile published per-species "
    "dive-tag / TDR time-at-depth (cumulative time-at-depth CDF) for right, "
    "humpback, fin, blue, sperm, minke, sei, gray, and Rice's whales. Sources: "
    "DTAG / LIMPET / Argos studies, NOAA tech memos, peer-reviewed tagging "
    "papers. Output = whale_dive_cdf.csv built in Phase 3, reused for "
    "availability g(0) (Phase 3) and Pstrikedepth (Phase 4)."
)

_FOLLOW_THREAD_MSG = (
    "No separate message - this is answered inside the AMAPPS email thread "
    "(action #1). The three asks (data, redistribution terms, MRDS metadata) "
    "are deliberately bundled into one request so the science center replies "
    "once."
)

# num, action, where_to_send, link, blocks_t1, status, notes, message
ROWS = [
    (
        1,
        "Request raw AMAPPS perpendicular-distance + segmentable-effort tables "
        "(NARW + Atlantic large whales)",
        "Beth Josephson, NOAA Fisheries NEFSC (Woods Hole) - OBIS-SEAMAP "
        "provider 671; elizabeth.josephson@noaa.gov / 508.495.2362. Cc SEFSC "
        "for the Southeast cruises.",
        "https://seamap.env.duke.edu/provider/671",
        "YES",
        "Not started",
        "Cornerstone NARW dataset. CONFIRMED: AMAPPS NE+SE aerial+shipboard "
        "cruises (2010-2023) are on OBIS-SEAMAP under provider 671 (Beth "
        "Josephson, NEFSC data manager). Observations downloadable there; "
        "request the on-effort tracklines + perpendicular distances behind "
        "them. Send FIRST; fold actions 2 & 3 into the same email.",
        _AMAPPS_MSG,
    ),
    (
        2,
        "Confirm redistribution / storage licence for the AMAPPS data received",
        "Same reply thread as #1 (Beth Josephson, NEFSC)",
        "https://seamap.env.duke.edu/provider/671",
        "YES",
        "Not started",
        "Decides whether raw data can live in repo or only derived surfaces + "
        "code may be published. Also check the OBIS-SEAMAP per-dataset terms "
        "of use.",
        _FOLLOW_THREAD_MSG,
    ),
    (
        3,
        "Confirm double-platform / MRDS perception-bias metadata is in the deliverable",
        "Same reply thread as #1 (Beth Josephson, NEFSC)",
        "https://seamap.env.duke.edu/provider/671",
        "YES",
        "Not started",
        "Sets GO-full (g(0)-corrected) vs GO-caveated (g(0)=1, divers flagged "
        "biased-low) for NARW. NEFSC shipboard cruises run two teams; confirm "
        "the independent-observer fields are included.",
        _FOLLOW_THREAD_MSG,
    ),
    (
        4,
        "Pull Rice's-whale GoMMAPPS sighting count -> set seasonal-vs-annual DSM grain",
        "SEFSC + NOAA InPort (GoMMAPPS record)",
        "https://www.fisheries.noaa.gov/inport/item-browse?searchterm=GoMMAPPS",
        "no",
        "Not started",
        "Low n likely -> pool years into one annual surface with wide CV.",
        _GOMMAPPS_MSG,
    ),
    (
        5,
        "Apply for NARWC data-use agreement (NARW validation / presence layer)",
        "narwc.org application (login) -> hpettis@neaq.org (Heather Pettis)",
        "https://www.narwc.org/sightings-database.html",
        "no",
        "Not started",
        "Formal DUA, not an email. State use = validation/presence ONLY, not "
        "density fitting.",
        _NARWC_MSG,
    ),
    (
        6,
        "Inventory published per-species dive-tag / TDR time-at-depth for "
        "whale_dive_cdf.csv",
        "Literature search (no external request)",
        "https://scholar.google.com/scholar?q=whale+dive+time-at-depth+TDR+DTAG",
        "no",
        "Not started",
        "Single-source in Phase 3; reused for availability g(0) + Phase-4 "
        "Pstrikedepth.",
        _DIVE_MSG,
    ),
    (
        7,
        "Request SWFSC California Current line-transect distance + effort",
        "SWFSC ERDDAP first, then SWFSC data manager",
        "https://coastwatch.pfeg.noaa.gov/erddap/index.html",
        "no",
        "Not started",
        "Second validated region after NARW. Much may already be on ERDDAP.",
        _SWFSC_MSG,
    ),
    (
        8,
        "Request AFSC / PIFSC distance + effort (region-by-region)",
        "AFSC / PIFSC via NOAA InPort",
        "https://www.fisheries.noaa.gov/inport/item-browse?searchterm=HICEAS",
        "no",
        "Not started",
        "Background queue. AFSC sparse; PIFSC HICEAS few large-whale strike targets.",
        _AFSC_PIFSC_MSG,
    ),
]

HEADERS = [
    "#",
    "Action",
    "Where to send",
    "Link",
    "Blocks Tranche 1",
    "Status",
    "Owner",
    "Date sent",
    "Notes",
    "Full request message",
]

COL_WIDTHS = [4, 40, 34, 28, 13, 18, 13, 13, 40, 90]
# 1-based column indices.
COL_NUM, COL_ACTION, COL_WHERE, COL_LINK = 1, 2, 3, 4
COL_BLOCKS, COL_STATUS, COL_OWNER, COL_DATE = 5, 6, 7, 8
COL_NOTES, COL_MSG = 9, 10


def _style_header(cell):
    cell.font = Font(bold=True, color=WHITE, size=11)
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Action tracker"
    last_col = len(HEADERS)
    last_col_letter = get_column_letter(last_col)

    # Title row.
    ws.merge_cells(f"A1:{last_col_letter}1")
    t = ws["A1"]
    t.value = (
        "Survey-Data Sourcing - Manual Action Tracker (IWC migration, gates Phase 3)"
    )
    t.font = Font(bold=True, color=WHITE, size=14)
    t.fill = PatternFill("solid", fgColor=TEAL)
    t.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 26

    # Subtitle / legend row.
    ws.merge_cells(f"A2:{last_col_letter}2")
    s = ws["A2"]
    s.value = (
        "Status: Not started -> Drafted -> Submitted -> Partial data received "
        "-> Complete   |   'Blocks Tranche 1' = gates NARW->GO exit condition. "
        "Links are clickable. Mirror of docs/survey_data_status.md §7. "
        "Last updated 2026-06-14."
    )
    s.font = Font(italic=True, color="333333", size=9)
    s.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 28

    # Header row (row 3).
    hdr = 3
    for col, name in enumerate(HEADERS, start=1):
        _style_header(ws.cell(row=hdr, column=col, value=name))
    ws.row_dimensions[hdr].height = 30

    # Data rows.
    for i, row in enumerate(ROWS):
        num, action, where, link, blocks, status, notes, message = row
        r = hdr + 1 + i
        zebra = LIGHT if i % 2 else WHITE
        values = {
            COL_NUM: num,
            COL_ACTION: action,
            COL_WHERE: where,
            COL_LINK: link,
            COL_BLOCKS: blocks,
            COL_STATUS: status,
            COL_OWNER: "",
            COL_DATE: "",
            COL_NOTES: notes,
            COL_MSG: message,
        }
        for col, val in values.items():
            c = ws.cell(row=r, column=col, value=val)
            c.border = BORDER
            c.fill = PatternFill("solid", fgColor=zebra)
            wrap = col in (COL_ACTION, COL_WHERE, COL_LINK, COL_NOTES, COL_MSG)
            c.alignment = Alignment(
                horizontal="center"
                if col in (COL_NUM, COL_BLOCKS, COL_STATUS, COL_DATE)
                else "left",
                vertical="top",
                wrap_text=wrap,
            )
            if col == COL_NUM:
                c.font = Font(bold=True, color=NAVY)
            elif col == COL_LINK:
                c.hyperlink = val
                c.font = Font(color=LINKBLUE, underline="single", size=9)
            elif col == COL_MSG:
                c.font = Font(size=8, color="222222")
            elif col == COL_BLOCKS:
                if val == "YES":
                    c.fill = PatternFill("solid", fgColor=AMBER)
                    c.font = Font(bold=True, color="5A3000")
                else:
                    c.font = Font(color=GREY)
        ws.row_dimensions[r].height = 210

    # Dropdown validation on the Status column for the data rows.
    first = hdr + 1
    last = hdr + len(ROWS)
    status_letter = get_column_letter(COL_STATUS)
    dv = DataValidation(
        type="list",
        formula1='"{}"'.format(",".join(STATUS_OPTIONS)),
        allow_blank=False,
    )
    dv.add(f"{status_letter}{first}:{status_letter}{last}")
    ws.add_data_validation(dv)

    # Column widths.
    for idx, width in enumerate(COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    # Freeze header + first two cols, enable autofilter.
    ws.freeze_panes = "C4"
    ws.auto_filter.ref = f"A{hdr}:{last_col_letter}{last}"
    ws.sheet_view.showGridLines = False

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"Wrote {OUT} ({len(ROWS)} actions)")


if __name__ == "__main__":
    main()
