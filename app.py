"""StudyMate private PDF text library. Run behind HTTPS with one persistent disk."""
import hashlib, hmac, json, os, re, secrets, sqlite3, subprocess, sys, time, threading
from pathlib import Path
from urllib.parse import urlsplit
from contextlib import contextmanager

ROOT = Path(__file__).parent
MAX_UPLOAD = 5 * 1024 * 1024
TTL = 900

class Problem(Exception):
    def __init__(self, status, message): self.status, self.message = status, message

def digest(code): return hashlib.sha256(code.encode()).hexdigest()
def need(value, limit=100):
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > limit:
        raise Problem(400, 'Check the required fields and length limits.')
    return value.strip()

class Service:
    def __init__(self, db_path, key, universe, origin, clock=time.time):
        if len(key) < 32: raise ValueError('STUDYMATE_KEY must contain at least 32 characters.')
        self.db_path, self.key, self.universe, self.origin, self.clock = str(db_path), key, str(universe), origin.rstrip('/'), clock
        self.parser_slot = threading.BoundedSemaphore(1)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS pending (hash TEXT PRIMARY KEY, text TEXT NOT NULL, pages INTEGER NOT NULL, expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, user TEXT NOT NULL, course TEXT NOT NULL, lecture TEXT NOT NULL, unit TEXT NOT NULL, chapter TEXT NOT NULL, category TEXT NOT NULL, text TEXT NOT NULL, pages INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS owner ON documents(user,course);
            CREATE TABLE IF NOT EXISTS limits (bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
            ''')
    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def rate(self, bucket, limit, period):
        now = int(self.clock())
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM limits WHERE expires<=?', (now,))
            db.execute('INSERT OR IGNORE INTO limits VALUES (?,0,?)', (bucket, now+period))
            row = db.execute('SELECT count FROM limits WHERE bucket=?', (bucket,)).fetchone()
            if row['count'] >= limit: raise Problem(429, 'Too many requests. Please try again later.')
            db.execute('UPDATE limits SET count=count+1 WHERE bucket=?', (bucket,))
    def parse_pdf(self, raw):
        if not self.parser_slot.acquire(blocking=False):
            raise Problem(503, 'Another PDF is processing. Try again in a moment.')
        try:
            return self._parse_pdf(raw)
        finally:
            self.parser_slot.release()
    def _parse_pdf(self, raw):
        try:
            result = subprocess.run([sys.executable, str(ROOT/'extract_pdf.py')], input=raw, capture_output=True, timeout=20)
            parsed = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, ValueError):
            raise Problem(422, 'This PDF took too long or could not be read. Try a smaller file.')
        if result.returncode or 'error' in parsed:
            raise Problem(422, parsed.get('error', 'The PDF could not be read.'))
        return parsed
    def game(self, action, data):
        user = need(data.get('userId'), 24)
        if not re.fullmatch(r'[1-9][0-9]*', user): raise Problem(400, 'Invalid player.')
        self.rate('player:'+user, 120, 60)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if action == 'import':
                course = need(data.get('courseId'), 80)
                code = need(data.get('code'), 40).upper().replace('-', '').replace(' ', '')
                if not re.fullmatch('[A-F0-9]{32}', code): raise Problem(400, 'Check your import code.')
                row = db.execute('SELECT * FROM pending WHERE hash=? AND expires>?', (digest(code), self.clock())).fetchone()
                if not row: raise Problem(404, 'Import code expired or already used. Upload the PDF again.')
                count, size = db.execute('SELECT count(*),coalesce(sum(length(CAST(text AS BLOB))),0) FROM documents WHERE user=?', (user,)).fetchone()
                if count >= 60 or size+len(row['text'].encode()) > 2_000_000:
                    raise Problem(409, 'PDF library full. Delete a PDF before importing another.')
                category = data.get('category')
                if category not in ('lecture','exam'): raise Problem(400, 'Choose lecture or practice exam.')
                document_id = 'pdf-'+secrets.token_hex(16)
                db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)', (document_id,user,course,need(data.get('lecture'),100),need(data.get('unit'),80) if data.get('unit') else '',need(data.get('chapter'),80) if data.get('chapter') else '',category,row['text'],row['pages']))
                db.execute('DELETE FROM pending WHERE hash=?', (digest(code),))
                return {'documentId':document_id}
            if action == 'library':
                rows = db.execute('SELECT * FROM documents WHERE user=? ORDER BY rowid DESC', (user,)).fetchall()
                return {'documents':[{'id':r['id'],'courseId':r['course'],'lecture':r['lecture'],'unit':r['unit'],'chapter':r['chapter'],'category':r['category'],'kind':'pdf','status':'ready','pages':r['pages']} for r in rows]}
            if action == 'read':
                row = db.execute('SELECT * FROM documents WHERE user=? AND id=?', (user,need(data.get('documentId'),80))).fetchone()
                if not row: raise Problem(404, 'PDF not found.')
                page = data.get('page',1)
                chunks = [row['text'][i:i+1500] for i in range(0,len(row['text']),1500)]
                if type(page) is not int or not 1<=page<=len(chunks): raise Problem(400,'Invalid text section.')
                return {'text':chunks[page-1],'page':page,'pageCount':len(chunks),'lecture':row['lecture']}
            if action == 'delete':
                db.execute('DELETE FROM documents WHERE user=? AND id=?',(user,need(data.get('documentId'),80)))
                return {'ok':True}
            if action == 'delete-course':
                db.execute('DELETE FROM documents WHERE user=? AND course=?',(user,need(data.get('courseId'),80)))
                return {'ok':True}
        raise Problem(404,'Unknown action.')
    def __call__(self, env, start):
        status, mime = 200, 'application/json; charset=utf-8'
        try:
            path, method = env.get('PATH_INFO','/'), env.get('REQUEST_METHOD','GET')
            with self.db() as db:
                db.execute('DELETE FROM pending WHERE expires<=?', (self.clock(),))
            if method == 'GET' and path in ('/','/style.css','/upload.js'):
                file = {'/':'index.html','/style.css':'style.css','/upload.js':'upload.js'}[path]
                mime = {'/':'text/html; charset=utf-8','/style.css':'text/css','/upload.js':'text/javascript'}[path]
                body = (ROOT/file).read_bytes()
            elif method == 'GET' and path == '/health': body = b'{"ok":true}'
            elif method == 'POST' and path == '/api/uploads':
                if env.get('HTTP_ORIGIN') != self.origin: raise Problem(403,'Open the upload page to upload a PDF.')
                self.rate('upload:'+env.get('REMOTE_ADDR','unknown'), 10, 900)
                self.rate('all-uploads', 200, 3600)
                length = int(env.get('CONTENT_LENGTH') or 0)
                if not 0 < length <= MAX_UPLOAD: raise Problem(413,'Choose a PDF up to 5 MB.')
                if env.get('CONTENT_TYPE','').split(';')[0] != 'application/pdf': raise Problem(415,'Choose a PDF file.')
                raw = env['wsgi.input'].read(length)
                if len(raw)!=length or not raw.startswith(b'%PDF-'): raise Problem(422,'Choose a valid PDF file.')
                parsed = self.parse_pdf(raw)
                code = secrets.token_hex(16).upper()
                with self.db() as db:
                    count = db.execute('SELECT count(*) FROM pending').fetchone()[0]
                    if count>=500: raise Problem(503,'Uploads are busy. Try again shortly.')
                    db.execute('INSERT INTO pending VALUES (?,?,?,?)',(digest(code),parsed['text'],parsed['pages'],int(self.clock())+TTL))
                body = json.dumps({'code':'-'.join(code[i:i+8] for i in range(0,32,8)),'expiresIn':TTL,'pages':parsed['pages']}).encode()
            elif method == 'POST' and path.startswith('/v1/game/'):
                if not hmac.compare_digest(env.get('HTTP_X_STUDYMATE_KEY',''),self.key) or env.get('HTTP_X_UNIVERSE_ID')!=self.universe:
                    raise Problem(401,'Unauthorized.')
                length = int(env.get('CONTENT_LENGTH') or 0)
                if not 0<length<=30000: raise Problem(413,'Request too large.')
                data = json.loads(env['wsgi.input'].read(length))
                if not isinstance(data,dict): raise Problem(400,'Invalid request.')
                body = json.dumps(self.game(path.rsplit('/',1)[-1],data)).encode()
            else: raise Problem(404,'Not found.')
        except Problem as exc:
            status, body = exc.status, json.dumps({'error':exc.message}).encode()
        except (ValueError,UnicodeError):
            status, body = 400, b'{"error":"Invalid request."}'
        except Exception:
            status, body = 503, b'{"error":"Service temporarily unavailable. Please try again."}'
        from http import HTTPStatus
        start(f'{status} {HTTPStatus(status).phrase}', [('Content-Type',mime),('Content-Length',str(len(body))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('Content-Security-Policy',"default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")])
        return [body]

def create_app():
    origin = (os.environ.get('PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL') or '').rstrip('/')
    if urlsplit(origin).scheme != 'https' and not origin.startswith('http://127.0.0.1:'):
        raise ValueError('PUBLIC_ORIGIN must use HTTPS.')
    return Service(os.environ.get('DATABASE_PATH','data/materials.sqlite3'),os.environ['STUDYMATE_KEY'],os.environ['ROBLOX_UNIVERSE_ID'],origin)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    print('Local preview at http://127.0.0.1:8787',flush=True)
    make_server('127.0.0.1',8787,create_app()).serve_forever()
