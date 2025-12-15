# Railroad Tycoon Streaming - Documentation Projet

## Serveur de production

```
Host: 69.62.108.82
User: automation
Path: /opt/railroad-tycoon-streaming/
Port: 8082
```

### Connexion SSH
```bash
ssh automation@69.62.108.82
cd /opt/railroad-tycoon-streaming
```

### Deploiement rapide
```bash
# Upload depuis Windows (PowerShell)
scp -r * automation@69.62.108.82:/opt/railroad-tycoon-streaming/

# Sur le serveur
ssh automation@69.62.108.82 "cd /opt/railroad-tycoon-streaming && docker-compose build --no-cache && docker-compose up -d"
```

### URL
- **Railroad Tycoon** : http://69.62.108.82:8082/

---

## Vue d'ensemble

Streaming de **Railroad Tycoon** (DOS via DOSBox-X) vers un **iPad 1 avec Safari 5.1.1**.

Le serveur tourne dans un container Docker sur un VPS Linux et diffuse le jeu via JPEG polling HTTP.

## Architecture

```
+-------------------------------------------------------------+
|                    Container Docker                          |
|  +----------------------------------------------------------+
|  | Xvfb :99 (640x480x24)                                    |
|  |   +-- Openbox (window manager)                           |
|  |         +-- DOSBox-X                                     |
|  |               +-- Railroad Tycoon (DOS)                  |
|  +----------------------------------------------------------+
|                          |                                   |
|                     FFmpeg x11grab                           |
|                          |                                   |
|  +----------------------------------------------------------+
|  | Flask Server (port 8081 interne -> 8082 externe)         |
|  |   /frame.jpg  -> JPEG polling (12 FPS)                   |
|  |   /input      -> xdotool (clics/touches)                 |
|  |   /key/<k>    -> xdotool key                             |
|  +----------------------------------------------------------+
+-------------------------------------------------------------+
                          |
                       HTTP
                          |
                    +-----v-----+
                    |  iPad 1   |
                    |Safari 5.1.1|
                    +-----------+
```

## Contraintes techniques critiques

### Safari 5.1.1 / iOS 5.1.1 (iPad 1)

| Feature | Support |
|---------|---------|
| MJPEG via `<img src>` | Buggy (flickering) |
| JavaScript polling | OK |
| XMLHttpRequest | OK |
| `object-fit` CSS | NON |
| WebSocket | NON |
| WebRTC | NON |
| WebAssembly | NON |
| Flexbox | Partiel |
| CSS Grid | NON |

### Consequences sur le code

1. **Pas de `object-fit: contain`** - Utiliser JavaScript pour calculer manuellement les dimensions
2. **MJPEG streaming direct instable** - Utiliser polling JPEG avec `setInterval`
3. **Pas de ES6** - Utiliser `var`, pas de arrow functions, pas de template literals
4. **XHR uniquement** - Pas de `fetch()`

## Structure des fichiers

```
.
+-- CLAUDE.md              # Ce fichier
+-- Dockerfile             # Image Debian Trixie + DOSBox-X
+-- docker-compose.yml     # Orchestration container
+-- supervisord.conf       # Gestion processus (Xvfb, DOSBox-X, Flask)
+-- openbox-rc.xml         # Config Openbox (maximise fenetres)
|
+-- app/
|   +-- server.py          # Serveur Flask - capture frames + input
|   +-- static/
|       +-- index.html     # Interface web iPad
|
+-- dosbox-x-config/
|   +-- dosbox-x.conf      # Config DOSBox-X pour Railroad Tycoon
|
+-- games/                 # Fichiers du jeu Railroad Tycoon
    +-- GAME.EXE           # Executable principal
    +-- *.PIC, *.DTA       # Assets du jeu
    +-- *.SAV, *.SVE       # Sauvegardes
```

## Fichiers cles

### `app/server.py`

Serveur Flask avec :
- **Thread de capture** : FFmpeg capture frames X11 -> buffer JPEG
- **`/frame.jpg`** : Retourne la derniere frame capturee
- **`/input`** : POST/GET pour clics (xdotool mousemove + click)
- **`/key/<keyname>`** : GET pour touches clavier

Configuration importante :
```python
FRAME_RATE = 12      # FPS cible
VIDEO_SIZE = '640x480'  # Resolution Railroad Tycoon
JPEG_QUALITY = 8     # 2-31, plus bas = meilleure qualite
```

### `supervisord.conf`

Ordre de demarrage :
1. **Xvfb** (priorite 10) - Display virtuel
2. **Openbox** (priorite 15, delai 1s) - Window manager
3. **DOSBox-X** (priorite 20, delai 2s) - Emulateur DOS
4. **Flask** (priorite 30, delai 3s) - Serveur web

### `docker-compose.yml`

Points importants :
- **Port 8082:8081** (externe:interne)
- **Volumes** : `games`, `dosbox-x-config`
- **Memoire** : 512MB
- **`seccomp:unconfined`** : Requis pour xdotool

## Commandes de deploiement

### Build et lancement
```bash
docker-compose build --no-cache
docker-compose up -d
```

### Logs
```bash
docker-compose logs -f
docker exec railroad-tycoon-streaming cat /var/log/supervisor/dosbox_err.log
docker exec railroad-tycoon-streaming cat /var/log/supervisor/webserver.log
```

### Redemarrage
```bash
docker-compose restart
```

### Debug interactif
```bash
docker exec -it railroad-tycoon-streaming bash
```

## Raccourcis Railroad Tycoon

| Touche | Action |
|--------|--------|
| F1 | Aide |
| F2 | Construire voies |
| F3 | Construire gare |
| F4 | Construire depot |
| F5 | Ameliorer gare |
| F6 | Supprimer |
| F7 | Trains |
| F8 | Rapports |
| F9 | Options |
| F10 | Menu principal |
| Space | Pause |
| Enter | Confirmer |
| Escape | Annuler/Menu |
| +/- | Zoom temporel |

## Comparaison avec autres projets streaming

| Aspect | Civ 1 | Civ 2 | Railroad Tycoon |
|--------|-------|-------|-----------------|
| Emulateur | DOSBox | DOSBox-X | DOSBox-X |
| OS | DOS | Windows 3.11 | DOS |
| Resolution | 640x480 | 1024x768 | 640x480 |
| Port | 8080 | 8081 | 8082 |
| Memoire | 512MB | 1024MB | 512MB |

## Problemes connus et solutions

### Image coupee / mal dimensionnee
**Cause** : `object-fit` non supporte par Safari 5.1.1
**Solution** : JavaScript calcule et applique les dimensions manuellement

### Flickering sur MJPEG
**Cause** : Bug Safari 5.1.1 avec `multipart/x-mixed-replace`
**Solution** : Polling JPEG avec cache-busting (`?_=timestamp`)

### Container qui crash (SIGKILL)
**Cause** : Memoire insuffisante
**Solution** : Augmenter `memory` dans docker-compose.yml

### DOSBox-X ne demarre pas
**Cause** : Xvfb pas encore pret
**Solution** : Delai dans supervisord.conf avant DOSBox-X

## Tests

### Verifier que le serveur repond
```bash
curl http://localhost:8082/status
# Doit retourner: OK
```

### Verifier la capture de frames
```bash
curl -o test.jpg http://localhost:8082/frame.jpg
# Doit creer un fichier JPEG valide
```

### Test de clic
```bash
curl -X POST http://localhost:8082/input -d "type=click&x=320&y=240"
```

### Test de touche
```bash
curl http://localhost:8082/key/Return
```
