# Setting up a Google Cloud Project and Service Account

1. Go to the Google Cloud Console (https://console.cloud.google.com/).

2. Create a new project:
   - Click on the project dropdown at the top of the page.
   - Click "New Project".
   - Enter a name for your project and click "Create".

3. Enable the Google Drive API:
   - In the left sidebar, go to "APIs & Services" > "Library".
   - Search for "Google Drive API" and click on it.
   - Click "Enable".

4. Create a service account:
   - In the left sidebar, go to "IAM & Admin" > "Service Accounts".
   - Click "Create Service Account" at the top of the page.
   - Enter a name for your service account and click "Create".
   - For the "Service account permissions" step, you can skip it by clicking "Continue".
   - For the "Grant users access" step, you can skip it by clicking "Done".

5. Create and download the key file:
   - In the list of service accounts, find the one you just created and click on it.
   - Go to the "Keys" tab.
   - Click "Add Key" > "Create new key".
   - Choose "JSON" as the key type and click "Create".
   - The key file will be automatically downloaded to your computer. Keep this file safe and secure.

6. Share your Google Drive folder:
   - Go to your Google Drive and right-click on the folder you want to use for your blog.
   - Click "Share".
   - In the "Add people and groups" field, enter the email address of your service account. It should look like `your-service-account-name@your-project-id.iam.gserviceaccount.com`.
   - Choose "Editor" for the access level.
   - Click "Send".

Now you have a service account set up with the necessary credentials to access your Google Drive folder.
