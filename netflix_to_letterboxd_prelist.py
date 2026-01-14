#!/usr/bin/env python3
"""
netflix_to_letterboxd_prelist.py

Step 1: Generate
  - prelist_review.csv   (candidate films to validate; you fill Approve)
  - discarded_tv.csv     (discarded TV/episodes for auditing)

Step 2: Generate
  - letterboxd_import.csv  (Letterboxd CSV import format: Title,WatchedDate[,Tags])
    from the edited prelist where Approve=1

Usage:
  # Step 1
  python netflix_to_letterboxd_prelist.py ViewingActivity.csv --start 2025-11-01 --end 2025-12-31

  # Step 2 (after you edit prelist_review.csv)
  python netflix_to_letterboxd_prelist.py ViewingActivity.csv --from-prelist prelist_review.csv --tag netflix
"""

from __future__ import annotations
import argparse
import re
from pathlib import Path
import pandas as pd


# --- STRONG TV markers: safe to discard immediately ---
TV_STRONG_PHRASES = [
    # Netflix pattern with colon + keyword
    r":\s*Temporada\b",
    r":\s*Season\b",
    r":\s*Episodio\b",
    r":\s*Episode\b",
    r":\s*Cap[ií]tulo\b",
    r":\s*Chapter\b",
    r":\s*Serie\b",            # "The Office (U.K.): Serie 2: ..."
    r"\bSerie\s+\d+\b",        # "Serie 2" even without colon (extra safety)
    r":\s*Series\b",           # sometimes English UI: ": Series 2"
    r"\bSeries\s+\d+\b",

    # Common compact episode codes
    r"\bS\d+\s*:\s*E\d+\b",
    r"\bT\d+\s*:\s*E\d+\b",
    r"\bS\d+E\d+\b",
]

TV_STRONG_REGEX = re.compile("|".join(TV_STRONG_PHRASES), flags=re.IGNORECASE)

# --- SOFT TV markers: ambiguous (films also use Part/Parte/Deel) ---
TV_SOFT_PHRASES = [
    r":\s*Parte\s+\d+\b",
    r":\s*Part\s+\d+\b",
    r":\s*Deel\s+\d+\b",

    # Sometimes appears without colon; keep as soft
    r"\bParte\s+\d+\b",
    r"\bPart\s+\d+\b",
    r"\bDeel\s+\d+\b",
]

TV_SOFT_REGEX = re.compile("|".join(TV_SOFT_PHRASES), flags=re.IGNORECASE)

# If a SOFT-marked "show base" appears at least this many times, treat it as TV.
TV_SOFT_MIN_COUNT = 3

# Ambiguous markers: do NOT discard, only flag for review (optional)
UNCERTAIN_REGEX = re.compile(r"\b(Parte|Part|Special|Especial)\b", flags=re.IGNORECASE)

def yyyymmdd(s: str | None) -> str:
    if not s:
        return "ALL"
    return pd.to_datetime(s).strftime("%Y%m%d")

def make_range_prefix(start: str | None, end: str | None) -> str:
    return f"{yyyymmdd(end)}_{yyyymmdd(start)}"


