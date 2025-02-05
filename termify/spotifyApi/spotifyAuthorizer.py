
import os
import base64
import hashlib
import hashlib
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse as urlparse
import webbrowser
from dotenv import set_key, get_key
from time import time
import os
from pathlib import Path

REDIRECT_URI = 'http://localhost:8888/callback'
envPath = Path(os.getenv('TERMIFY_ENV_PATH', Path.home() / '.termify' / '.env'))

class SpotifyAuthorizer:
    def __init__(self):
        self.clientId = get_key(envPath, 'TFY_CLIENT_ID')

        if self.clientId == None:
            raise Exception("Authorization Error: TFY_CLIENT_ID not defined in" + str(envPath))

    def refreshToken(self):
        if get_key(envPath, 'TFY_ACCESS_TOKEN') == None:
            self.requestAuth()
        else:
            if self.tokenExpired():
                self._refreshAccessToken()

        self.token = get_key(envPath, 'TFY_ACCESS_TOKEN')

    def requestAuth(self):
            secret = self._genPkceCodeVerifier()
            challenge = self._genPkceChallenge(secret)
            authUrl = self._getAuthorizationUrl(challenge)
            webbrowser.open(authUrl)
            authCode = self._getResponse()
            tokenJson = self._getAccessTokenJson(authCode, secret)
            self._saveToken(tokenJson)

    def _genPkceCodeVerifier(self):
        secret = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8').rstrip('=')
        return secret

    def _genPkceChallenge(self, codeVerifier):
        hash = hashlib.sha256(codeVerifier.encode('utf-8')).digest()
        hashEncoded = base64.urlsafe_b64encode(hash).decode('utf-8').rstrip('=')
        return hashEncoded

    def _getAuthorizationUrl(self, challenge):
        authUrl = (
            f"https://accounts.spotify.com/authorize"
            f"?client_id={self.clientId}"
            f"&response_type=code"
            f"&redirect_uri={REDIRECT_URI}"
            f"&code_challenge_method=S256"
            f"&code_challenge={challenge}"
            f"&scope=user-read-playback-state user-modify-playback-state"
            )
        return authUrl

    def _getResponse(self):
        authCode = []

        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse.urlparse(self.path)
                query = urlparse.parse_qs(parsed.query)

                if 'code' in query:
                    authCode.append(query['code'][0])
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Authorization complete. You can now close this window :)")
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Authorization failed :/")

            # Overwrite log_message of BaseHTTPRequestHandler to prevent printing to console
            def log_message(self, format, *args):
                pass

        serverAddr = ('', 8888)
        httpd = HTTPServer(serverAddr, RequestHandler)
        httpd.handle_request()
        return authCode[0]

    def _getAccessTokenJson(self, code, codeVerifier):
        tokenUrl = 'https://accounts.spotify.com/api/token' 

        response = requests.post(tokenUrl, data={
            'client_id': self.clientId,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'code_verifier': codeVerifier
            })

        if response.status_code == 200:
            tokenData = response.json()
            return tokenData 
        else:
            raise Exception("Unable to convert auth code into access token - Response:", response.status_code)
        
    def _refreshAccessToken(self):
        refreshToken = get_key(envPath, 'TFY_REFRESH_TOKEN')

        if refreshToken == None:
            self.requestAuth()
            return

        url = 'https://accounts.spotify.com/api/token'
        response = requests.post(url, data={
            'grant_type': 'refresh_token',
            'refresh_token': refreshToken,
            'client_id': self.clientId 
            })

        self._saveToken(response.json())

    def _saveToken(self, tokenJson):
        token = tokenJson.get('access_token')
        refreshToken = tokenJson.get('refresh_token')

        lifetime = int(tokenJson.get('expires_in'))
        currentTime = int(time())

        expirationTime = currentTime + lifetime

        set_key(envPath, "TFY_ACCESS_TOKEN", token)
        set_key(envPath, "TFY_REFRESH_TOKEN", refreshToken)
        set_key(envPath, "TFY_TOKEN_EXPIRATION", str(expirationTime))
    
    def tokenExpired(self):
        try:
           expirationTime = get_key(envPath, 'TFY_TOKEN_EXPIRATION')
           assert(expirationTime != None)
           expirationTime = int(expirationTime)
           currentTime = int(time())
           return currentTime >= expirationTime
        except Exception as e:
            return True


    def getToken(self):
        return get_key(envPath, 'TFY_ACCESS_TOKEN')

