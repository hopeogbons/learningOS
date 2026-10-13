import csv
import io
import re
import zipfile
from pathlib import Path
from .base import ExtractedSection, SourceError, SourceSnapshot

SUPPORTED = {'.pdf', '.md', '.txt', '.csv', '.xlsx', '.png', '.jpg', '.jpeg'}


def extract_file(data: bytes, filename: str, mime: str = '', vision=None) -> SourceSnapshot:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise SourceError('unsupported_type', 'Use PDF, Markdown, plain text, CSV, XLSX, JPG or PNG.')
    if not data:
        raise SourceError('empty_source', 'This file is empty.')
    sections = []
    if suffix == '.pdf':
        from pypdf import PdfReader
        try:
            pdf = PdfReader(io.BytesIO(data))
            if pdf.is_encrypted:
                raise SourceError('encrypted_pdf', 'Upload an unlocked PDF.')
            if len(pdf.pages)>100:raise SourceError('pdf_page_limit','Limit PDFs to 100 pages.')
            for page_number, page in enumerate(pdf.pages, 1):
                text = (page.extract_text() or '').strip()
                if text:
                    title = next((line.strip()[:160] for line in text.splitlines() if line.strip()), f'Page {page_number}')
                    sections.append(ExtractedSection(title, text, 'pdf', {'page': page_number, 'filename': filename}))
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError('unreadable_pdf', 'The PDF could not be read.') from exc
        if not sections:
            raise SourceError('ocr_required', 'No text found. Upload clear page photos for the verified vision path.')
    elif suffix in {'.md', '.txt'}:
        if len(data)>2*1024*1024:raise SourceError('text_size_limit','Limit text sources to 2 MiB.')
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise SourceError('text_encoding', 'Use UTF-8 encoded text.') from exc
        lines = text.splitlines()
        start, title = 1, Path(filename).stem
        for index, line in enumerate(lines, 1):
            if suffix == '.md' and re.match(r'^#{1,6}\s+\S', line):
                prior = '\n'.join(lines[start-1:index-1]).strip()
                if prior and re.sub(r'^#{1,6}\s+.*$', '', prior, flags=re.MULTILINE).strip():
                    sections.append(ExtractedSection(title, prior, 'text', {'filename': filename, 'heading': title, 'line_start': start, 'line_end': index-1}))
                start, title = index, re.sub(r'^#{1,6}\s+', '', line).strip()
        tail = '\n'.join(lines[start-1:]).strip()
        if tail and (suffix != '.md' or re.sub(r'^#{1,6}\s+.*$', '', tail, flags=re.MULTILINE).strip()):
            sections.append(ExtractedSection(title, tail, 'text', {'filename': filename, 'heading': title, 'line_start': start, 'line_end': len(lines)}))
    elif suffix == '.csv':
        if len(data)>2*1024*1024:raise SourceError('text_size_limit','Limit CSV sources to 2 MiB.')
        try:
            rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
            if sum(len(row) for row in rows)>10000:raise SourceError('spreadsheet_limit','Limit parsed spreadsheets to 10,000 cells.')
        except (UnicodeDecodeError, csv.Error) as exc:
            raise SourceError('unreadable_csv', 'The CSV could not be read as UTF-8.') from exc
        if rows:
            header = rows[0]
            for index, row in enumerate(rows[1:], 2):
                if any(cell.strip() for cell in row):
                    text = '\n'.join(f'{header[col] if col < len(header) else f"Column {col+1}"}: {value}' for col, value in enumerate(row))
                    sections.append(ExtractedSection(row[0][:160] or f'Row {index}', text, 'csv', {'filename': filename, 'row_start': index, 'row_end': index, 'column_start': 1, 'column_end': len(row), 'headers': header}))
    elif suffix == '.xlsx':
        from openpyxl import load_workbook
        from openpyxl.utils import get_column_letter
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries=archive.infolist()
                if len(entries)>1000 or sum(entry.file_size for entry in entries)>64*1024*1024:
                    raise SourceError('spreadsheet_limit','The expanded workbook exceeds the safe extraction limit.')
            book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            for sheet in book:
                if sheet.max_row*sheet.max_column>10000:
                    raise SourceError('spreadsheet_limit', 'Limit parsed spreadsheets to 10,000 cells per sheet.')
                rows = sheet.iter_rows(values_only=True)
                header = next(rows, ())
                for index, row in enumerate(rows, 2):
                    if any(value is not None for value in row):
                        text = '\n'.join(f'{header[col] if col < len(header) and header[col] is not None else f"Column {col+1}"}: {value}' for col, value in enumerate(row) if value is not None)
                        sections.append(ExtractedSection(f'{sheet.title} — {row[0] if row[0] is not None else index}'[:160], text, 'xlsx', {'filename': filename, 'sheet': sheet.title, 'cell_range': f'A{index}:{get_column_letter(len(row))}{index}'}))
            book.close()
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError('unreadable_spreadsheet', 'The spreadsheet could not be read.') from exc
    else:
        if (suffix == '.png' and not data.startswith(b'\x89PNG\r\n\x1a\n')) or (suffix in {'.jpg', '.jpeg'} and not data.startswith(b'\xff\xd8\xff')):
            raise SourceError('invalid_photo', 'The photo does not match its file type.')
        if vision is None:
            raise SourceError('vision_unavailable', 'Photo reading needs a configured, verified vision provider. Text uploads remain available.')
        try:
            text = vision(data, 'image/png' if suffix == '.png' else 'image/jpeg')
        except Exception as exc:
            raise SourceError('vision_unavailable', 'The configured vision provider could not read this photo.') from exc
        if not text or not text.strip():
            raise SourceError('unreadable_photo', 'Retake this photo with clear lighting and readable text.')
        sections.append(ExtractedSection(Path(filename).stem, text.strip(), 'photo', {'filename': filename, 'section': 1, 'reading_method': 'vision'}))
    if not sections:
        raise SourceError('empty_source', 'No readable study content was found.')
    if len(sections) > 10000:
        raise SourceError('section_limit', 'This source has too many sections.')
    return SourceSnapshot(sections)
