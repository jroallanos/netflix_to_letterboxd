# netflix_to_letterboxd

I was watching Netflix before I had a Letterboxd account. Since Netflix lets you download your viewing history, I wanted a simple way to upload my past watches into my Letterboxd diary.

This project takes the raw Netflix viewing history (downloadable as a `.csv` file from `"netflix.com/settings/viewed/"`) you can download from your Netflix settings and, after a manual validation, can be uploaded to Letterboxd (`"letterboxd.com/import/"`).

---

## What this does

✅ Reads your Netflix viewing history CSV (`Title,Date`)  
✅ Filters by a date range (`--start`, `--end`)  
✅ Detects and groups TV shows/episodes (so they don’t end up as films)  
✅ Interactive validation in the terminal:
 - Confirm grouped TV shows once (fast)
 - Approve movies one-by-one (press Enter to include)
 
✅ Exports a **Letterboxd-ready CSV** (canonical header format)  
✅ Writes audit files so you can inspect what was discarded / kept

---

## Requirements

- Python 3.10+
- `pandas`

Install dependencies:

```bash
py -m pip install pandas
````

---

## Running from the terminal (Windows)

This is a command-line tool. You run it from a terminal (Command Prompt, PowerShell, or Git Bash).

1. Open a terminal
2. Go to the folder where the script and the `NetflixViewingHistory.csv` that you downloaded are:

```bash
cd "path\to\your\folder"
```

3. Run the following command (explained further down below):

```bash
py netflix_to_letterboxd_prelist.py NetflixViewingHistory.csv --start 2018-01-01 --end 2018-12-31 --interactive
```

---

## How to use

### 1) Download your Netflix viewing history

Go to:
[https://netflix.com/settings/viewed/](https://netflix.com/settings/viewed/)

Download the CSV (example filename: `NetflixViewingHistory.csv`).

---

### 2) Run the interactive pipeline

Example: import only watches from 2018

```bash
py netflix_to_letterboxd_prelist.py NetflixViewingHistory.csv --start 2018-01-01 --end 2018-12-31 --interactive
```

You’ll be prompted in two stages:

**A) TV grouping**

* You’ll see something like: `FRIENDS (10 episodes)`
* Press **Enter** to confirm it’s TV (kept discarded)
* Type `n` to move it back to film candidates (in case of false positives)
* Type `l` to list episodes for that show (optional)
* Type `q` to quit

**B) Film approval**

* For each film candidate, press **Enter** to include it
* Type `n` to exclude it
* Type `q` to stop early (progress is saved)

---

### 3) Upload to Letterboxd

After the run, you’ll get a file like:

```
<ENDYYYYMMDD>_<STARTYYYYMMDD>_letterboxd_import.csv
```

Upload it here:
[https://letterboxd.com/import/](https://letterboxd.com/import/)

---

## Output files

The script generates audit + import CSVs using the date window as a prefix:

* `<END>_<START>_prelist_review.csv`

  Candidate films + approval column (for transparency / debugging)

* `<END>_<START>_discarded_tv.csv`

  TV rows that were discarded (includes grouping/discard reasons)

* `<END>_<START>_letterboxd_import.csv` ✅

  Final file to upload to Letterboxd (canonical CSV header, blank values allowed)

---

## Notes / limitations

* Netflix logs “plays”, not guaranteed full watches.
  That’s why this tool uses an interactive validation step.
* Matching is title-based (no TMDb/IMDB ID resolution yet).
  For most imports this is good enough, but remakes / same-title films might need manual corrections in Letterboxd.

---

## License

MIT