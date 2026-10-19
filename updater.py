"""Local updater for Glaycon Nova.

An update is a folder (or .zip) inside  <bot folder>/updates/  that holds an update.json plus the changed files:

    updates/v4.44/update.json
    updates/v4.44/nova_bot.py          (files keep their path inside the bot folder)
    updates/v4.44/templates/x.png

update.json:  {"version": "v4.44", "date": "2026-10-17", "notes": ["what is new", ...],
               "files": {"nova_bot.py": "<sha256>", ...}, "delete": ["old_file.py"]}

Installing backs up every file it replaces to  backups/<old version>_<time>/  and rolls back by itself if the new
version does not start properly.  Your logins, settings, progress, history, calibration, log and screenshots are
never touched.  No internet is used - updates only ever come from the updates folder.
Run as a script (`pythonw updater.py --restart <pid>`) it acts as the restart helper.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPDATES = 'updates'
BACKUPS = 'backups'
STATE_FILE = 'update_state.json'
OK_FILE = 'update_ok.flag'
ALLOWED_EXT = {'.py', '.png', '.txt', '.json', '.bat', '.md', '.ico', '.jpg', '.jpeg', '.gif', '.wav', '.mp3'}
PROTECTED_NAMES = {'account.json', 'accounts.json', 'settings.json', 'state.json', 'history.json', 'calibration.json',
                   'positions.json', 'nova_v2.log', STATE_FILE, OK_FILE, 'glaycon nova.exe'}
PROTECTED_DIRS = {'.venv', 'venv', 'screenshots', 'recordings', 'debug', 'backups', 'updates', '__pycache__', '.git'}
KEEP_BACKUPS = 8
LAST_PROBLEM = {}      # package name -> why it was skipped (shown in the log)
# Remote updates: downloaded from this public GitHub repo, and installed ONLY if the manifest carries a valid
# signature made with the owner's private key (the matching public key is below).
REMOTE_BASE = 'https://raw.githubusercontent.com/Nirexjava/glaycon-nova-updates/main/'
PUBLIC_KEY = bytes.fromhex('02c49e2baa58c51a32fbccf332cf7031a9e5062f6f18db5d6fcd08ff8818c6ba')
MAX_FILE = 30 * 1024 * 1024


def parse_version(v):
    nums = re.findall(r'\d+', str(v))
    return tuple(int(n) for n in nums) if nums else (0,)


def is_newer(a, b):
    """True if version a is newer than b."""
    return parse_version(a) > parse_version(b)


def safe_rel(root, rel):
    """Return the absolute target for a relative path, or None if it is not allowed."""
    if not isinstance(rel, str) or not rel:
        return None
    rel = rel.replace('\\', '/')
    if rel.startswith('/') or re.match(r'^[A-Za-z]:', rel):
        return None
    parts = rel.split('/')
    if any(p in ('', '.', '..') for p in parts):
        return None
    if parts[-1].lower() in PROTECTED_NAMES or any(p.lower() in PROTECTED_DIRS for p in parts[:-1]):
        return None
    if Path(rel).suffix.lower() not in ALLOWED_EXT:
        return None
    root = Path(root).resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------- Ed25519 signature check (pure Python, RFC 8032)
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, -1, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _xrec(y):
    xx = (y * y - 1) * pow(_D * y * y + 1, -1, _P) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P:
        x = x * _I % _P
    if x % 2:
        x = _P - x
    return x


_BY = 4 * pow(5, -1, _P) % _P
_B = (_xrec(_BY) % _P, _BY)


def _add(a, b):
    x1, y1 = a
    x2, y2 = b
    t = _D * x1 * x2 * y1 * y2
    return ((x1 * y2 + x2 * y1) * pow(1 + t, -1, _P) % _P, (y1 * y2 + x1 * x2) * pow(1 - t, -1, _P) % _P)


def _mul(pt, e):
    r = (0, 1)
    while e:
        if e & 1:
            r = _add(r, pt)
        pt = _add(pt, pt)
        e >>= 1
    return r


def _decode_pt(b):
    y = int.from_bytes(b, 'little')
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= _P:
        raise ValueError('bad point')
    x = _xrec(y)
    if (x * x - (y * y - 1) * pow(_D * y * y + 1, -1, _P)) % _P:
        raise ValueError('bad point')
    if x & 1 != sign:
        x = _P - x
    return (x, y)


def ed25519_verify(pub, sig, msg):
    try:
        if len(pub) != 32 or len(sig) != 64:
            return False
        a = _decode_pt(pub)
        r = _decode_pt(sig[:32])
        s = int.from_bytes(sig[32:], 'little')
        if s >= _L:
            return False
        h = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), 'little') % _L
        return _mul(_B, s) == _add(r, _mul(a, h))
    except Exception:
        return False


# ------------------------------------------------------------------- remote
def _fetch(url, limit=MAX_FILE, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': 'GlayconNova-updater', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError('file too large')
    return data


def check_remote(root, current, base=None, pub=None):
    """Look at the signed manifest online; if it is newer, download what differs into updates/<version>/.
    Returns (version_or_None, error_text). Never raises."""
    base = base or REMOTE_BASE
    pub = pub or PUBLIC_KEY
    root = Path(root)
    try:
        raw = _fetch(base + 'manifest.json', 1 << 20)
        sig = base64.b64decode(_fetch(base + 'manifest.sig', 4096).strip())
    except Exception as exc:
        return None, f'could not reach the update server ({exc})'
    if not ed25519_verify(pub, sig, raw):
        return None, 'the online update is NOT signed by the owner - ignored'
    try:
        meta = json.loads(raw.decode('utf-8'))
        ver = str(meta['version'])
        files = meta['files']
        assert isinstance(files, dict)
    except Exception:
        return None, 'the online update list is unreadable'
    if not is_newer(ver, current):
        return None, ''
    if meta.get('base') and is_newer(str(meta['base']), current):
        return None, f'this update needs at least {meta["base"]} - please install the latest full zip once'
    dest = root / UPDATES / ver
    if (dest / 'update.json').is_file():
        return ver, ''
    todo = {}
    for rel, want in files.items():
        tgt = safe_rel(root, rel)
        if tgt is None:
            return None, f'the online update tries to change a protected file ({rel}) - ignored'
        if tgt.is_file() and sha256(tgt) == str(want).lower():
            continue
        todo[rel] = str(want).lower()
    delete = [d for d in meta.get('delete', []) if isinstance(d, str) and safe_rel(root, d) is not None and safe_rel(root, d).is_file()]
    if not todo and not delete:
        return None, ''
    tmp = root / UPDATES / (ver + '.partial')
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        for rel, want in todo.items():
            data = _fetch(base + 'files/' + urllib.parse.quote(rel))
            if _sha_bytes(data) != want:
                raise ValueError(f'{rel} did not match its checksum')
            out = tmp / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        pm = {'version': ver, 'date': meta.get('date', ''), 'notes': meta.get('notes', []), 'files': todo, 'delete': delete}
        (tmp / 'update.json').write_text(json.dumps(pm, indent=1), encoding='utf-8')
        shutil.rmtree(dest, ignore_errors=True)
        os.replace(tmp, dest)
    except Exception as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, f'download failed ({exc})'
    return ver, ''


# ------------------------------------------------------------------ discovery
class Package:
    """One update package: a folder or a zip. read(rel) returns the bytes of a file inside it."""

    def __init__(self, path, meta):
        self.path = Path(path)
        self.meta = meta
        self.version = str(meta.get('version', ''))
        self.notes = [str(n) for n in meta.get('notes', [])] if isinstance(meta.get('notes'), list) else []
        self.date = str(meta.get('date', ''))
        files = meta.get('files', {})
        self.files = files if isinstance(files, dict) else {}
        self.delete = [d for d in meta.get('delete', []) if isinstance(d, str)] if isinstance(meta.get('delete'), list) else []
        self.base = ''      # prefix inside a zip when update.json is not at its top

    def read(self, rel):
        if self.path.is_dir():
            return (self.path / rel).read_bytes()
        with zipfile.ZipFile(self.path) as z:
            return z.read(self.base + rel)


def load_package(path):
    path = Path(path)
    try:
        if path.is_dir():
            meta = json.loads((path / 'update.json').read_text(encoding='utf-8'))
            pkg = Package(path, meta)
        elif path.suffix.lower() == '.zip':
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                cand = [n for n in names if n.replace('\\', '/').split('/')[-1] == 'update.json'
                        and n.count('/') <= 1]
                if not cand:
                    return None
                cand.sort(key=lambda n: n.count('/'))
                meta = json.loads(z.read(cand[0]).decode('utf-8'))
                pkg = Package(path, meta)
                pkg.base = cand[0][:-len('update.json')]
        else:
            return None
    except (OSError, ValueError, zipfile.BadZipFile, KeyError):
        return None
    if not isinstance(pkg.meta, dict) or not pkg.version or not pkg.files and not pkg.delete:
        return None
    return pkg


def find_pending(root, current):
    """The newest valid package in <root>/updates that is newer than `current`, or None."""
    udir = Path(root) / UPDATES
    best = None
    if not udir.is_dir():
        return None
    try:
        entries = sorted(udir.iterdir())
    except OSError:
        return None
    bad = read_state(root).get('bad', [])
    for p in entries:
        pkg = load_package(p)
        if pkg is None or not is_newer(pkg.version, current) or pkg.version in bad:
            continue
        if best is not None and not is_newer(pkg.version, best.version):
            continue
        ok, problem = verify(root, pkg)          # a damaged package is skipped (another one of the same version may be fine)
        if not ok:
            LAST_PROBLEM[str(pkg.path.name)] = problem
            continue
        best = pkg
    return best


def verify(root, pkg):
    """Return (ok, problem). Checks every path is allowed and every file's hash matches before anything is touched."""
    for rel, want in pkg.files.items():
        if safe_rel(root, rel) is None:
            return False, f'not allowed to update "{rel}"'
        try:
            data = pkg.read(rel)
        except (OSError, KeyError, zipfile.BadZipFile):
            return False, f'file "{rel}" is missing from the update'
        if want and _sha_bytes(data) != str(want).lower():
            return False, f'file "{rel}" is damaged (checksum differs)'
        if rel.endswith('.py'):
            try:
                compile(data, rel, 'exec')
            except SyntaxError as exc:
                return False, f'"{rel}" has a code error ({exc.msg}, line {exc.lineno})'
    for rel in pkg.delete:
        if safe_rel(root, rel) is None:
            return False, f'not allowed to delete "{rel}"'
    return True, ''


