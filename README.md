# ArcGIS Self-Service Onboarding

# Overview

This repository demonstrates how to quickly set up an **Azure Static Web App** that provides a **self-service interface** for users to onboard themselves into an **ArcGIS Online** or **ArcGIS Enterprise** group.

The app helps reduce reliance on **ArcGIS Administrators** and **Group Managers** in time-critical situations. By automating user onboarding, administrators can focus on higher-value activities instead of manually creating users and managing group memberships.

Once configured, the app allows users to:

1. **Scan a QR code** or navigate to a predefined URL  
2. **Sign in** with their ArcGIS credentials (or create a new account in the deploying organisation, if enabled)  
3. **Be automatically added** to a specified group, granting them the required permissions  
4. **Be redirected** to a predefined app or URL upon completion

Multiple QR codes can be active at once, allowing the app owner to distribute different URLs or QR codes to different user groups, based on their access needs.

The sign-in process works whether the user belongs to:
- The **same ArcGIS Online organisation** as the deployed app, or  
- A **different ArcGIS Online organisation**


## Setup

1. **Fork this repository** into GitHub, Azure DevOps, or another Git repository hosting service.

### Azure Static Web App

Next, you'll create the **Azure Static Web App** — this will host the self-service onboarding website.

1. Go to [portal.azure.com](https://portal.azure.com).  
2. Navigate to **Static Web Apps** and select **Create**. The **Free** tier is sufficient.  
3. Enter a **name** for your Static Web App (best practice is to reference the ArcGIS portal or AGOL instance it supports).  
4. Assign it to a **Resource Group** (used to organise resources in billing and management).  
5. Under **Source**, select the Git repository you forked earlier.  
6. Set the following paths:
   - **App location:** `./web`  
   - **API location:** `./api`  
   - **Output location:** `.`  
7. Deploy the Static Web App.  
8. Once deployed, note the **URL** shown in the top-right of the Overview page — you’ll need it later.


### ArcGIS

Next, configure **ArcGIS** to recognise the new app and grant it permission to manage users.

1. [Create an OAuth App](https://developers.arcgis.com/documentation/security-and-authentication/user-authentication/tutorials/create-oauth-credentials-user-auth/) in the **ArcGIS Online Organisation** or **ArcGIS Enterprise portal** you want to associate with this app.  

   > ℹ️ **Note:** No special privileges or administrative permissions are required to be assigned to the OAuth Application.

   For the **Redirect URL**, use the URL of your deployed Static Web App and append `/callback.html`.  
   Example:  `https://y3r98guef.azurestaticwebsites.net/callback.html`

2. **Deploy a Hosted Feature Table** using the zipped file geodatabase in the repository (`config_table_template.zip`).  
This table will be used to define:
- The **Group ID** to add users to  
- The **App or webpage URL** users are sent to after onboarding  
- (Optional) The **User Type** and **Role** for users who select to create their own accounts  


### Github (or your chosen git repository hosting service)

You will now configure the website against your ArcGIS Online Organisation or ArcGIS Enterprise Portal. 

In the index.html page there are some placeholders `__CALLBACK_URL__`, `__PORTAL_URL__` and `__CLIENT_ID__`. These need to be replaced with:
- CALLBACK_URL - as described in the ArcGIS section above
- CLIENT_ID - OAuth Client ID created in ArcGIS section above
- PORTAL_URL - this is the full URL to your Portal i.e. https://www.arcgis.com or https://maps.example.com/portal

The most simple way is to open the `./web/index.html` file in the editor, find the placeholders above and replace them with the correct details.

> ℹ️ Note: Alternatively, if you have multiple environments, store the values as repository secrets and use Github Actions to replace the values at build-time. An example of how you can do this is available in the `.github/workflows` folder.


### Azure Static Web App

Next, return to your **Azure Static Web App** and (under Settings > Environment Variables) add the following **environment variables**.  
These values allow the backend Python function to connect to ArcGIS and manage onboarding correctly.

| Variable name | Purpose |
|----------------|----------|
| **CALLBACK_URL** | The callback URL used in the ArcGIS OAuth App (see the ArcGIS section above). |
| **CLIENT_ID** | The OAuth Client ID created in the ArcGIS section. |
| **PORTAL_URL** | The full ArcGIS portal URL, e.g. `https://www.arcgis.com` or `https://maps.example.com/portal`. *(Do not include a trailing slash.)* |
| **MGR_USER** | The username of a **built-in ArcGIS user** who has:<br>• Privileges to create users (“Security and Infrastructure” or “Add user”)<br>• Group Manager or Owner permissions for the groups users will be added to. |
| **MGR_PWORD** | The password for the user specified in `MGR_USER`. |
| **CONFIG_LAYER_ID** | The **Item ID** of the Hosted Feature Table (`config`) deployed previously. |

> ⚠️ **Note:**  Currently you must use built-in ArcGIS credentials for managing groups automatically as OAuth credentials don't provide the required scopes.

> ⚠️ **Note:**  
> For enhanced security, you can store credentials in **Azure Key Vault**.  
> However, this requires code modifications and either:
> - a **Premium-tier** Static Web App, or  
> - separating the API into an **Azure Function**, since Key Vault integration isn’t supported on the Free tier.  
>  
> Configuring this is **outside the scope** of this prototype/documentation.


## Configuration

This section describes how to generate **QR codes** that users can scan to automatically onboard themselves into ArcGIS groups.  
Each QR code is tied to a specific configuration record using the record’s **GlobalID**.

---

1. **Create the group** containing the content you wish to share.  

   Ensure the `MGR_USER` (from the environment variables) is either a **Group Owner** or **Group Manager** and has access to read the `config Hosted Feature Layer`.  
   If you expect external users (from other ArcGIS Online organisations) to join via QR code, set the group’s membership option to  
   **“Members of any organization.”**

---

2. **Add a new record** to the `config` table.  

   - Enter the **Group ID** — the 32-character ID found in the group’s URL.  
   - Enter the **Redirect URI** — the URL users should be redirected to after signing in.  
   - *(Optional)* Enter the **User Type** and **Role ID** to assign to users who sign up using the “Sign Up” option.  
     Leaving these fields blank will disable the sign-up feature.

   > 💡 **Tip:** To list available Role IDs using the ArcGIS API for Python:
   > ```python
   > from arcgis import GIS
   > gis = GIS("home")
   > roles = gis.users.roles.all(max_roles=50)
   > for role in roles:
   >     print(f"{role.name} - {role.id}")
   > ```

   ![Config table](https://github.com/hansonwj/arcgis-alternative-signin-web/blob/main/docs/config-table.png)

---

3. **Generate the QR code.**

   - Copy the **GlobalID** from the row you just added.  
   - Append it to your Static Web App’s URL as the `id` parameter:  
     ```
     https://<your-app>.azurestaticwebsites.net/?id=<globalid>
     ```
   - Open this URL in a browser, **right-click** the page, and select **“Create QR Code.”**  
   - Distribute the generated QR code to your users!


## Usage

Once everything is configured, users can simply **scan the QR code** to begin the onboarding process.

They’ll then choose between:

- **Sign in** — to use their existing ArcGIS account (or a Social Login, if configured against ArcGIS Hub Premium), or  
- **Sign up** — to create a new account (if this option has been enabled)

After signing in or signing up, the app will automatically:

1. Add them to the configured ArcGIS group  
2. Redirect them to the specified application or URL  

The example below shows the **Sign In** workflow in action:

![User onboarding video](https://github.com/hansonwj/arcgis-alternative-signin-web/blob/main/docs/arcgis-user-onboarding.gif)
