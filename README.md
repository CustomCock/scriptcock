# okm Script-Baukasten

Webanwendung fürs okm-Intranet: Mitarbeiter **ohne Script- oder KI-Kenntnisse** stellen sich
aus geprüften Bausteinen ein Script für ihre aktuelle Aufgabe zusammen und laden es herunter –
für **Windows PowerShell 5.1**, **Windows CMD**, **Linux (Bash)** und **macOS (zsh)**.

Die Anwendung **erzeugt** Scripte, sie führt sie **nicht** selbst aus.

> 📷 *Screenshot Startseite (Betriebssystem wählen)* – folgt
>
> 📷 *Screenshot Rezept-Formular mit Live-Validierung* – folgt
>
> 📷 *Screenshot Vorschau mit Download und SHA-256* – folgt
>
> 📷 *Screenshot freier Baukasten mit Drag & Drop* – folgt
>
> 📷 *Screenshot Blockly-Modus mit „Versuche“ und „Wiederhole“* – folgt

## Funktionen

- **Rezept-Modus:** Betriebssystem wählen → Rezept suchen → Formular ausfüllen (Live-Prüfung,
  Hilfetexte, Beispielwerte) → Vorschau mit Syntax-Highlighting → Download / Zwischenablage,
  dazu eine Anleitung „So führst du das Script aus“.
- **Freier Baukasten:** Bausteine per Drag & Drop (oder „+“) zu einer Schrittliste zusammenstellen,
  umsortieren, Werte ausfüllen; Live-Vorschau, Zielsystem jederzeit umschaltbar (nicht verfügbare
  Bausteine werden markiert, der Download gesperrt). Admins können die Liste als Rezept speichern.
- **Blockly-Modus:** Bausteine grafisch zusammenstecken, inklusive Ablauf-Bausteinen
  „Versuche … wenn das fehlschlägt …“ und „Wiederhole N-mal“. Blockly erzeugt dabei nur eine
  Schrittliste – Prüfung und Script-Erzeugung macht immer der Server.
- **Bibliothek:** Scripte mit Titel, Beschreibung und Tags speichern, suchen, filtern,
  „Hat funktioniert ✓“ markieren und **erneut öffnen und anpassen** (aus der gespeicherten
  Zwischenrepräsentation – mit Hinweis, wenn sich Bausteine seitdem geändert haben).
- **Verwaltung für Admins:** Rezept-Vorschläge von Nutzern freigeben oder ablehnen.
- **24 Bausteine**, z. B. Systeminfo, Ping, Traceroute, Port prüfen, Netzlaufwerk, Drucker per IP,
  Dienste, Prozesse, Windows-Update-Reset, SetupDiag, Diagnosepaket, Software installieren.
- **8 Rezepte**, z. B. „Drucker einrichten“, „Netzwerkproblem diagnostizieren“,
  „Diagnosepaket für den Support“, „Windows Update reparieren“.
- Jedes Script hat Kopfkommentar, Fehlerbehandlung, Protokolldatei, Fortschrittsanzeige,
  Admin-Prüfung, Abschlusszusammenfassung; rote (destruktive) Schritte fragen nach „JA“.
- Modus **„Nur simulieren“** (Dry-Run).
- SHA-256 jedes Scripts wird gespeichert und angezeigt.
- Login über **Keycloak (OIDC)**, Rollen `nutzer` und `admin`.
- Neue Bausteine **nur per YAML** – siehe [docs/neuen-block-anlegen.md](docs/neuen-block-anlegen.md).

Sicherheitskonzept: [docs/sicherheit.md](docs/sicherheit.md).

## Installation

Voraussetzung: Python 3.11+, Debian 12 (oder Docker).

### Betrieb mit systemd + nginx (Debian-VM)

