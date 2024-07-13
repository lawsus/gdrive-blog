## Setup
1. Create google cloud project and service account according to [google-cloud-setup.md](google-cloud-setup.md).
2. Hosting on pythonanywhere.com:
    - main.py, templates/base.html, templates/admin.html
    - json for service account
    - create mysql database
3. In main.py, change folder_name to shared folder name, SERVICE_ACCOUNT_FILE to path to service account json, db_config to created mysql database credentials. Set admin account username and password.

## Database
Pythonanywhere:
- [UsingMySQL](https://help.pythonanywhere.com/pages/UsingMySQL/)

Setup db:
```
CREATE TABLE bp (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_name VARCHAR(255) NOT NULL UNIQUE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## Admin
Go to /admin to view, delete, add, and update posts.

## Cloudflare
1. Change pythonanywhere webapp name to domain name and get CNAME.
2. Go to cloudflare DNS page for the site.
3. Add CNAME record with DNS Only.

## Additional Notes
- requirements.txt may or may not be complete.
- Yes, all the python is in one file. This was an intentional choice.
- Of course I used Claude 3.5 Sonnet, shout out to Anthropic.

Issues:
- glink doesn't properly handle external links
- can't get mobile view to work well