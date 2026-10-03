# PDF Toolkit

A modern desktop app for working with PDFs — drag & drop, live page preview, themes, and a Windows installer.

> **Looking for the original PDF Merger?** See release [v1.0](../../releases/tag/v1.0).

## Features (v2.0)
- **Merge** – combine PDFs, drag to reorder
- **Split** – by ranges, every N pages, or one file per page
- **Pages** – live preview, reorder, rotate, delete, keep/delete ranges, reverse
- **Compress** – Low (lossless), Medium, High
- 5 themes, progress bar, safe saving (never overwrites your source file)

## Install (Windows)
Download `PDF-Toolkit-Setup.exe` from the [latest release](../../releases/latest) and run it.

## Run from source
```
pip install -r requirements.txt
python pdf_toolkit.py
```

## Build it yourself
Run `build.bat`, then compile `installer.iss` with [Inno Setup](https://jrsoftware.org/isinfo.php).
