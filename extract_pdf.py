"""Run in a disposable subprocess; never retain the original PDF."""
import io, json, sys

def extract(raw):
    if not raw.startswith(b'%PDF-'):
        raise ValueError('Choose a valid PDF file.')
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        raise ValueError('Remove the PDF password before uploading.')
    if len(reader.pages) > 100:
        raise ValueError('Split this PDF into files of at most 100 pages.')
    pages, size = [], 0
    for page in reader.pages:
        text = page.extract_text() or ''
        size += len(text)
        if size > 120000:
            raise ValueError('Split this PDF into smaller files (120,000 characters maximum).')
        pages.append(text)
    text = '\n\n'.join(pages).strip()
    if len(text.encode('utf-8')) > 120000 or len(json.dumps({'text':text},ensure_ascii=False).encode('utf-8')) > 170000:
        raise ValueError('Split this PDF into smaller files (120 KB of extracted text maximum).')
    if not text:
        raise ValueError('No selectable text found. Scanned PDFs need OCR before upload.')
    return {'text': text, 'pages': len(pages)}

if __name__ == '__main__':
    try:
        if sys.platform != 'win32':
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (256*1024*1024, 256*1024*1024))
            resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        print(json.dumps(extract(sys.stdin.buffer.read(5*1024*1024+1))))
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'This PDF could not be read. Try exporting it again.'
        print(json.dumps({'error': message}))
        sys.exit(1)
