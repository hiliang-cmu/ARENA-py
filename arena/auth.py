"""
arena/auth.py - Authentication methods for accessing the ARENA.
"""

import json
import os
import pickle
import ssl
import sys
import webbrowser
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError, URLError

from google.auth.transport.requests import AuthorizedSession, Request
from google_auth_oauthlib.flow import InstalledAppFlow

debug_toggle = False
scopes = ["openid",
          "https://www.googleapis.com/auth/userinfo.profile",
          "https://www.googleapis.com/auth/userinfo.email"]
user_gauth_path = f'{str(Path.home())}/.arena_google_auth'
user_mqtt_path = f'{str(Path.home())}/.arena_mqtt_auth'
local_mqtt_path = f'.arena_mqtt_auth'


def authenticate(realm, scene, broker, webhost, debug=False):
    global debug_toggle
    debug_toggle = debug
    print("Signing in to the ARENA...")

    # TODO: remove local check after ARTS supports mqtt_token passing
    # check for local mqtt_token first
    if os.path.exists(local_mqtt_path):
        print("Using local MQTT token.")
        f = open(local_mqtt_path, "r")
        mqtt_json = f.read()
        f.close()
        # TODO: check token expiration
        return json.loads(mqtt_json)

    # begin authentication flow
    creds = None
    browser = None
    try:
        browser = webbrowser.get()
    except (webbrowser.Error) as err:
        print("Console-only login. {0}".format(err))

    # store the user's access and refresh tokens
    if os.path.exists(user_gauth_path):
        print("Using cached Google authentication.")
        with open(user_gauth_path, 'rb') as token:
            creds = pickle.load(token)
        session = AuthorizedSession(creds)
    # if no credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Requesting refreshed Google authentication.")
            creds.refresh(Request())
            session = AuthorizedSession(creds)
        else:
            print("Requesting new Google authentication.")
            gauth_json = get_gauthid(webhost)
            flow = InstalledAppFlow.from_client_config(
                json.loads(gauth_json), scopes)
            if browser:
                # TODO: select best client port to avoid likely conflicts
                creds = flow.run_local_server(port=8989)
            else:
                creds = flow.run_console()
            session = flow.authorized_session()
        with open(user_gauth_path, 'wb') as token:
            # save the credentials for the next run
            pickle.dump(creds, token)
        os.chmod(user_gauth_path, 0o600)  # set user-only perms.

    id_token = creds.id_token
    profile_info = session.get(
        'https://www.googleapis.com/userinfo/v2/me').json()

    # use JWT for authentication
    if profile_info != None:
        mqtt_json = None
        user = profile_info['email']
        print(f'Authenticated Google account: {user}')

        # TODO: permissions may change by owner or admin,
        # for now, get a fresh mqtt_token each time
        # if os.path.exists(user_mqtt_path):
        #     f = open(user_mqtt_path, "r")
        #     mqtt_json = f.read()
        #     f.close()
        # # TODO: check token expiration

        # if no credentials available, get them.
        if not mqtt_json:
            print("Using remote-authenticated MQTT token.")
            mqtt_json = get_mqtt_token(broker, realm, scene, user, id_token)
            # save mqtt_token
            with open(user_mqtt_path, mode="w") as d:
                d.write(mqtt_json)
            os.chmod(user_mqtt_path, 0o600)  # set user-only perms.

    # end authentication flow
    return json.loads(mqtt_json)


# TODO: will be deprecated after using arena-account
def get_gauthid(webhost):
    url = f'https://{webhost}/conf/gauth.json'
    return _urlopen(url)


def get_mqtt_token(broker, realm, scene, user, id_token):
    url = f'https://{broker}/auth/'
    if broker == 'oz.andrew.cmu.edu':
        # TODO: remove this workaround for non-auth broker
        url = f'https://{broker}:8888/'
    params = {
        "id_auth": "google-installed",
        "username": user,
        "id_token": id_token,
        "realm": realm,
        "scene": scene
    }
    query_string = parse.urlencode(params)
    data = query_string.encode("ascii")
    return _urlopen(url, data)


def _urlopen(url, data=None):
    global debug_toggle
    try:
        if debug_toggle:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            res = request.urlopen(url, data=data, context=context)
        else:
            res = request.urlopen(url, data=data)
        return res.read().decode('utf-8')
    except (URLError, HTTPError) as err:
        print("{0}: ".format(err)+url)
        sys.exit("Terminating...")


def signout():
    if os.path.exists(user_gauth_path):
        os.remove(user_gauth_path)
    if os.path.exists(user_mqtt_path):
        os.remove(user_mqtt_path)
    print("Signed out of the ARENA.")


if __name__ == '__main__':
    globals()[sys.argv[1]]()