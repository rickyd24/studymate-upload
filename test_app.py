import io,json,tempfile,unittest,subprocess,uuid
from pathlib import Path
from unittest.mock import patch
from reportlab.pdfgen import canvas
from app import Service,MAX_UPLOAD,create_app

class Tests(unittest.TestCase):
    def setUp(self):
        self.testdir=Path(__file__).parent/('test-'+uuid.uuid4().hex);self.testdir.mkdir();self.now=1000
        self.app=Service(self.testdir/'pending.sqlite3','https://study.example',clock=lambda:self.now)
    def tearDown(self):
        assert self.testdir.parent.resolve()==Path(__file__).parent.resolve()
        for f in self.testdir.iterdir(): f.unlink()
        self.testdir.rmdir()
    def call(self,path,data=None,raw=None,origin=True):
        raw=raw if raw is not None else json.dumps(data or {}).encode()
        env={'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/pdf' if path=='/api/uploads' else 'application/json','wsgi.input':io.BytesIO(raw),'REMOTE_ADDR':'test'}
        if origin:env['HTTP_ORIGIN']='https://study.example'
        out={}
        def start(status,headers):out.update(status=int(status.split()[0]),headers=dict(headers))
        out['body']=json.loads(b''.join(self.app(env,start)));return out
    def pdf(self,text='Photosynthesis converts light into chemical energy.'):
        out=io.BytesIO();c=canvas.Canvas(out);c.drawString(50,750,text);c.save();return out.getvalue()
    def upload(self):
        r=self.call('/api/uploads',raw=self.pdf());self.assertEqual(r['status'],200,r);return r['body']['code']
    def test_upload_import_retry(self):
        code=self.upload()
        a=self.call('/v1/game/import',{'code':code});b=self.call('/v1/game/import',{'code':code})
        self.assertEqual(a['status'],200);self.assertEqual(a['body'],b['body']);self.assertIn('Photosynthesis',a['body']['text'])
    def test_wrong_code(self):
        self.upload();self.assertEqual(self.call('/v1/game/import',{'code':'A'*32})['status'],404)
    def test_expiry(self):
        code=self.upload();self.now+=901
        self.assertEqual(self.call('/v1/game/import',{'code':code})['status'],404)
    def test_no_library_endpoints(self):
        for action in ['library','read','delete','delete-course']:self.assertEqual(self.call('/v1/game/'+action)['status'],404)
        with self.app.db() as db:self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='documents'").fetchone())
    def test_bad_origin(self):self.assertEqual(self.call('/api/uploads',raw=self.pdf(),origin=False)['status'],403)
    def test_bad_files(self):
        for raw in [b'bad',b'%PDF-1.4 broken',self.pdf('')]:self.assertEqual(self.call('/api/uploads',raw=raw)['status'],422)
        self.assertEqual(self.call('/api/uploads',raw=b'x'*(MAX_UPLOAD+1))['status'],413)
    def test_encrypted(self):
        from pypdf import PdfWriter,PdfReader
        w=PdfWriter();w.append(PdfReader(io.BytesIO(self.pdf())));w.encrypt('secret');out=io.BytesIO();w.write(out)
        self.assertEqual(self.call('/api/uploads',raw=out.getvalue())['status'],422)
    def test_timeout(self):
        with patch('app.subprocess.run',side_effect=subprocess.TimeoutExpired('parser',20)):self.assertEqual(self.call('/api/uploads',raw=self.pdf())['status'],422)
    def test_concurrency(self):
        self.app.parser_slot.acquire()
        try:self.assertEqual(self.call('/api/uploads',raw=self.pdf())['status'],503)
        finally:self.app.parser_slot.release()
        self.upload()
    def test_lost_upload(self):
        code=self.upload();self.app=Service(self.testdir/'new.sqlite3','https://study.example')
        r=self.call('/v1/game/import',{'code':code});self.assertEqual(r['status'],404);self.assertIn('restarted',r['body']['error'])
    def test_rate(self):
        for _ in range(10):self.call('/api/uploads',raw=b'bad')
        r=self.call('/api/uploads',raw=b'bad');self.assertEqual(r['status'],429);self.assertEqual(r['headers']['Cache-Control'],'no-store')
    def test_no_secret_required(self):
        with patch.dict('os.environ',{'RENDER_EXTERNAL_URL':'https://example.onrender.com','DATABASE_PATH':self.app.db_path},clear=True):self.assertEqual(create_app().origin,'https://example.onrender.com')
if __name__=='__main__':unittest.main(verbosity=2)

