# StudyMate PDF uploads

Prepared for **Studymate Classroom [STUDY ON ROBLOX]**, place 106502643487150, universe 10772638166.

## Current status

The Studio scripts have been updated and their originals backed up in `ServerStorage.StudyMatePDF_Backup_20261024`. The upload service is implemented and locally tested. It is **not publicly deployed or connected to Roblox yet**. The game has not been published by this task. Save the Studio place to preserve the edits.

## Player flow

1. Upload a PDF on this companion website.
2. Copy its private, one-use code (valid for 15 minutes).
3. Open Study Materials in the game and select or create a course.
4. Open Lecture PDFs or Practice Exams, enter a title and the code, then select Import PDF.
5. Read extracted text in sections, or delete the document from the personal library.

PDFs are limited to 5 MB, 100 pages, and 120,000 extracted characters. The service does not save original PDFs. Scans, handwriting, images, PDF layout and OCR are not supported. Imported text is not automatically fed into the tutor or NPC lesson system. Each player's library supports 60 PDFs and 2 MB of extracted text.

## Hosting setup

The included `render.yaml` configures a Render Python web service on the smallest paid compute plan, with a 1 GB persistent disk at `/var/data`. It generates the shared secret securely on Render. The website origin is taken from Render's `RENDER_EXTERNAL_URL`; no URL placeholder needs editing. This configuration has a base cost of $7.25/month at the pricing checked on October 24, 2026, before taxes and usage overages. Applying the Blueprint creates paid resources; review the price first.

Use one service instance; this SQLite design is not for independent replicas. One PDF is processed at a time, with a 256 MB parser memory limit, to fit the 512 MB compute plan. Other concurrent uploads receive a retry message. For hosts other than Render, the Dockerfile uses `/data`, writable by uid 10001, and port 8080. Configure the host's request-body limit at 5 MB and a request timeout of at least 45 seconds.

Required private environment variables:

| Variable | Value |
| --- | --- |
| `PUBLIC_ORIGIN` | Optional on Render; elsewhere, the final HTTPS website origin with no trailing slash |
| `ROBLOX_UNIVERSE_ID` | `10772638166` |
| `STUDYMATE_KEY` | A newly generated random secret, at least 32 characters |
| `DATABASE_PATH` | `/var/data/materials.sqlite3` on Render; `/data/materials.sqlite3` in Docker |

Generate the secret in your host's secure settings or with `python -c "import secrets; print(secrets.token_hex(32))"`. Keep it out of source control, browser code and chat. Put the **same value** in the Roblox experience secret store under `studymate_materials_key`, restricted to the service's domain.

Health check: `GET /health`. The Render start command uses its assigned port; Docker uses port 8080. HTTPS must terminate at the hosting platform. A persistent disk is essential: an ephemeral filesystem would lose player libraries on restart or deployment. Backups of the database contain private text; protect access and set an appropriate retention policy. Create consistent SQLite backups with its backup API rather than relying solely on whole-disk snapshots.

The per-address upload limit uses the direct connection address and does not trust forwarded headers. A reverse proxy may cause multiple users to share this limit; configure an edge upload rate limit and trusted-proxy address handling before a broad release. The global limit is 200 uploads per hour. This is an initial small-service limit, not a high-scale deployment.

## Connect Roblox after hosting

1. In the experience security settings, enable HTTP requests.
2. Configure the experience secret `studymate_materials_key` as described above.
3. In `ServerScriptService.AIU.MaterialsConfig`, set `BackendURL` to the HTTPS origin. Keep the secret value out of this module.
4. Leave `AllowStudioBackend = false` for ordinary playtests: Studio courses are temporary and should not mix with live libraries.
5. Validate with a separate staging service if you need Studio HTTP tests. Use Studio's local secret configuration for that staging key, and temporarily enable `AllowStudioBackend` only for the staging test.
6. Test a PDF import in the connected environment, confirm another player cannot read it, and publish the Studio changes when ready.

The game UI contains no website links or QR codes. Roblox restricts off-platform directions; distributing or promoting the website needs a permitted route under Roblox's current rules. Do not add an in-game external website link as a shortcut.

## Data and access

The game server authenticates using its shared secret and universe ID. Player IDs come from Roblox's server-side Player object; the browser cannot select a player ID. A code is a 128-bit random bearer credential: whoever redeems it first receives that document. Only code hashes are stored. Do not share import codes. Redemption is atomic and transfers text into the authenticated player's library. Unclaimed codes expire after 15 minutes, and expired records are purged on the next request. Imported text remains until its owner deletes the PDF or course. There is no public document-download route.

All text shown inside Roblox passes through the game's TextService filter for that player. Parsing runs in a subprocess with a 20-second wall-clock timeout and Linux CPU/memory limits. File sizes and user-library sizes are checked server-side. Browser responses are uncached, and the site loads no third-party scripts.

## Tests and local preview

Install `requirements-dev.txt`, then run `python -m unittest -v test_app`. Tests cover successful upload/import/read/delete, isolation, one-use and expiring codes, concurrent redemption, restart persistence, invalid files, encrypted and textless PDFs, parser timeout, authentication, origin checks, rate limits, parser concurrency limits and Render origin configuration.

For a local-only preview, set the environment variables with `PUBLIC_ORIGIN=http://127.0.0.1:8787` and a temporary database path, then run `python app.py`. This development server binds only to localhost. It is not a production server. Unit tests use generated sample PDFs and temporary databases.

## Included Studio source copies

- `MaterialsService.lua` → `ServerScriptService.AIU.MaterialsService`
- `StudyMaterialsUI.lua` → `StarterPlayer.StarterPlayerScripts.AIUClient.StudyMaterialsUI`

Original scripts remain backed up in Studio. The upload service is separate from the game's existing paste-notes storage, course system and lesson behavior.
