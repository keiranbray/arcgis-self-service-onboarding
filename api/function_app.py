import logging
import os
import json
import traceback
from copy import deepcopy
import azure.functions as func
import requests

PORTAL = os.getenv("PORTAL_URL")
MGR_USER = os.getenv("MGR_USER")
MGR_PWORD = os.getenv("MGR_PWORD")
CONFIG_LAYER_ID = os.getenv("CONFIG_LAYER_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
REDIRECT_URI = os.getenv("CALLBACK_URL")

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="check-permissions", methods=[func.HttpMethod.POST])
def add_existing_user(req: func.HttpRequest) -> func.HttpResponse:
    '''Adds an existing ArcGIS user to the group 
    and redirects them to the app'''
    logging.info(PORTAL)
    logging.info(MGR_USER)
    logging.info(CONFIG_LAYER_ID)
    logging.info(CLIENT_ID)
    logging.info(REDIRECT_URI)

    logging.info('Python HTTP trigger function ' \
    'processed a request to add a user to a group.')
    try:
        body = req.get_json()
        logging.info(body)
        code = body.get("code")
        verifier = body.get("verifier")
        globalid = body.get("globalid")

        # Get tokens for the admin and the user
        user_token = _get_user_token(PORTAL, CLIENT_ID, code,
                                    REDIRECT_URI, verifier)
        mgr_token = _get_grp_mgr_token(MGR_USER,
                                      MGR_PWORD, REDIRECT_URI)

        if user_token is None:
            result = {"message": "Could not get user token"}
            logging.info(result)
            return func.HttpResponse(json.dumps(result),
                                status_code=500)
        if mgr_token is None:
            result = {"message": "Could not get admin token"}
            logging.info(result)
            return func.HttpResponse(json.dumps(result),
                                status_code=500)

        # Get the app details so we know which group to add them to
        app_details = _get_app_details(PORTAL, CONFIG_LAYER_ID,
                            globalid, mgr_token, REDIRECT_URI)
        if "group_id" not in app_details or \
              'redirect_uri' not in app_details:
            result = {"message": "Couldn't get group id or \
                      redirect uri from config. \
                      Field is missing from config table."}
            logging.error("Couldn't get group id or \
                          redirect uri from config.")
            return func.HttpResponse(json.dumps(result),
                                     status_code=500)
        group_id = app_details["group_id"]

        # Check if user in same or different org
        username = _get_username_from_token(PORTAL, user_token)
        group_org = _get_user_org(PORTAL, mgr_token)
        user_org = _get_user_org(PORTAL, user_token)
        logging.info(username)
        logging.info(group_org)
        logging.info(user_org)

        # If not in same org, invite and accept on their behalf
        invite = False
        if user_org is None or user_org != group_org:
            invite = True
        message, status_code = _add_user_to_group(PORTAL,
                        mgr_token, username, group_id,
                        REDIRECT_URI, invite, user_token)

        result = {
            "message": message,
            "redirect_uri": app_details["redirect_uri"]
        }
    except Exception as e:
        logging.error(traceback.format_exc())
        result = {
            "message": e
        }
        status_code = 500

    return func.HttpResponse(json.dumps(result),
                             status_code=status_code)


