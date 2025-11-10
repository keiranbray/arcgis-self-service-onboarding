# arcgis-alternative-signin-web

This repository shows how you can quickly set up a Static Web App in Microsoft Azure which provides a
self-service interface for users to onboard themselves into an ArcGIS Online or ArcGIS Enterprise group.
The app helps to remove the reliance on ArcGIS Administrators and Group Managers in time-critical situations,
freeing them up from creating users and adding them into groups and allowing them to focus on higher-value activities.

Once configured, the user can:
1. Scan a QR code or navigate to a pre-specified URL
2. Sign in with their ArcGIS credentials (or choose to create a new account, if enabled)
3. Be automatically added to a pre-specified group, providing permissions to access the resource
4. Be redirected to the pre-specified app or URL.

If configured, the app can also allow users to sign up for their own ArcGIS Online account within the Organisation
who have deployed the app. Each QR code can be configured with a different default User Type and Role, meaning that
the app owner can configure what permissions will be applied when users create their own accounts.

Multiple QR codes can be active at the same time, meaning that the app owner can provide different URLs/QR Codes to 
different groups of people depending on their access requirements. Disabling a QR code from future use is as simple as 
removing a record from an ArcGIS Hosted Feature Layer.

The sign-in process works whether the user is in the same ArcGIS Online Organisation or a different ArcGIS Online Organisation
as the deployed App.

## Setup

1. Fork this repo into Github, Azure Devops or another git repository hosting service

### Azure Static Web App

First, we will create the Static Web App (the website which users will use for the self-service onboarding).

1. Go to portal.azure.com
2. Navigate to Static Web Apps and select Create. The free tier is sufficient.
3. Give your static web app a name (best practice is to reference the portal/agol you are creating it for) 
and assign it to a resource group (used to group resources together in billing reports)
4. Under Source, select the git repository you forked above
5. Under app location enter `./web`
6. Under api location enter `./api`
7. Leave output location as `.`

8. Deploy the static web app.
- Take a note of the URL in the top right of the overview page, you will use it later.

### ArcGIS

We now need to configure ArcGIS to recognise the new app, and give it the permissions to manage users on its behalf.

1. [Create an OAuth App](https://developers.arcgis.com/documentation/security-and-authentication/user-authentication/tutorials/create-oauth-credentials-user-auth/) in the ArcGIS Online Organisation or ArcGIS Enterprise portal you want to associate this app with.

> Note: No specific permissions/privileges are required.

For the redirect url, use the url to your Static Web App that you noted above and add `/callback.html` on the end. It should look like 
`https://y3r98guef.azurestaticwebsites.net/callback.html`

2. Deploy a Hosted Feature Table using the zipped file geodatabase in the repository (`config_table_template.zip`). This will be where you configure
the Group and App URL (and optionally the User Type and Role for new users) associated with each QR Code. This Hosted Feature Table must be owned by the same user as the OAuth App above.

### Github (or your chosen git repository hosting service)

We will now configure the website specifically for your ArcGIS Online Organisation or ArcGIS Enterprise Portal. 

In the index.html page there are some placeholders `__CALLBACK_URL__`, `__PORTAL_URL__` and `__CLIENT_ID__`. These need to be replaced with:
- CALLBACK_URL - as described in the ArcGIS section above
- CLIENT_ID - OAuth Client ID created in ArcGIS section above
- PORTAL_URL - this is the full URL to your Portal i.e. https://www.arcgis.com or https://maps.example.com/portal

Simply open the `./web/index.html` file in the editor, find the placeholders above and replace them with the correct details.


### Azure Static Web App

Back in the Azure Static Web App, we also need to add the following environment variables into azure static web apps so that the python function has the correct information

| Variable name | Purpose |
|---------------|---------|
|CALLBACK_URL | As in the ArcGIS section above|
|CLIENT_ID | OAuth Client ID created in ArcGIS section above|
|PORTAL_URL | This is the full url i.e. https://www.arcgis.com or https://maps.example.com/portal. Don't include a forward slash at the end.|
|MGR_USER | Username of the Built-in ArcGIS user with a) permissions to create users ("Security and Infrastructure" or "Add user" privileges in their Role) and b) Group Manager or Owner of the group(s) that users will be added to. |
|MGR_PWORD | Password of above user|
|CONFIG_LAYER_ID | Item ID of the 'config' Hosted Feature Table deployed previously|

> Note: If you require the enhanced security of storing your credentials in Azure Key Vault, this is possible but will require changes to the code. You will also need to either use a premium-tier Static Web App, or separate the api into an Azure Function as integration with Key Vault is not supported in the free tier of Static Web Apps. Configuring this is outside the scope of this demonstrator app.

## Configuration

This section describes how to generate QR codes which users can scan to be onboarded into groups automatically. You will use the globalid from each row to create a separate QR code.

1. Create the group containing the content you wish to share. 

Make sure the MGR_USER specified above is a group owner or manager, and if you expect external users (from other ArcGIS Online Organisations) to use the QR code, make sure that `Members of any organization` is selected when choosing who can join the group.

2. Create a new record in the config table

- Enter the group_id (the 32-digit ID from the URL when the group is created), and the redirect_uri - the URL to be redirected to once they've signed in
- Optionally, enter the User Type and Role ID you want new users to be assigned when using the Sign Up option. Leaving these blank will disable sign-up.

> Note: You can find the correct role ID to use using the ArcGIS API for Python
    from arcgis import GIS
    gis = GIS("home")
    rolesList = gis.users.roles.all(max_roles=50)
    for role in rolesList:
      print(f"{role.name} - {role.id})

![Config table](https://github.com/hansonwj/arcgis-alternative-signin-web/blob/main/docs/config-table.png)

- Copy the globalid from the row you want to create a QR code for and add it as the "id" parameter after your Static Web App URL. The url will look like this:
  `https://<your-app>.azurestaticwebsites.net/?id=<globalid>`
- Right click the browser window and click Create QR Code.
- Send out the QR Code!

## Usage

The user will scan the QR code then select "Sign in" or "Sign up" to either provide access through their existing account, or create a new account. The Sign In workflow is shown below.

![User onboarding video](https://github.com/hansonwj/arcgis-alternative-signin-web/blob/main/docs/arcgis-user-onboarding.gif)