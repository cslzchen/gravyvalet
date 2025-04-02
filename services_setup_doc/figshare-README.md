# OSF Figshare Addon

## Setup Figshare for development

1. Download [ngrok](https://dashboard.ngrok.com/get-started/setup) (free, but signup is required)
2. GO to [domains](https://dashboard.ngrok.com/domains) page, and create a domain (you have one free domain). 
3. Replace all later occurrences of YOUR_DOMAIN with domain created here.
2. Run with `ngrok http 5000 --domain YOUR_DOMAIN`
  * this assumes you have the OSF running
4. Go to [figshare](http://figshare.com), create an account, and login
5. Click the dropdown with your name and select **Applications** and click **Create application**
6. Add https://YOUR_DOMAIN/api/v1/oauth/callback/figshare/ as the **Callback URL**
7. Open GV admin
  * Copy the *consumer_key* to **Client ID**
  * Copy the *consumer_secret* to **Client Secret**
  * COPY https://YOUR_DOMAIN/api/v1/oauth/callback/figshare/ to redirect url
