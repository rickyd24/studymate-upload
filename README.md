# StudyMate PDF uploads — free hosting

The website converts PDFs; **Roblox DataStore stores imported text**. No paid server, persistent disk, external database or shared connection secret is required.

Upload a PDF, copy its private code, then import it in Study Materials under your selected course's Lecture PDFs or Practice Exams tab. Saved text can be read or deleted even while the website is asleep.

Keep codes private: anyone with a code can retrieve the uploaded text until it expires. Codes expire after 15 minutes or a service restart. Upload again if needed. Retries are supported; Roblox avoids duplicate imports. Original PDFs are not saved. Temporary extracted text is purged after expiry on the next request. The website accepts no player IDs and exposes no saved-library endpoints.

Limits: 5 MB, 100 pages, and 120 KB extracted UTF-8 text per PDF. Text only: no layout, images, OCR or tutor integration. The Roblox library allows 60 documents within a shared 3 MB JSON budget. Text is filtered for its owner before display. Studio saves are session-only; published servers use DataStore.

## Render
Use the included render.yaml: **Free** compute, no disk or paid database. DATABASE_PATH points to /tmp/studymate-pending.sqlite3. The website origin comes from Render's RENDER_EXTERNAL_URL. No secret is needed. Health check: /health.
Free services sleep after inactivity and may take about a minute to wake. Unused codes may disappear on restart; PDFs already saved in Roblox are unaffected. Monthly free limits apply. Do not enable paid upgrades or paid overages without approval. This is a hobby/test deployment.

## Roblox
Set ServerScriptService.AIU.MaterialsConfig.BackendURL to the deployed HTTPS origin and enable HTTP requests. Set MaxPdfBytes=120000 and MaxLibraryBytes=3000000. SecretName is unused. AllowStudioBackend can be enabled for testing the converter, but Studio saves remain temporary. Save and publish the place when ready.
The game contains no website links or QR codes. Website discovery must follow Roblox's off-platform rules.

## Tests
Install requirements-dev.txt and run python -m unittest -v test_app.
Tests cover imports, retries, expired codes, invalid/encrypted/textless PDFs, timeouts, rate limits and concurrency.
Only one parser runs at once, with a 20-second timeout and a 256 MB Linux memory limit. The direct-address upload rate limit may be shared behind Render's proxy; retry if busy.

For local preview, set PUBLIC_ORIGIN=http://127.0.0.1:8787 and a temporary DATABASE_PATH, then run python app.py.

