# OSF OneDrive Addon

### Register the addon with Microsoft at: https://portal.azure.com/#home


1. Search or click "App registrations"
2. Click "+ New registration"
    1. Name: COS OneDrive App
    2. Supported account types:
         Accounts in any organizational directory (Any Azure AD directory - Multitenant) and personal Microsoft accounts (e.g. Skype, Xbox)
    3. Redirect URI (optional)
         http://localhost:5000/oauth/callback/onedrive/
3. sent to new application registration page
     1. "Note Application (client) ID", to fill it into GV admin
4. Click on "Certificates & secrets"
     1. Click "+ New client secret"
     2. Choose term limits
     3. Save
     4. Copy "Value" of new secret. to fill it into GV admin 
5. Click on "API permissions"
6. Click "+ Add a permission"
     1. Select "Microsoft Graph"
     2. Select "Delegated Permission"
     3. "User.Read" is selected by default.  Add "offline_access", "Files.Read",
          "Files.Read.All", "Files.ReadWrite"w
