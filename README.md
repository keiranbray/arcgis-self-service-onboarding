# arcgis-alternative-signin-web

This app allows ArcGIS administrators and power users to create QR codes which, when scanned,
add a user to a group and automatically redirects the user to a specified app.

If configured, it also allows users to sign up for an account in the configured organisation.

## Setup

1. Fork this repo into Github, Azure Devops or another git repository hosting service

### Azure static web app

- Go to portal.azure.com
- Go to static web apps and Create
- Give your static web app a name (reference the portal/agol you are creating it for) 
and assign it to a resource group (used to group resources together in billing reports)
- Under Source, select the github repo you forked above
- Under app location enter `./web`
- Under api location enter `./api`
- Leave output location as `.`

- Deploy the static web app.
- Note the URL in the top right of the overview page, you will use it later

### ArcGIS

1. Create an oauth app in the portal/agol you want to associate this app with - follow these steps
https://developers.arcgis.com/documentation/security-and-authentication/user-authentication/tutorials/create-oauth-credentials-user-auth/
No specific permissions are required.
For the redirect url, get the url to your static web app (as deployed above) and add `/callback.html` on the end.

2. Deploy a hosted feature table using the zipped file geodatabase in the repo. This will be the config table used to define the QR codes.


### Github (or other hosting service)

In the index.html page there are some placeholders ``__CALLBACK_URL__`, `__PORTAL_URL__` and `__CLIENT_ID__`. You can either manually replace these or setup the 
Github actions to replace them for you based on repository-level environment variables you set.

If you decide to include the string replacement in your pipeline build, Set up environment variables for your repo. For `Github` the workflow is as follows:
Under Settings > Secrets and variables > Actions, create an environment (I named mine "prod"). Create three entries under Variables:
- CALLBACK_URL - as in the arcgis section above
- CLIENT_ID - oauth client id created in arcgis section above
- PORTAL_URL - this is the full url i.e. https://www.arcgis.com or https://maps.example.com/portal

Add the following code to the yaml file under .github\workflows (see example in repo)

```
    environment: prod
    env:
      CALLBACK_URL: ${{ vars.CALLBACK_URL }} 
      CLIENT_ID: ${{ vars.CLIENT_ID }} 
      PORTAL_URL: ${{ vars.PORTAL_URL }}

    - uses: actions/checkout@v3
        with:
          submodules: true
          lfs: false

    steps:
      # 🔧 Replace placeholders in index html script
      - name: Replace CLIENT ID placeholder
        run: |
          for file in $(find web -type f -name "*.html"); do
            sed -i "s|__CLIENT_ID__|${CLIENT_ID}|g" "$file"
          done
      - name: Replace CALLBACK URL placeholder
        run: |
          for file in $(find web -type f -name "*.html"); do
            sed -i "s|__CALLBACK_URL__|${CALLBACK_URL}|g" "$file"
          done
      - name: Replace PORTAL URL placeholder
        run: |
          for file in $(find web -type f -name "*.html"); do
            sed -i "s|__PORTAL_URL__|${PORTAL_URL}|g" "$file"
          done
```

### Azure
We also need to add the following environment variables into azure static web apps

| Variable name | Purpose |
|---------------|---------|
|CALLBACK_URL | as in the arcgis section above|
|CLIENT_ID | oauth client id created in arcgis section above|
|PORTAL_URL | this is the full url i.e. https://www.arcgis.com or https://maps.example.com/portal. Don't include a forward slash at the end.|
|MGR_USER | username of user with permissions to create users ("Security and Infrastructure" or "Add user" privileges) and group manager or owner of group users will be added to |
|MGR_PWORD | password of above user|
|CONFIG_LAYER_ID | id of config table in your portal|


## Usage
- Add a row into the config table.
- Enter the group id you want users to be automatically added to, and the url they should be redirected to on sign in
- Optionally add the user type and role id that users using the create user workflow will be assigned.

- Take the globalid from the row you want to use and add it as the "id" parameter after your url. Right click the browser and click create qr code.
  `https://<your-app>.azurestaticwebsites.net/?id=<globalid>`
- Send out the qr code!
