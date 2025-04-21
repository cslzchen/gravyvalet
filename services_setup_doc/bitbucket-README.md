# OSF Bitbucket Addon

## Enabling the addon for development


### Setup Bitbucket
1. On your Bitbucket user settings, go to "Access Management" -> "OAuth" -> "Add consumer"
2. Enter any name for the application name, e.g. "OSF Bitbucket Addon (local)"
3. In the Callback URL field, enter `http://localhost:5000/oauth/callback/bitbucket/`
4. In the URL field, enter `http://localhost:5000/`
5. For Permissions, select:
 * Account: Email, Read
 * Team Memberships: Read
 * Projects: Read
 * Repositories: Read
5. Submit the form.
6. Click on your new consumer to show the secret and key, , which you'll need to input into GV admin.
