import io, json, tempfile, unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app import Service, MAX_UPLOAD
from reportlab.pdfgen import canvas

class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.now=1000
        self.key='test-only-'+'a'*40
        self.app=Service(Path(self.temp.name)/'test.sqlite3',self.key,'10772638166','https://study.example',clock=lambda:self.now)
    def tearDown(self): self.temp.cleanup()
    def call(self,path,data=None,raw=None,auth=True,origin=True,method='POST',user='123'):
        if raw is None: raw=json.dumps(dict(data or {},userId=user)).encode()
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/pdf' if path=='/api/uploads' else 'application/json','wsgi.input':io.BytesIO(raw),'REMOTE_ADDR':'127.0.0.1'}
        if origin: env['HTTP_ORIGIN']='https://study.example'
        if auth: env.update(HTTP_X_STUDYMATE_KEY=self.key,HTTP_X_UNIVERSE_ID='10772638166')
        result={}
        def start(status,headers): result['status']=int(status.split()[0]);result['headers']=dict(headers)
        body=b''.join(self.app(env,start))
        result['body']=json.loads(body) if result['headers']['Content-Type'].startswith('application/json') else body
        return result
    def pdf(self,text='Photosynthesis converts light into chemical energy.'):
        output=io.BytesIO(); c=canvas.Canvas(output);c.drawString(50,750,text);c.save();return output.getvalue()
    def upload(self):
        result=self.call('/api/uploads',raw=self.pdf());self.assertEqual(result['status'],200,result)
        return result['body']['code']
    def claim(self,code,user='123',course='bio'):
        return self.call('/v1/game/import',{'code':code,'courseId':course,'lecture':'Lecture 1','category':'lecture'},user=user)
    def test_full_upload_import_read_delete(self):
        code=self.upload(); claim=self.claim(code);self.assertEqual(claim['status'],200)
        doc=claim['body']['documentId']
        library=self.call('/v1/game/library')['body']['documents'];self.assertEqual(len(library),1)
        read=self.call('/v1/game/read',{'documentId':doc,'page':1});self.assertIn('Photosynthesis',read['body']['text'])
        self.assertEqual(self.claim(code)['status'],404)
        self.call('/v1/game/delete',{'documentId':doc});self.assertEqual(self.call('/v1/game/read',{'documentId':doc})['status'],404)
    def test_owner_isolation(self):
        doc=self.claim(self.upload())['body']['documentId']
        self.assertEqual(self.call('/v1/game/library',user='456')['body']['documents'],[])
        self.assertEqual(self.call('/v1/game/read',{'documentId':doc},user='456')['status'],404)
        self.call('/v1/game/delete',{'documentId':doc},user='456')
        self.assertEqual(self.call('/v1/game/read',{'documentId':doc})['status'],200)
    def test_expired_code(self):
        code=self.upload();self.now+=901
        self.assertEqual(self.claim(code)['status'],404)
        with self.app.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM pending').fetchone()[0],0)
    def test_racing_claim_only_one_wins(self):
        code=self.upload()
        with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda user:self.claim(code,user=user),['123','456']))
        self.assertEqual(sorted(r['status'] for r in results),[200,404])
    def test_auth_required(self):
        self.assertEqual(self.call('/v1/game/library',auth=False)['status'],401)
    def test_wrong_origin(self):
        self.assertEqual(self.call('/api/uploads',raw=self.pdf(),origin=False)['status'],403)
    def test_invalid_and_oversize_files(self):
        self.assertEqual(self.call('/api/uploads',raw=b'not a PDF')['status'],422)
        self.assertEqual(self.call('/api/uploads',raw=b'%PDF-'+b'x'*MAX_UPLOAD)['status'],413)
        self.assertEqual(self.call('/api/uploads',raw=b'%PDF-1.4 broken')['status'],422)
    def test_encrypted_and_empty_files(self):
        from pypdf import PdfReader,PdfWriter
        writer=PdfWriter();writer.append(PdfReader(io.BytesIO(self.pdf())));writer.encrypt('secret');out=io.BytesIO();writer.write(out)
        self.assertEqual(self.call('/api/uploads',raw=out.getvalue())['status'],422)
        self.assertEqual(self.call('/api/uploads',raw=self.pdf(''))['status'],422)
    def test_parser_timeout(self):
        from unittest.mock import patch
        import subprocess
        with patch('app.subprocess.run',side_effect=subprocess.TimeoutExpired('parser',20)):
            self.assertEqual(self.call('/api/uploads',raw=self.pdf())['status'],422)
    def test_bad_page_and_course_delete(self):
        doc=self.claim(self.upload())['body']['documentId']
        self.assertEqual(self.call('/v1/game/read',{'documentId':doc,'page':0})['status'],400)
        self.call('/v1/game/delete-course',{'courseId':'bio'})
        self.assertEqual(self.call('/v1/game/library')['body']['documents'],[])
    def test_restart_preserves_documents(self):
        self.claim(self.upload())
        self.app=Service(self.app.db_path,self.key,'10772638166','https://study.example')
        self.assertEqual(len(self.call('/v1/game/library')['body']['documents']),1)
    def test_rate_limit_and_headers(self):
        for _ in range(10): self.call('/api/uploads',raw=b'bad')
        result=self.call('/api/uploads',raw=b'bad')
        self.assertEqual(result['status'],429)
        self.assertEqual(result['headers']['Cache-Control'],'no-store')
        self.assertIn("frame-ancestors 'none'",result['headers']['Content-Security-Policy'])
    def test_concurrent_parser_rejected_and_recovers(self):
        self.app.parser_slot.acquire()
        try:
            self.assertEqual(self.call('/api/uploads',raw=self.pdf())['status'],503)
        finally:
            self.app.parser_slot.release()
        self.assertEqual(self.call('/api/uploads',raw=self.pdf())['status'],200)
    def test_render_origin_default(self):
        from unittest.mock import patch
        from app import create_app
        with patch.dict('os.environ',{'RENDER_EXTERNAL_URL':'https://example.onrender.com','DATABASE_PATH':self.app.db_path,'STUDYMATE_KEY':self.key,'ROBLOX_UNIVERSE_ID':'10772638166'},clear=True):
            self.assertEqual(create_app().origin,'https://example.onrender.com')

if __name__=='__main__':unittest.main(verbosity=2)
