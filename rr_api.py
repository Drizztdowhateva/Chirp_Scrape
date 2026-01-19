"""Radioreference API key encryption helper.

Provides simple utilities to encrypt an API key to a file and load it back
using a passphrase. Uses PBKDF2HMAC + Fernet (symmetric) if the `cryptography`
package is available.

File format (JSON): {"salt": <base64>, "token": <base64>}

Usage:
  # create encrypted file (one-time)
  from rr_api import encrypt_api_key
  encrypt_api_key('MY-API-KEY', 'my-passphrase', outpath='rr_api.enc')

  # load at runtime (set RR_API_PASS env var to the passphrase)
  from rr_api import load_api_key
  key = load_api_key(os.environ['RR_API_PASS'], 'rr_api.enc')
"""
from __future__ import annotations

import os
import json
import base64
from typing import Optional

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.fernet import Fernet
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False
    # Try to install cryptography automatically and re-import
    try:
        import subprocess, sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--quiet', 'cryptography'])
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        from cryptography.fernet import Fernet
        _HAS_CRYPTO = True
    except Exception:
        _HAS_CRYPTO = False


def _derive_key(password: bytes, salt: bytes, iterations: int = 390000) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )
    return base64.urlsafe_b64encode(kdf.derive(password))


def encrypt_api_key(api_key: str, passphrase: str, outpath: str = 'rr_api.enc') -> None:
    """Encrypt `api_key` with `passphrase` and write to `outpath`.

    Requires the `cryptography` package.
    """
    if not _HAS_CRYPTO:
        raise RuntimeError('cryptography package is required to encrypt API keys')
    salt = os.urandom(16)
    key = _derive_key(passphrase.encode('utf-8'), salt)
    f = Fernet(key)
    token = f.encrypt(api_key.encode('utf-8'))
    payload = {
        'salt': base64.b64encode(salt).decode('ascii'),
        'token': base64.b64encode(token).decode('ascii'),
    }
    with open(outpath, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh)


def load_api_key(passphrase: str, path: str = 'rr_api.enc') -> Optional[str]:
    """Load and decrypt API key from `path` using `passphrase`.

    Returns the API key string or raises on failure.
    """
    if not _HAS_CRYPTO:
        raise RuntimeError('cryptography package is required to load encrypted API keys')
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, 'r', encoding='utf-8') as fh:
        payload = json.load(fh)
    salt = base64.b64decode(payload['salt'])
    token = base64.b64decode(payload['token'])
    key = _derive_key(passphrase.encode('utf-8'), salt)
    f = Fernet(key)
    try:
        raw = f.decrypt(token)
    except Exception as e:
        raise RuntimeError('Failed to decrypt API key') from e
    return raw.decode('utf-8')


def api_get(path: str, params: dict | None = None, use_param: bool = False,
            enc_path: str = 'rr_api.enc', passphrase: str | None = None):
    """Perform a GET to RadioReference using the stored API key.

    This helper will attempt to load the API key from `enc_path` using the
    supplied `passphrase`. If `passphrase` is None, it will try the
    `RR_API_PASS` environment variable.

    `use_param` controls whether the key is sent as a query param named
    `apikey` (True) or as an `X-API-Key` header (False). Adjust to match
    the RadioReference API behavior.
    """
    import requests

    if passphrase is None:
        passphrase = os.environ.get('RR_API_PASS')
    if passphrase is None:
        raise RuntimeError('Passphrase not provided; set RR_API_PASS env or pass it explicitly')
    api_key = load_api_key(passphrase, enc_path)
    headers = {}
    if not params:
        params = {}
    if use_param:
        params['apikey'] = api_key
    else:
        headers['X-API-Key'] = api_key
    base = 'https://www.radioreference.com'
    url = base.rstrip('/') + '/' + path.lstrip('/')
    return requests.get(url, headers=headers, params=params, timeout=15)


def login_and_save_api_key(username: str | None = None, password: str | None = None,
                           enc_path: str = 'rr_api.enc', passphrase: str | None = None) -> str:
    """Attempt to log in to RadioReference with provided credentials, retrieve
    the API key from the `/account/api` page, encrypt it to `enc_path` using
    `passphrase` and return the API key.

    This is a best-effort implementation that parses the login form and
    submits credentials. If `passphrase` is None, a random one is generated
    and returned alongside the API key (but the function returns only the
    API key string; callers should save the passphrase if provided).
    """
    if not _HAS_CRYPTO:
        raise RuntimeError('cryptography package is required for login_and_save_api_key')
    import requests
    from bs4 import BeautifulSoup
    import secrets
    session = requests.Session()
    login_page = 'https://www.radioreference.com/account/api'
    r = session.get(login_page, timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')
    # Find the form that contains a password input
    form = None
    for f in soup.find_all('form'):
        if f.find('input', {'type': 'password'}):
            form = f
            break
    if form is None:
        # Try the general account login URL
        r = session.get('https://www.radioreference.com/account/login', timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        for f in soup.find_all('form'):
            if f.find('input', {'type': 'password'}):
                form = f
                break
    if form is None:
        raise RuntimeError('Could not find login form on RadioReference pages')

    action = form.get('action') or login_page
    if action.startswith('/'):
        action = 'https://www.radioreference.com' + action

    payload = {}
    user_set = False
    for inp in form.find_all('input'):
        name = inp.get('name')
        if not name:
            continue
        val = inp.get('value') or ''
        typ = inp.get('type') or 'text'
        if typ == 'password':
            if password is None:
                raise RuntimeError('Password required')
            payload[name] = password
        elif typ in ('text', 'email') and not user_set:
            if username is None:
                raise RuntimeError('Username required')
            payload[name] = username
            user_set = True
        else:
            payload[name] = val

    # Post the form
    post = session.post(action, data=payload, timeout=15)
    # After login attempt, go to /account/api to look for API key
    r2 = session.get('https://www.radioreference.com/account/api', timeout=15)
    s2 = BeautifulSoup(r2.text, 'html.parser')
    text = s2.get_text('\n')
    # Look for an API key pattern (UUID-like)
    import re
    m = re.search(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})', text)
    if not m:
        # Try to find input or code block containing key
        el = s2.find(lambda tag: tag.name in ('code', 'pre') and tag.text and re.search(r'[0-9a-fA-F\-]{32,}', tag.text))
        if el:
            m2 = re.search(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})', el.text)
            if m2:
                m = m2
    if not m:
        raise RuntimeError('API key not found on account page; login may have failed')
    api_key = m.group(1)

    # Ensure we have a passphrase
    if passphrase is None:
        passphrase = secrets.token_urlsafe(24)

    # Encrypt and save the API key
    encrypt_api_key(api_key, passphrase, outpath=enc_path)
    return api_key


