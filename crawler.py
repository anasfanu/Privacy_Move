#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawler.py
=================
Crawl (merayap) SEMUA data yang ada di dalam sebuah folder secara rekursif:
- Mendata semua file & subfolder (nama, ukuran, tanggal modifikasi, ekstensi)
- Membaca isi file teks (txt, csv, json, xml, html, md, log, py, dll.)
- Mengekstrak data terstruktur dari file JSON / CSV / Excel
- Menyimpan hasil crawling ke:
    * report.csv   -> daftar semua file + metadata
    * content.jsonl-> isi/teks tiap file (1 baris = 1 file)
    * summary.txt  -> ringkasan hasil crawl

Cara pakai:
    python crawler.py <path_folder>
    python crawler.py ./data --output hasil_crawl --max-size 2097152

Contoh (default):
    python crawler.py .
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Konfigurasi tipe file
# ---------------------------------------------------------------------------

# Ekstensi yang dianggap sebagai "file teks" dan akan dibaca isinya
TEXT_EXTENSIONS = {
    ".txt", ".csv", ".tsv", ".json", ".jsonl", ".xml", ".html", ".htm",
    ".md", ".rst", ".log", ".ini", ".cfg", ".conf", ".yaml", ".yml",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go",
    ".rb", ".php", ".sh", ".bat", ".sql", ".env", ".toml",
}

# Ekstensi file data terstruktur
JSON_EXTENSIONS = {".json", ".jsonl"}
CSV_EXTENSIONS = {".csv", ".tsv"}
EXCEL_EXTENSIONS = {".xlsx", ".xls"}

# Batas default ukuran file yang boleh dibaca isinya (2 MB)
DEFAULT_MAX_SIZE = 2 * 1024 * 1024


# ---------------------------------------------------------------------------
# Fungsi bantu
# ---------------------------------------------------------------------------

def is_text_file(path: Path) -> bool:
    """Kembalikan True jika file termasuk kategori teks yang bisa dibaca."""
    ext = path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return True
    # Jika tidak punya ekstensi, cek 1024 byte pertama:
    # file dianggap teks bila tidak mengandung banyak byte null.
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        return b"\x00" not in chunk
    except OSError:
        return False


