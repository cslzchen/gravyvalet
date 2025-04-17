# OSF Github Addon

## Enabling the addon for development

### Setup up on Github

1. On your Github user settings, under "Developer settings" go to “OAuth Apps”
2. Click on "Register a new application"
2. Enter any name for the application name, e.g. "OSF Github Addon (local)"
3. In the "Homepage URL" field, enter `http://localhost:5000/`
4. In the Authorization Callback URL field, enter `http://localhost:5000/oauth/callback/github/`.
5. Submit the form.
6. Make a note of your Client ID and Client Secret, and fill them into GV admin.

## Testing webhooks (not supported by GV yet)

To test Github webhooks, your development server must be exposed to the web using a service like ngrok:
* brew install ngrok
* ngrok 5000
* Copy forwarding address to addons/github/settings/local.py:HOOK_DOMAIN