def _ensure_zeep():
    """Ensure the `zeep` SOAP client library is available, try to install if missing."""
    try:
        import zeep  # type: ignore
        return zeep
    except Exception:
        try:
            import subprocess, sys
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--quiet', 'zeep'])
            import zeep  # type: ignore
            return zeep
        except Exception:
            return None


def call_soap_method(api_key: str, method_name: str, wsdl: str = 'http://api.radioreference.com/soap2/?wsdl&v=latest', **params):
    """Call a SOAP method using zeep. Returns the raw response object.

    This will try to install `zeep` if it's not present. Pass `api_key` and
    method-specific params as kwargs.
    """
    zeep = _ensure_zeep()
    if zeep is None:
        raise RuntimeError('zeep SOAP client not available and could not be installed')
    from zeep import Client
    client = Client(wsdl)
    service = client.service
    # Prefer passing apiKey param name commonly used
    kwargs = dict(params)
    if 'apiKey' not in kwargs and 'apikey' not in kwargs and 'APIKey' not in kwargs:
        kwargs['apiKey'] = api_key
    func = getattr(service, method_name, None)
    if not func:
        # try camel/lower variants
        for alt in (method_name.lower(), method_name.capitalize()):
            func = getattr(service, alt, None)
            if func:
                break
    if not func:
        raise AttributeError(f'Method {method_name} not found in SOAP service')
    return func(**kwargs)


def try_get_repeaters_via_soap(api_key: str, ctid: str | int, min_mhz: float | None = None, max_mhz: float | None = None):
    """Best-effort: try a few likely SOAP methods to retrieve repeater lists for a CTID.

    Returns a list of dict-like records or raises on failure.
    """
    zeep = _ensure_zeep()
    if zeep is None:
        raise RuntimeError('zeep SOAP client not available')
    # candidate method names based on RadioReference SOAP naming conventions
    candidates = ['GetRepeatersByCTID', 'GetRepeaters', 'GetRepeatersByCounty', 'getRepeaterList', 'GetRepeatersByLocation']
    last_exc = None
    for m in candidates:
        try:
            resp = call_soap_method(api_key, m, ctid=ctid)
            # zeep returns complex types — try to coerce to Python objects
            # If resp is iterable, return list(resp)
            if resp is None:
                continue
            # Convert to list of dicts
            out = []
            # zeep objects may be list-like or single object
            try:
                seq = list(resp)
            except Exception:
                seq = [resp]
            for item in seq:
                try:
                    d = dict(item)
                except Exception:
                    # try attribute access
                    d = {k: getattr(item, k) for k in dir(item) if not k.startswith('_') and not callable(getattr(item, k))}
                out.append(d)
            # optional band filtering
            if min_mhz or max_mhz:
                def in_band(rec):
                    for key in ('Frequency','Freq','frequency','f'):
                        if key in rec and rec[key] is not None:
                            try:
                                fv = float(rec[key])
                                if min_mhz and fv < min_mhz: return False
                                if max_mhz and fv > max_mhz: return False
                                return True
                            except Exception:
                                continue
                    return False
                out = [r for r in out if in_band(r)]
            return out
        except Exception as e:
            last_exc = e
            continue
    raise RuntimeError(f'All SOAP attempts failed; last error: {last_exc}')


def inspect_wsdl(wsdl: str = 'http://api.radioreference.com/soap2/?wsdl&v=latest'):
    """Return a mapping of available SOAP operations and their signatures.

    Uses zeep to parse the WSDL. Returns dict {operation_name: {'input': {param: type}, 'output': type, 'doc': docstring}}
    """
    zeep = _ensure_zeep()
    if zeep is None:
        raise RuntimeError('zeep SOAP client not available')
    from zeep import Client
    client = Client(wsdl)
    ops = {}
    try:
        for service in client.wsdl.services.values():
            for port in service.ports.values():
                binding = port.binding
                for opname, operation in binding._operations.items():
                    inp = {}
                    try:
                        if operation.input:
                            # attempt to list input message parts
                            body_type = operation.input.body.type
                            if hasattr(body_type, 'elements'):
                                for part in body_type.elements:
                                    inp[part[0]] = str(part[1])
                    except Exception:
                        try:
                            sig = operation.input.signature()
                            inp = {'signature': sig}
                        except Exception:
                            inp = {}
                    out = None
                    try:
                        if operation.output:
                            out = str(operation.output.body.type)
                    except Exception:
                        out = None
                    ops[opname] = {'input': inp, 'output': out, 'doc': operation.doc or ''}
    except Exception as e:
        raise RuntimeError(f'Failed to inspect WSDL: {e}')
    return ops