def human_size(num_bytes: int) -> str:
    """Ubah ukuran byte menjadi bentuk mudah dibaca (KB/MB/GB)."""
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def read_text_content(path: Path, max_size: int) -> str | None:
    """Baca isi file teks. Kembalikan None jika terlalu besar / gagal."""
    if path.stat().st_size > max_size:
        return None
    for encoding in ("utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return None


def extract_json_data(path: Path, max_size: int):
    """Ekstrak data dari file JSON / JSONL. Kembalikan objek Python atau None."""
    if path.stat().st_size > max_size:
        return None
    try:
        if path.suffix.lower() == ".jsonl":
            records = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            return records
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def extract_csv_data(path: Path, max_size: int):
    """Ekstrak data dari file CSV/TSV menjadi list of dict. Atau None."""
    if path.stat().st_size > max_size:
        return None
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            return [dict(row) for row in reader]
    except (OSError, csv.Error, UnicodeDecodeError):
        return None


def extract_excel_data(path: Path, max_size: int):
    """Ekstrak data dari file Excel memakai pandas/openpyxl jika tersedia."""
    if path.stat().st_size > max_size:
        return None
    try:
        import pandas as pd  # type: ignore
        sheets = pd.read_excel(path, sheet_name=None)
        return {name: df.to_dict(orient="records") for name, df in sheets.items()}
    except ImportError:
        print(f"[!] Modul pandas/openpyxl tidak terpasang, lewati: {path}")
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core crawler
# ---------------------------------------------------------------------------

def crawl_folder(root_dir: Path, output_dir: Path, max_size: int) -> dict:
    """
    Crawl seluruh isi folder `root_dir` secara rekursif.
    Hasil disimpan ke `output_dir` (report.csv, content.jsonl, summary.txt).
    Kembalikan ringkasan (summary) dalam bentuk dict.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.csv"
    content_path = output_dir / "content.jsonl"
    summary_path = output_dir / "summary.txt"

    rows = []          # metadata per file untuk report.csv
    total_size = 0
    file_count = 0
    dir_count = 0
    ext_counter: dict[str, int] = {}
    errors = []

    with open(report_path, "w", newline="", encoding="utf-8") as fp_report, \
         open(content_path, "w", encoding="utf-8") as fp_content:

        writer = csv.writer(fp_report)
        writer.writerow([
            "path", "name", "extension", "type", "size_bytes", "size_human",
            "modified", "sha256_16", "has_structured_data", "structured_rows",
        ])

        for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
            current = Path(dirpath)

            # Catat subfolder
            for d in dirnames:
                dir_count += 1
                dp = current / d
                try:
                    st = dp.stat()
                    writer.writerow([
                        str(dp), d, "", "DIR", 0, "-",
                        datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                        "", False, 0,
                    ])
                except OSError as e:
                    errors.append(f"Gagal stat folder {dp}: {e}")

            # Catat & proses file
            for fname in filenames:
                fp = current / fname
                file_count += 1
                ext = fp.suffix.lower() or "(tanpa ekstensi)"
                ext_counter[ext] = ext_counter.get(ext, 0) + 1
                try:
                    st = fp.stat()
                except OSError as e:
                    errors.append(f"Gagal stat file {fp}: {e}")
                    continue

                total_size += st.st_size

                # Hash singkat untuk identifikasi konten
                sha = ""
                try:
                    h = hashlib.sha256()
                    with open(fp, "rb") as fh:
                        h.update(fh.read(min(st.st_size, max_size)))
                    sha = h.hexdigest()[:16]
                except OSError:
                    pass

                # Ekstraksi data terstruktur
                structured = None
                if ext in JSON_EXTENSIONS:
                    structured = extract_json_data(fp, max_size)
                elif ext in CSV_EXTENSIONS:
                    structured = extract_csv_data(fp, max_size)
                elif ext in EXCEL_EXTENSIONS:
                    structured = extract_excel_data(fp, max_size)

                n_rows = 0
                if isinstance(structured, list):
                    n_rows = len(structured)
                elif isinstance(structured, dict):
                    n_rows = sum(len(v) if isinstance(v, list) else 1
                                 for v in structured.values())

                writer.writerow([
                    str(fp), fname, ext, "FILE", st.st_size, human_size(st.st_size),
                    datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    sha, structured is not None, n_rows,
                ])

                # Simpan isi / data ke content.jsonl (1 baris = 1 file)
                entry = {
                    "path": str(fp),
                    "name": fname,
                    "extension": ext,
                    "size_bytes": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                }
                if structured is not None:
                    entry["data"] = structured
                elif is_text_file(fp):
                    text = read_text_content(fp, max_size)
                    if text is not None:
                        entry["text"] = text
                fp_content.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Ringkasan
    summary = {
        "root": str(root_dir.resolve()),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_files": file_count,
        "total_directories": dir_count,
        "total_size_bytes": total_size,
        "total_size_human": human_size(total_size),
        "extensions": dict(sorted(ext_counter.items(), key=lambda x: -x[1])),
        "errors": errors,
        "outputs": {
            "report_csv": str(report_path),
            "content_jsonl": str(content_path),
            "summary_txt": str(summary_path),
        },
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("HASIL CRAWLING FOLDER\n")
        f.write("=" * 40 + "\n")
        f.write(f"Folder sumber   : {summary['root']}\n")
        f.write(f"Waktu crawl     : {summary['generated_at']}\n")
        f.write(f"Total file      : {summary['total_files']}\n")
        f.write(f"Total folder    : {summary['total_directories']}\n")
        f.write(f"Total ukuran    : {summary['total_size_human']}\n\n")
        f.write("Jumlah file per ekstensi:\n")
        for ext, count in summary["extensions"].items():
            f.write(f"  {ext:<20} {count}\n")
        if errors:
            f.write("\nKesalahan saat crawling:\n")
            for e in errors:
                f.write(f"  - {e}\n")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crawl semua data di dalam folder secara rekursif."
    )
    parser.add_argument("folder", nargs="?", default=".",
                        help="Folder yang akan di-crawl (default: folder saat ini)")
    parser.add_argument("--output", "-o", default="crawl_output",
                        help="Folder hasil crawling (default: crawl_output)")
    parser.add_argument("--max-size", type=int, default=DEFAULT_MAX_SIZE,
                        help="Ukuran maksimum file yang dibaca isinya dalam byte "
                             f"(default: {DEFAULT_MAX_SIZE})")
    args = parser.parse_args()

    root = Path(args.folder)
    if not root.is_dir():
        print(f"[!] Folder tidak ditemukan: {root}", file=sys.stderr)
        return 1

    print(f"[*] Mulai crawl folder: {root.resolve()}")
    summary = crawl_folder(root, Path(args.output), args.max_size)
    print(f"[+] Selesai! {summary['total_files']} file, "
          f"{summary['total_directories']} folder, "
          f"total {summary['total_size_human']}")
    print(f"[+] Laporan : {summary['outputs']['report_csv']}")
    print(f"[+] Konten  : {summary['outputs']['content_jsonl']}")
    print(f"[+] Ringkasan: {summary['outputs']['summary_txt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
