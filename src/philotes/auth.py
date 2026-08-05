import os
import sys
import json
import urllib.parse
import urllib.request
import secrets
import hashlib
import base64
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from philotes.config import CONFIG_DIR

TOKENS_FILE = CONFIG_DIR / "gcp_tokens.json"
CLIENT_CONFIG_FILE = CONFIG_DIR / "client_secret.json"

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None
    error = None

    def do_GET(self):
        url_parts = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url_parts.query)

        if "code" in query:
            OAuthCallbackHandler.auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Authentication successful! Return to Philotes.</h2></body></html>")
        else:
            OAuthCallbackHandler.error = query.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Authentication failed!</h2></body></html>")

    def log_message(self, format, *args):
        return


class GCPAuthManager:
    def __init__(self, client_json_path=None):
        self.client_json_path = client_json_path or CLIENT_CONFIG_FILE
        self.client_id = None
        self.client_secret = None
        self.auth_uri = "https://accounts.google.com/o/oauth2/auth"
        self.token_uri = "https://oauth2.googleapis.com/token"
        
        self.tokens = self._load_tokens()
        self._load_client_config()

    def _load_client_config(self):
        if not self.client_json_path.exists():
            return False
        
        try:
            with open(self.client_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            config = data.get("installed") or data.get("web")
            if config:
                self.client_id = config.get("client_id")
                self.client_secret = config.get("client_secret")
                self.auth_uri = config.get("auth_uri", self.auth_uri)
                self.token_uri = config.get("token_uri", self.token_uri)
                return True
        except Exception as e:
            sys.stderr.write(f"[Philotes Auth] Error reading client JSON config: {e}\n")
        return False

    def is_configured(self):
        return bool(self.client_id and self.client_secret)

    def is_authenticated(self):
        return bool(self.tokens and "refresh_token" in self.tokens)

    def _load_tokens(self):
        if TOKENS_FILE.exists():
            try:
                with open(TOKENS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                sys.stderr.write(f"[Philotes Auth] Error loading saved tokens: {e}\n")
        return {}

    def _save_tokens(self, tokens_dict):
        self.tokens = tokens_dict
        try:
            with open(TOKENS_FILE, "w", encoding="utf-8") as f:
                json.dump(tokens_dict, f, indent=2)
            os.chmod(TOKENS_FILE, 0o600)
        except Exception as e:
            sys.stderr.write(f"[Philotes Auth] Error saving tokens: {e}\n")

    def perform_pkce_login(self, port=8085):
        if not self.is_configured():
            raise ValueError("GCP client_secret.json is not configured or missing.")

        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("utf-8")).digest()
        ).decode("utf-8").replace("=", "")

        redirect_uri = f"http://127.0.0.1:{port}/oauth/callback"

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }

        auth_url = f"{self.auth_uri}?{urllib.parse.urlencode(params)}"
        
        server = HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None

        webbrowser.open(auth_url)
        server.handle_request()

        if OAuthCallbackHandler.error:
            raise RuntimeError(f"OAuth failed: {OAuthCallbackHandler.error}")

        auth_code = OAuthCallbackHandler.auth_code
        if not auth_code:
            raise RuntimeError("Failed to receive authorization code.")

        token_data = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }).encode("utf-8")

        req = urllib.request.Request(self.token_uri, data=token_data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req) as resp:
            tokens_response = json.loads(resp.read().decode("utf-8"))

        self._save_tokens(tokens_response)
        return tokens_response

    def refresh_access_token(self):
        refresh_token = self.tokens.get("refresh_token")
        if not refresh_token:
            raise ValueError("No refresh_token found. Login required.")

        token_data = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")

        req = urllib.request.Request(self.token_uri, data=token_data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req) as resp:
            tokens_response = json.loads(resp.read().decode("utf-8"))

        if "refresh_token" not in tokens_response:
            tokens_response["refresh_token"] = refresh_token

        self._save_tokens(tokens_response)
        return tokens_response