def normalize_title(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def tv_reason(title: str) -> str | None:
    m = TV_REGEX.search(title)
    if not m:
        return None
    return f"tv_match:{m.group(0)}"


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_csv", help="Netflix CSV with columns Title,Date")
    ap.add_argument("--start", default=None, help="Start date inclusive (YYYY-MM-DD)")
    ap.add_argument("--end", default=None, help="End date inclusive (YYYY-MM-DD)")
    ap.add_argument("--date-format", default="%m/%d/%y", help="Netflix date format (default: %%m/%%d/%%y)")
    ap.add_argument("--outdir", default=".", help="Output directory")
    ap.add_argument("--tag", default=None, help='Optional tag for Letterboxd import, e.g. "netflix"')
    ap.add_argument("--from-prelist", default=None, help="Edited prelist_review.csv with Approve filled (1/0)")
    ap.add_argument("--interactive", action="store_true",
                help="Prompt in CMD for each candidate row (Enter=yes, n=no, q=quit) and build letterboxd_import.csv")
    return ap.parse_args()


def load_netflix(path: str, date_format: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8", engine="python", on_bad_lines="skip")
    if "Title" not in df.columns or "Date" not in df.columns:
        raise SystemExit(f"Expected columns Title,Date. Found: {list(df.columns)}")

    df["Title"] = df["Title"].map(normalize_title)

    dt = pd.to_datetime(df["Date"], format=date_format, errors="coerce")
    bad = dt.isna().sum()
    if bad:
        print(f"[warn] {bad} rows had unparseable dates and were dropped.")
    df = df.loc[~dt.isna()].copy()
    df["WatchedDate"] = dt.loc[~dt.isna()].dt.strftime("%Y-%m-%d")
    return df


def apply_window(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if start:
        s = pd.to_datetime(start)
        df = df.loc[pd.to_datetime(df["WatchedDate"]) >= s].copy()
    if end:
        e = pd.to_datetime(end)
        df = df.loc[pd.to_datetime(df["WatchedDate"]) <= e].copy()
    return df





def build_letterboxd_import(prelist_path: str, tag: str | None) -> pd.DataFrame:
    df = pd.read_csv(prelist_path, encoding="utf-8", engine="python")
    required = {"Title", "WatchedDate", "Approve"}
    if not required.issubset(df.columns):
        raise SystemExit(f"Prelist must contain {sorted(required)}. Found: {list(df.columns)}")

    approve = df["Approve"].astype(str).str.strip().isin({"1", "true", "True", "yes", "YES", "y", "Y"})
    approved = df.loc[approve, ["Title", "WatchedDate"]].copy()

    # Canonical Letterboxd import columns (always present, even if blank)
    cols = [
        "LetterboxdURI", "tmdbID", "imdbID", "Title", "Year", "Directors",
        "Rating", "Rating10", "WatchedDate", "Rewatch", "Tags", "Review"
    ]

    # Create an empty DF with the right columns (no scalar-values error)
    out = pd.DataFrame(columns=cols)

    if not approved.empty:
        # Start with blanks
        out = pd.DataFrame("", index=range(len(approved)), columns=cols)
        out["Title"] = approved["Title"].astype(str).values
        out["WatchedDate"] = approved["WatchedDate"].astype(str).values
        if tag:
            out["Tags"] = tag

        out = out.drop_duplicates(subset=["Title", "WatchedDate"]).reset_index(drop=True)

    return out



def interactive_approve(prelist: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    """
    prelist columns: Title, WatchedDate, Uncertain, Approve (Approve can be blank)
    Returns prelist with Approve filled ("1" or "0") interactively.
    """
    window_txt = ""
    if start or end:
        window_txt = f" between {start or '...'} and {end or '...'}"
    print("\nInteractive review:")
    print("  Enter = YES (include) | n = NO (exclude) | q = quit\n")

    approved = []
    for i, row in prelist.iterrows():
        title = row["Title"]
        watched_date = row["WatchedDate"]
        uncertain = row.get("Uncertain", False)

        prefix = "[?] " if bool(uncertain) else ""
        prompt = f"{i+1}/{len(prelist)} {prefix}{title}  (date: {watched_date})\nIs this a movie that you watched{window_txt}? "
        ans = input(prompt).strip().lower()

        if ans == "q":
            print("[info] Quit requested. Saving progress so far.")
            # Keep unanswered as blank
            prelist.loc[prelist.index[:len(approved)], "Approve"] = approved
            return prelist

        if ans == "" or ans in {"y", "yes"}:
            approved.append("1")
        elif ans in {"n", "no"}:
            approved.append("0")
        else:
            # Unknown input: treat as NO (safe default), but you can change this behavior
            approved.append("0")

        # small visual spacer
        print()

    prelist["Approve"] = approved
    return prelist

import re
import pandas as pd

SHOW_EXTRACTOR = re.compile(
    r"^(?P<show>.+?):\s*(Temporada|Season|Episodio|Episode|Cap[ií]tulo|Chapter|Seizoen|Aflevering|Serie|Series|Parte|Part|Deel)\b",
    flags=re.IGNORECASE
)


def extract_show_name(title: str) -> str:
    t = str(title).strip()
    m = SHOW_EXTRACTOR.search(t)
    if m:
        return m.group("show").strip()

    # Fallback: first token before colon
    if ":" in t:
        return t.split(":", 1)[0].strip()

    return t

def make_prelist_and_discarded(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = df.copy()
    work["Show"] = work["Title"].map(extract_show_name)

    # Count how often each "show base" appears
    show_counts = work["Show"].value_counts()

    # Compute match types
    strong = work["Title"].str.contains(TV_STRONG_REGEX, na=False)
    soft = work["Title"].str.contains(TV_SOFT_REGEX, na=False)

    # Soft becomes TV only if repeated enough times
    soft_repeated = work["Show"].map(show_counts).fillna(0).astype(int) >= TV_SOFT_MIN_COUNT

    is_tv = strong | (soft & soft_repeated)

    discarded = work.loc[is_tv].copy()
    # Reason for audit
    discarded["DiscardReason"] = ""
    discarded.loc[strong, "DiscardReason"] = "strong_tv_marker"
    discarded.loc[~strong & soft & soft_repeated, "DiscardReason"] = "soft_marker_repeated"
    discarded["ShowCount"] = discarded["Show"].map(show_counts).astype(int)

    # Candidates (films + ambiguous leftovers)
    prelist = work.loc[~is_tv].copy()

    # Optional: keep a flag to surface ambiguous soft markers for manual attention
    prelist["Uncertain"] = prelist["Title"].str.contains(TV_SOFT_REGEX, na=False)
    prelist["Approve"] = ""

    # Clean outputs
    discarded_out = discarded[["Title", "WatchedDate", "DiscardReason", "Show", "ShowCount"]].copy()
    discarded_out = discarded_out.drop_duplicates(subset=["Title", "WatchedDate"]).reset_index(drop=True)
    discarded_out = discarded_out.sort_values(by=["ShowCount", "WatchedDate", "Title"], ascending=[False, False, True]).reset_index(drop=True)

    prelist_out = prelist[["Title", "WatchedDate", "Uncertain", "Approve"]].copy()
    prelist_out = prelist_out.drop_duplicates(subset=["Title", "WatchedDate"]).reset_index(drop=True)
    prelist_out = prelist_out.sort_values(by=["WatchedDate", "Uncertain", "Title"], ascending=[False, False, True]).reset_index(drop=True)

    return prelist_out, discarded_out

def interactive_tv_group_review(discarded_tv: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Takes discarded_tv with columns: Title, WatchedDate, DiscardReason
    Returns:
      - confirmed_tv: stays discarded
      - moved_back: rows that user says are NOT TV (move back to candidates)
    """
    if discarded_tv.empty:
        return discarded_tv.copy(), discarded_tv.iloc[0:0].copy()

    tv = discarded_tv.copy()
    tv["Show"] = tv["Title"].map(extract_show_name)

    # Group by show, biggest first (so Avatar with 10 eps comes before Bojack with 1)
    grp_sizes = tv.groupby("Show").size().sort_values(ascending=False)

    confirmed = []
    moved_back = []

    print("\nTV review:")
    print("  Enter = YES (this is TV, keep discarded)")
    print("  n     = NO  (NOT TV → move all rows of this group back to candidates)")
    print("  q     = quit\n")

    for idx, (show, nrows) in enumerate(grp_sizes.items(), start=1):
        block = tv[tv["Show"] == show].sort_values(["WatchedDate", "Title"], ascending=[True, True]).copy()

        show_line = f"{show.upper()} ({nrows} episodes)"
        print(f"{idx}/{len(grp_sizes)} {show_line}")
        ans = input("This is a TV show, right? [Enter=yes, n=no, l=list episodes, q=quit] ").strip().lower()

        if ans == "l":
            print("-" * 70)
            for _, r in block.iterrows():
                print(f"{r['WatchedDate']}  {r['Title']}")
            ans = input("This is a TV show, right? [Enter=yes, n=no, q=quit] ").strip().lower()

        print()


        if ans == "q":
            print("[info] Quit requested. Saving progress so far.")
            # Remaining groups stay as confirmed by default (safer to keep discarded)
            confirmed.append(block)
            break

        if ans == "" or ans in {"y", "yes"}:
            confirmed.append(block)
        elif ans in {"n", "no"}:
            moved_back.append(block)
        else:
            # Unknown input: default to YES (keep discarded)
            confirmed.append(block)

    confirmed_tv = pd.concat(confirmed, ignore_index=True) if confirmed else tv.iloc[0:0].copy()
    moved_back_df = pd.concat(moved_back, ignore_index=True) if moved_back else tv.iloc[0:0].copy()

    # Drop helper column Show from outputs
    if "Show" in confirmed_tv.columns:
        confirmed_tv = confirmed_tv.drop(columns=["Show"])
    if "Show" in moved_back_df.columns:
        moved_back_df = moved_back_df.drop(columns=["Show"])

    return confirmed_tv, moved_back_df




def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.from_prelist:
        out = build_letterboxd_import(args.from_prelist, args.tag)
        out_file = outdir / "letterboxd_import.csv"
        out.to_csv(out_file, index=False, encoding="utf-8")
        print(f"[ok] Letterboxd import written: {out_file} ({len(out)} rows)")
        print("[info] Columns are Title,WatchedDate[,Tags] (Letterboxd import format).")
        return

    df = load_netflix(args.input_csv, args.date_format)
    df = apply_window(df, args.start, args.end)
    prefix = make_range_prefix(args.start, args.end)

    prelist, discarded = make_prelist_and_discarded(df)

    # Interactive grouped confirmation of discarded TV rows
    # (lets you audit Avatar-like blocks and fix false positives)
    confirmed_tv, moved_back = interactive_tv_group_review(discarded)

    # Save the confirmed TV discard list (audit)
    discarded = confirmed_tv

    # If you said "NO this is not TV" for a group, move it back into film candidates
    if not moved_back.empty:
        moved_back_as_candidates = moved_back[["Title", "WatchedDate"]].copy()
        moved_back_as_candidates["Uncertain"] = False
        moved_back_as_candidates["Approve"] = ""  # will be handled by your film interactive pass

        # Merge back into prelist and re-sort
        prelist = pd.concat([prelist, moved_back_as_candidates], ignore_index=True)
        prelist = prelist.drop_duplicates(subset=["Title", "WatchedDate"]).reset_index(drop=True)
        prelist = prelist.sort_values(by=["WatchedDate", "Uncertain", "Title"],
                                      ascending=[False, False, True]).reset_index(drop=True)

   # Always write audit files
    prelist_file   = outdir / f"{prefix}_prelist_review.csv"
    discarded_file = outdir / f"{prefix}_discarded_tv.csv"


    prelist.to_csv(prelist_file, index=False, encoding="utf-8")
    discarded.to_csv(discarded_file, index=False, encoding="utf-8")

    print(f"[ok] Wrote candidates (review) -> {prelist_file} ({len(prelist)} rows)")
    print(f"[ok] Wrote discarded TV audit  -> {discarded_file} ({len(discarded)} rows)")

    # NEW: interactive approval -> immediately build Letterboxd import
    if args.interactive:
        prelist = interactive_approve(prelist, args.start, args.end)
        # Save the answered prelist (so you keep a record)
        prelist.to_csv(prelist_file, index=False, encoding="utf-8")

        out = build_letterboxd_import(str(prelist_file), args.tag)
        out_file = outdir / f"{prefix}_letterboxd_import.csv"
        out.to_csv(out_file, index=False, encoding="utf-8", na_rep="")


        print(f"[ok] Letterboxd import written: {out_file} ({len(out)} rows)")
        print("[info] Upload letterboxd_import.csv to Letterboxd import.")
        return




if __name__ == "__main__":
    main()