@app.route(route="signup", methods=[func.HttpMethod.POST])
def user_signup(req: func.HttpRequest) -> func.HttpResponse:
    '''Creates a new user account, adds user to 
    group and redirects them to the app'''
    logging.info('Python HTTP trigger function \
                 processed a request to create a user.')
    logging.info(PORTAL)
    logging.info(MGR_USER)
    logging.info(CONFIG_LAYER_ID)
    logging.info(CLIENT_ID)
    logging.info(REDIRECT_URI)
    try:
        try:
            data = req.get_json()
        except ValueError:
            result = {
                "message": "Invalid JSON",
            }
            return func.HttpResponse(json.dumps(result),
                                     status_code=400)

        logging.info(deepcopy(data).pop("password", None))
        username = data.get("username")
        password = data.get("password")
        given_name = data.get("given_name")
        family_name = data.get("family_name")
        email = data.get("email")
        globalid = data.get("globalid")

        # Get a token for the manager
        mgr_token = _get_grp_mgr_token(MGR_USER,
                        MGR_PWORD, REDIRECT_URI)
        if mgr_token is None:
            result = {"message": "Could not get admin token"}
            return func.HttpResponse(json.dumps(result),
                                status_code=500)

        # Get the licence id for new user and group details
        app_details = _get_app_details(PORTAL,
                    CONFIG_LAYER_ID, globalid, mgr_token,
                    REDIRECT_URI)

        for attr in ('group_id', 'user_license_id',
                     'user_role_id', 'redirect_uri'):
            if attr not in app_details:
                result = {"message": f"Couldn't get {attr}. \
                          Field is missing from config table."}
                logging.error("Could not get required details from layer.")
                return func.HttpResponse(json.dumps(result),
                                         status_code=500)
        group_id = app_details["group_id"]

        if app_details["user_license_id"] in (None, '') or \
            app_details["user_role_id"] in (None, ''):
            result = {"message": "Signup is not enabled. \
                      Sign in with an existing account \
                      or contact an administrator."}
            logging.error(result)
            return func.HttpResponse(json.dumps(result),
                                     status_code=403)

        new_user, message = _create_portal_user(
            portal_url=PORTAL,
            token=mgr_token,
            username=username,
            password = password,
            firstname = given_name,
            lastname = family_name,
            email = email,
            role = app_details["user_role_id"],
            user_type= app_details["user_license_id"],
            redirect_uri=REDIRECT_URI,
            group_id = group_id
        )
        if new_user:
            logging.info(new_user)
            # Add the user to the group
            message, status_code = _add_user_to_group(
                PORTAL, mgr_token, username,
                group_id, REDIRECT_URI, False)

            result = {
                "message": message,
                "redirect_uri": app_details["redirect_uri"]
            }
            return func.HttpResponse(json.dumps(result),
                                    status_code=status_code)
        else:
            result = {
                "message": f"Could not create new user. \
                    {message}. Please contact an administrator.",
            }
            logging.error(result)
            return func.HttpResponse(json.dumps(result),
                                    status_code=500)

    except Exception as e:
        logging.error("General error: %s",
                          traceback.format_exc())
        result = {
                "message": f"An unexpected error occurred: {e}",
            }
        return func.HttpResponse(json.dumps(result),
                                    status_code=500)

def _get_user_token(portal, client_id, code, redirect_uri, verifier):
    '''Gets a token using authorization code with pkce
    :param portal: base url for portal/agol
    :param client_id: oauth2 client id
    :param code: authorization code
    :param redirect_uri: oauth redirect uri
    :param verifier: pkce verifier
    :return token:str'''
    token_url = f"{portal}/sharing/rest/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier
    }

    reqs = requests.post(token_url, data=data, timeout=10)
    try:
        data = reqs.json()
        return data["access_token"]
    except:
        logging.error(traceback.format_exc())
        return None