# ------------------------------------------------------------------- install
def _write_state(root, data):
    try:
        (Path(root) / STATE_FILE).write_text(json.dumps(data, indent=1), encoding='utf-8')
    except OSError:
        pass


def read_state(root):
    try:
        d = json.loads((Path(root) / STATE_FILE).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def install(root, pkg, current):
    """Back up and replace files. Returns (ok, message, backup_dir). Rolls back by itself on any error."""
    root = Path(root)
    ok, problem = verify(root, pkg)
    if not ok:
        return False, problem, None
    stamp = time.strftime('%Y%m%d-%H%M%S')
    bdir = root / BACKUPS / f'{current}_{stamp}'
    touched = list(pkg.files) + [d for d in pkg.delete if d not in pkg.files]
    existed = []
    try:
        bdir.mkdir(parents=True, exist_ok=True)
        for rel in touched:
            tgt = safe_rel(root, rel)
            if tgt.is_file():
                dst = bdir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tgt, dst)
                existed.append(rel)
        (bdir / 'manifest.json').write_text(json.dumps({'from': current, 'to': pkg.version, 'existed': existed,
                                                        'new': [r for r in pkg.files if r not in existed]}, indent=1), encoding='utf-8')
    except OSError as exc:
        return False, f'could not make a backup: {exc}', None
    try:
        for rel in pkg.files:
            tgt = safe_rel(root, rel)
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tmp = tgt.with_name(tgt.name + '.new')
            tmp.write_bytes(pkg.read(rel))
            os.replace(tmp, tgt)
        for rel in pkg.delete:
            tgt = safe_rel(root, rel)
            if tgt.is_file():
                tgt.unlink()
    except Exception as exc:
        rollback(root, bdir)
        return False, f'install failed and was undone: {exc}', None
    _write_state(root, {'status': 'installed', 'version': pkg.version, 'from': current, 'backup': str(bdir),
                        'time': time.time(), 'notes': pkg.notes, 'bad': read_state(root).get('bad', [])})
    try:
        (root / OK_FILE).unlink()
    except OSError:
        pass
    _prune_backups(root)
    return True, f'installed {pkg.version}', bdir


