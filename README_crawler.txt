# Crawler Folder — Python

Script `crawler.py` untuk crawling (merayap) **semua data** di dalam sebuah folder secara rekursif.

## Fitur
- ✅ Jalan ke semua subfolder (`os.walk`)
- ✅ Metadata tiap file: path, nama, ekstensi, ukuran, tanggal modifikasi, hash SHA-256
- ✅ Membaca isi file teks (`.txt`, `.md`, `.log`, `.py`, `.html`, `.xml`, `.yaml`, dll.)
- ✅ Ekstraksi data terstruktur dari `.json`, `.jsonl`, `.csv`, `.tsv` (dan `.xlsx` bila `pandas`+`openpyxl` terpasang)
- ✅ Ringkasan jumlah file per ekstensi dan total ukuran
- ✅ Tanpa dependensi eksternal (hanya modul standar Python)

## Cara pakai

```bash
# Crawl folder saat ini
python crawler.py

# Crawl folder tertentu
python crawler.py /path/ke/folder

# Atur folder output & batas ukuran file yang dibaca isinya (byte)
python crawler.py ./data --output hasil --max-size 1048576
```

## Hasil keluaran (`crawl_output/`)

| File | Isi |
|---|---|
| `report.csv` | Daftar semua file & folder + metadata (ukuran, tanggal, hash, jumlah baris data) |
| `content.jsonl` | Isi/data tiap file — 1 baris JSON per file (`text` untuk file teks, `data` untuk JSON/CSV) |
| `summary.txt` | Ringkasan: total file, folder, ukuran, jumlah per ekstensi, error |

## Contoh output `content.jsonl`

```json
{"path": "data/warga.csv", "name": "warga.csv", "extension": ".csv", "size_bytes": 47, "modified": "2026-11-02T14:32:26", "data": [{"nama": "Andi", "umur": "25", "kota": "Jakarta"}, {"nama": "Budi", "umur": "30", "kota": "Bandung"}]}
{"path": "data/catatan.txt", "name": "catatan.txt", "extension": ".txt", "size_bytes": 42, "modified": "2026-11-02T14:32:26", "text": "Halo ini file catatan biasa.\nBaris kedua.\n"}
```

## Catatan keamanan
- File lebih besar dari `--max-size` (default 2 MB) hanya didata metadatanya, isinya tidak dibaca (hemat memori).
- Error akses file/folder dicatat di `summary.txt`, proses tetap lanjut.