```bash
sudo apt install python3-venv nginx git
sudo useradd --system --home /opt/script-baukasten --shell /usr/sbin/nologin baukasten
sudo git clone <repo-url> /opt/script-baukasten
cd /opt/script-baukasten
sudo python3 -m venv .venv
sudo .venv/bin/pip install .
sudo cp .env.example .env && sudo nano .env        # Werte eintragen (siehe Konfiguration)
sudo mkdir -p data && sudo chown -R baukasten:baukasten data
sudo chown root:baukasten .env && sudo chmod 640 .env

sudo cp deploy/script-baukasten.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now script-baukasten
systemctl status script-baukasten        # bei Fehlern: journalctl -u script-baukasten

sudo cp deploy/nginx-script-baukasten.conf /etc/nginx/sites-available/script-baukasten
sudo ln -s /etc/nginx/sites-available/script-baukasten /etc/nginx/sites-enabled/
sudo nano /etc/nginx/sites-available/script-baukasten   # server_name + Zertifikate
sudo nginx -t && sudo systemctl reload nginx
```

Update: `git pull && .venv/bin/pip install . && systemctl restart script-baukasten`.

Ist eine Block- oder Rezept-Datei fehlerhaft, startet die Anwendung **nicht** und nennt Datei
und Problem im Journal.

### Betrieb mit Docker

```bash
cp .env.example .env && nano .env
docker compose up -d --build
```

Der Container lauscht auf `127.0.0.1:8000`; davor gehört nginx mit TLS (Konfiguration wie oben).
Die SQLite-Datenbank liegt im Volume `baukasten-daten`.

### Keycloak einrichten

1. Im Realm einen Client `script-baukasten` anlegen: *Client authentication* an,
   *Standard flow* an, Redirect-URI `https://baukasten.okm.local/auth/callback`,
   *Valid post logout redirect URIs* `https://baukasten.okm.local/`.
2. Client-Secret nach `OIDC_CLIENT_SECRET` übernehmen.
3. Gruppen `script-baukasten` und `script-baukasten-admin` anlegen und Benutzer zuordnen.
4. Am Client (bzw. einem Client-Scope) einen Mapper *Group Membership* mit
   Token-Claim-Name `groups` anlegen (ID-Token und Userinfo aktiv).

## Konfiguration

Alle Einstellungen per Umgebungsvariable bzw. `.env` (Vorlage: [.env.example](.env.example)):

| Variable | Bedeutung |
|---|---|
| `APP_SECRET_KEY` | geheimer Schlüssel für Session-Cookies (Pflicht) |
| `DATABASE_URL` | SQLite-Datei, Standard `sqlite:///./data/baukasten.db` |
| `ROOT_PATH` | Pfad-Präfix, wenn unter einem Unterpfad betrieben |
| `SESSION_COOKIE_SECURE` | Cookies nur über HTTPS (Standard `true`) |
| `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | Keycloak-Anbindung |
| `OIDC_ERLAUBTE_GRUPPE` | nur diese Gruppe darf rein (leer = alle angemeldeten) |
| `OIDC_ADMIN_GRUPPE` | Admin-Rolle |
| `OIDC_GRUPPEN_CLAIM` | Name des Gruppen-Claims (Standard `groups`) |
| `AUTH_DISABLED` | **nur Entwicklung:** Anmeldung aus, rotes Warnbanner |

## Entwicklung

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
AUTH_DISABLED=true uvicorn app.main:app --reload
pytest -q -rs
ruff check . && ruff format --check . && mypy app
```

Optional für den Browser-Test des Baukastens: `pip install playwright && playwright install chromium`.

Für die vollständigen Syntax-Checks lokal `zsh`, `shellcheck` und `pwsh` (mit Modul
`PSScriptAnalyzer`) installieren; sonst werden diese Tests mit Hinweis übersprungen.
Golden-Files nach gewollten Änderungen neu erzeugen: `UPDATE_GOLDEN=1 pytest tests/test_golden.py`.

Weitere Doku: [CLAUDE.md](CLAUDE.md) (Architektur & Konventionen),
[docs/test-vms.md](docs/test-vms.md) (manuelle Prüfung auf Proxmox),
[docs/offene-punkte.md](docs/offene-punkte.md).