def rollback(root, bdir):
    """Put back every file from a backup (and remove files the update added)."""
    root, bdir = Path(root), Path(bdir)
    try:
        man = json.loads((bdir / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        man = {}
    n = 0
    for rel in man.get('existed', []):
        src, tgt = bdir / rel, safe_rel(root, rel)
        if tgt is not None and src.is_file():
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, tgt)
            n += 1
    for rel in man.get('new', []):
        tgt = safe_rel(root, rel)
        if tgt is not None and tgt.is_file():
            try:
                tgt.unlink()
            except OSError:
                pass
    return n


def _prune_backups(root):
    bdir = Path(root) / BACKUPS
    try:
        items = sorted([p for p in bdir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)
        for p in items[:-KEEP_BACKUPS]:
            shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def confirm_ok(root, version=''):
    """Called by the app once it has been running healthily: the update stays."""
    try:
        (Path(root) / OK_FILE).write_text(str(version), encoding='utf-8')
    except OSError:
        pass
    st = read_state(root)
    if st.get('status') == 'installed':
        st['status'] = 'confirmed'
        _write_state(root, st)


def startup_note(root, current):
    """For the app's log at start: what happened with the last update. Returns text or ''."""
    st = read_state(root)
    if st.get('status') == 'rolled_back':
        if st.get('rb_announced'):
            return ''
        st['rb_announced'] = True
        _write_state(root, st)
        return f'The update to {st.get("version")} did not start properly, so the bot went back to {st.get("from")}. Reason: {st.get("reason", "?")}'
    if st.get('status') in ('installed', 'confirmed') and st.get('version') == current and not st.get('announced'):
        st['announced'] = True
        _write_state(root, st)
        return f'Updated from {st.get("from")} to {current}.'
    return ''


# ------------------------------------------------------------------- restart
def _gui_python():
    exe = Path(sys.executable)
    pw = exe.with_name('pythonw.exe')
    return str(pw if pw.exists() else exe)


def spawn_restart_helper(root, pid):
    """Start a detached helper that waits for this process to exit, relaunches the bot and checks it came up."""
    flags = 0
    if os.name == 'nt':
        flags = 0x00000008 | 0x00000200      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([_gui_python(), str(Path(root) / 'updater.py'), '--restart', str(pid)], cwd=str(root),
                     creationflags=flags, close_fds=True)


def _pid_alive(pid):
    if os.name == 'nt':
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))     # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _launch(root):
    flags = 0x00000008 if os.name == 'nt' else 0
    return subprocess.Popen([_gui_python(), str(Path(root) / 'nova_bot.py')], cwd=str(root), creationflags=flags, close_fds=True)


