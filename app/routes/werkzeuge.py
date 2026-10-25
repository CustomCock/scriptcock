"""Intranet-Spiegel für „Admin-Werkzeug bereitstellen“: ``GET /werkzeuge/<id>/<datei>``.

Ausgeliefert werden nur die Original-Dateien aus ``registry/admx-quellen.yaml`` (siehe ``app/werkzeuge.py``),
ohne Anmeldung – die Scripte laufen auf Windows-Rechnern ohne Sitzung, und die Dateien sind ohnehin
öffentliche Hersteller-Downloads. Das Script prüft den SHA-256 selbst.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response

from app import werkzeuge

router = APIRouter()


@router.get("/werkzeuge/{pfad:path}", include_in_schema=False)
async def werkzeug_datei(pfad: str) -> Response:
    datei = werkzeuge.gespiegelt(pfad)
    if datei is None:
        return JSONResponse(
            {"fehler": "Nicht gefunden – Datei mit tools/admx_holen.py ablegen."}, status_code=404
        )
    return FileResponse(datei, media_type="application/octet-stream", filename=datei.name)
