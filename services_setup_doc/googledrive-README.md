# OSF Google Drive Addon


### Important! Do not use your corporate accounts for this, use personal ones

## Enabling the addon for development
1. Go to https://console.developers.google.com
2. If you do not already have a project, create a project
3. Click on the "Google Drive API" link, and enable it
4. Click on "Credentials", and "create credentials". Select "Oath Client ID", with "web application" and set the redirect uri to `http://localhost:5000/oauth/callback/googledrive/`
5. Submit your new client ID and make a note of your new **Client ID** and **Client secret** to fill them into GV admin.
6. Add yourself as a test user and ensure the oauth app is configured securely
7. (Optional) You may find that the default 10 "QPS per User" rate limit is too restrictive. This can result in unexpected 403 "User Rate Limit Exceeded" messages. You may find it useful to request this limit be raised to 100. To do so, in the Google API console, from the dashboard of your project, click on "Google Drive API" in the list of APIs. Then click the "quotas" tab. Then click any of the pencils in the quotas table. Click the "apply for higher quota" link. Request that your "QPS per User" be raised to 100.