def _flag_ok(root, st):
    try:
        return (Path(root) / OK_FILE).read_text(encoding='utf-8').strip() == str(st.get('version'))
    except OSError:
        return False


def helper_main(root, pid, wait_ok=150.0, wait_exit=60.0):
    """Restart helper: wait for the old process, start the new one, roll back if it does not come up."""
    root = Path(root)
    t0 = time.time()
    while _pid_alive(pid) and time.time() - t0 < wait_exit:
        time.sleep(0.3)
    time.sleep(1.5)       # let the debugging port free up
    st = read_state(root)
    check = st.get('status') == 'installed'
    proc = _launch(root)
    if not check:
        return 0
    t1 = time.time()
    while time.time() - t1 < wait_ok:
        if _flag_ok(root, st):
            return 0
        time.sleep(0.5)
    if _flag_ok(root, st):
        return 0
    # the new version never reported that it was running: undo it
    try:
        if proc.poll() is None:
            proc.kill()
    except Exception:
        pass
    n = rollback(root, st.get('backup', ''))
    bad = list(st.get('bad', []))
    if st.get('version') and st['version'] not in bad:
        bad.append(st['version'])
    st.update({'status': 'rolled_back', 'reason': 'it did not report a healthy start within %d s' % wait_ok,
               'restored': n, 'bad': bad})
    _write_state(root, st)
    time.sleep(2.0)
    _launch(root)
    return 1


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--restart':
        sys.exit(helper_main(ROOT, int(sys.argv[2])))
    print('This file is used by the bot (UPDATE button). Nothing to run here.')