def _get_grp_mgr_token(user, pword, referer):
    '''Gets a token for the group manager/user creator
    using legacy generateToken as oauth requires user
    auth for adding users to groups
    :param user: username
    :param pword: password
    :param referer: referer header
    :return token:str'''
    url = f"{PORTAL}/sharing/rest/generateToken"
    data = {
        "username": user,
        "password": pword,
        "client": "referer",
        "referer": referer,
        "expiration": 60,
        "f": "json"
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        token_info = response.json()
        return token_info["token"]
    except:
        logging.error(traceback.format_exc())
        return None    

def _get_username_from_token(portal, user_token):
    '''Gets the username of the user from the token
    :param portal: base url
    :param user_token: user's token
    return username: str'''
    try:
        reqs = requests.get(
            f"{portal}/sharing/rest/portals/self?f=json&token={user_token}",
            timeout=10)
        data = reqs.json()

        username = data["user"]["username"]
        logging.info(username)
        return username
    except:
        logging.error(traceback.format_exc())
        return None


def _get_app_details(base_url, config_layer_id, globalid, token, redirect_uri):
    """
    Gets the record from the config feature 
    layer and returns the attributes.
    
    :param base_url: Base URL of your ArcGIS portal 
        (e.g. "https://organization.example.com/<context>")
    :param config_layer_id: Item ID of the config Feature Service
    :param globalid: The GlobalID to match
    :param token: A valid ArcGIS token
    :param redirect_uri: used as referer header
    :return arcgis feature attributes (dict)
    """

    # Get the feature service url
    url = f"{base_url}/sharing/rest/content/items/{config_layer_id}"
    headers = {"referer": redirect_uri}
    item_info = requests.get(url, params={"token": token, "f": "json"},
                             timeout=10).json()

    # create the url, assuming config is table 0
    query_url = item_info["url"]+"/0/query"

    params = {
        "where": f"GlobalID = '{globalid}'",
        "outFields": "*",
        "f": "json",
        "token": token
    }

    try:
        response = requests.post(query_url,
                                 data=params,
                                 headers=headers,
                                 timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("features"):
            raise ValueError(f"No features found for GlobalID {globalid}")

        details = data["features"][0]["attributes"]
        return details
    except:
        logging.error(traceback.format_exc())
        return {}


def _add_user_to_group(base_url, mgr_token, user, group_id,
                      redirect_uri, invite=False, user_token=None):
    """
    Adds a user to a group (or invites them) using ArcGIS REST API.
    
    :param base_url: Base URL of your ArcGIS Portal 
        (e.g. https://organization.example.com/<context>)
    :param token: Valid ArcGIS token
    :param user: Username to add
    :param group_id: Group ID
    :param invite: Whether to send an invitation instead of direct add
    :return: (message:str, http_status_code:int)
    """

    try:
        # --- Step 1: Get current group membership
        members_url = f"{base_url}/sharing/rest/community/groups/{group_id}/users"
        params = {"f": "json", "token": mgr_token}
        headers = {"referer": redirect_uri}
        r = requests.get(members_url,
                         params=params,
                         headers=headers,
                         timeout=10)
        r.raise_for_status()
        members = r.json()

        if "error" in members:
            return f"Error getting group members: \
                {members['error']['message']}", 400

        if user == members.get("owner") or \
           user in members.get("admins", []) or \
           user in members.get("users", []):
            logging.info("User already in group")
            return "User already in group", 200

        # --- Step 2: Add or invite user
        if invite:
            success = _group_invite_user(base_url, group_id,
                        user, mgr_token, redirect_uri)
            if not success:
                return "User could not be invited to group", 500
            success = _group_accept_invite(base_url,
                        user, user_token, group_id, redirect_uri)
            if not success:
                return "Please sign in to ArcGIS and manually \
                    accept the group invite.", 500
            return "User invited to group", 200
        else:
            success = _group_add_user(base_url, group_id,
                    user, mgr_token, redirect_uri)
            if not success:
                return "User could not be added to the group. \
                    Contact an administrator.", 400
            return "User added to group", 200

    except Exception as e:
        logging.error("An error occurred adding the user\
                       to the group: %s", traceback.format_exc())
        return f"An error occurred adding the user to \
            the group: {e}. Contact an administrator.", 500

def _group_invite_user(base_url, group_id, user, mgr_token, redirect_uri):
    '''
    Invites a user to a group
    :param base_url: Base URL of your ArcGIS Portal 
        (e.g. https://organization.example.com/<context>)
    :param group_id: Group ID
    :param user: Username to add
    :param mgr_token: Valid ArcGIS token for group manager
    :param redirect_url: Referer header
    :return: bool
    '''
    headers = {"referer": redirect_uri}
    invite_url = f"{base_url}/sharing/rest/community/groups/{group_id}/invite"
    data = {
        "users": user,
        "f": "json",
        "token": mgr_token
    }
    resp = requests.post(invite_url, data=data,
                         headers=headers, timeout=10)
    resp.raise_for_status()
    result = resp.json()

    if not result.get("success"):
        return False
    return True

def _group_accept_invite(base_url, user, user_token, group_id, redirect_uri):
    '''
    Accepts invite on behalf of user
    :param base_url: Base URL of your ArcGIS Portal 
        (e.g. https://organization.example.com/<context>)
    :param user: Username to add
    :param user_token: Valid ArcGIS token for new group user
    :param group_id: Group ID
    :param redirect_url: Referer header
    :return: bool
    '''
    headers = {"referer": redirect_uri}
    user_invites_url = f"{base_url}/sharing/rest/community/users/{user}/invitations"
    params = {"f": "json", "token": user_token}
    resp = requests.get(user_invites_url,
                        params=params,
                        headers=headers,
                        timeout=10)
    resp.raise_for_status()
    result = resp.json()
    found = False
    for invite in result["userInvitations"]:
        if invite["groupId"] == group_id:
            user_invites_url = f"{base_url}/sharing/rest/community/users/{user}/invitations/{invite['id']}/accept"
            data = {
                "f": "json",
                "token": user_token
            }
            resp = requests.post(user_invites_url, data=data,
                                 headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            if "success" not in result or result["success"] is False:
                return False
            found = True
            break

    return found

def _group_add_user(base_url, group_id, user, mgr_token, redirect_uri):
    '''Adds a user to the group
    :param base_url: Base URL of your ArcGIS Portal 
        (e.g. https://organization.example.com/<context>)
    :param group_id: Group ID
    :param user: Username to add
    :param mgr_token: Valid ArcGIS token for group manager
    :param redirect_url: Referer header
    :return: bool
    '''
    headers = {"referer": redirect_uri}
    add_url = f"{base_url}/sharing/rest/community/groups/{group_id}/addUsers"
    data = {
        "users": user,
        "f": "json",
        "token": mgr_token
    }
    resp = requests.post(add_url, data=data,
                         headers=headers, timeout=10)
    resp.raise_for_status()
    result = resp.json()

    not_added = result.get("notAdded", [])
    if user in not_added:
        logging.info("User could not be added to group")
        return False

    logging.info("User added to group")
    return True

def _get_user_org(portal_url: str, token: str) -> str:
    """
    Determines what org the user is a member of using their token

    Args:
        portal_url (str): Base portal URL, e.g. 
            "https://myorg.maps.arcgis.com" 
            or "https://portal.domain.com/portal"
        token (str): User's token

    Returns:
        str: orgId of the user
    """
    # Query current user info
    url = f"{portal_url}/sharing/rest/community/self"
    params = {
        "token": token,
        "f": "json"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        user_info = response.json()

        if "error" in user_info:
            raise RuntimeError(f"Error fetching user info: {user_info['error']}")

        cur_user_org = user_info.get("orgId")
        logging.info(f"User org: {cur_user_org}")

        return cur_user_org
    except Exception as e:
        logging.error("An error occurred getting the \
                      org id: %s", traceback.format_exc())
        return None      


def _create_portal_user(portal_url: str, token: str,
                username: str, password: str,
                firstname: str, lastname: str,
                email: str, role: str, user_type: str,
                redirect_uri: str, group_id: str):
    """
    Creates a new user in ArcGIS using the REST API.

    Args:
        portal_url (str): Base portal URL, 
            e.g., https://organization.example.com/arcgis
        token (str): Admin token
        username (str): Username for new user
        password (str): Password
        firstname (str): First name
        lastname (str): Last name
        email (str): Email address
        role (str): Role, e.g., 'iAAAAAAAAA', 'iBBBBBBBB'
        user_type (str): License type, e.g., 'creatorUT', 'viewerUT', etc.
        redirect_uri: redirect uri used for token referer
        group_id: group to be added to


    Returns:
        bool: success
    """

    # Get default credit assignment
    reqs = requests.get(f"{portal_url}/sharing/rest/portals/self?f=json&token={token}",
                        timeout=10)
    data = reqs.json()
    _credits = data.get("defaultUserCreditAssignment")
    if _credits is None:
        _credits = -1

    headers = {"referer": redirect_uri}
    if "arcgis.com" in portal_url:
        params = {
            "f": "json",
            "token": token,
            "invitationList": json.dumps({
                "invitations": [
                    {
                        "username": username,
                        "firstname": firstname,
                        "lastname": lastname,
                        "fullname": firstname + " " + lastname,
                        "email": email,
                        "password": password,
                        "role": role,
                        "userLicenseType": user_type,
                        "groups": group_id,
                        "userCreditAssignment": _credits,
                        "userType": "arcgisonly"
                    }
                ],
                "apps": [],
                "appBundles": [],
            })
        }
        res = requests.post(f"{portal_url}/sharing/rest/portals/self/invite",
                            data=params, headers=headers, timeout=10)
        resp = res.json()
        logging.info(resp)
        if not resp.get("error"):
            if username in resp["notInvited"]:
                logging.error("Unable to create " + username)
                return False, "Username may already exist."
        else:
            logging.error("Can't create " + username)
            return False, resp["error"]["details"]
        return True, None  

    else:
        url = f"{portal_url}/portaladmin/security/users/createUser"
        data = {
            "username": username,
            "password": password,
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "role": role,
            "userLicenseTypeId": user_type,
            "f": "json",
            "token": token
        }

        try:
            response = requests.post(url, data=data, 
                                     headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                logging.error(f"Error creating user: \
                              {result['error']['details']}")
                raise RuntimeError(result)
            return True, None

        except Exception as e:
            logging.error("An error occurred creating the \
                          user: %s", traceback.format_exc())
            return False, e
