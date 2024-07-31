from flask import Flask, render_template, request, redirect, url_for, abort
from flask_basicauth import BasicAuth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io
import os
import pymysql
import pymysql.cursors
import re
from dotenv import load_dotenv

# ADD ENVIRONMENT PATH
env_path = "<env path>"
load_dotenv(env_path)

folder_name = os.getenv("FOLDER_NAME")

app = Flask(__name__)

# SET UP AUTH FOR ADMIN
app.config["BASIC_AUTH_USERNAME"] = os.getenv("ADMIN_NAME")
app.config["BASIC_AUTH_PASSWORD"] = os.getenv("ADMIN_PASSWORD")
app.config["BASIC_AUTH_FORCE"] = False  # We only want to force auth on specific routes
basic_auth = BasicAuth(app)

# SET UP GOOGLE DRIVE CREDENTIALS
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=credentials)

# SET UP DATABASE
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME"),
    "cursorclass": pymysql.cursors.DictCursor,
}


def get_db_connection():
    return pymysql.connect(**db_config)


# GET FOLDER_ID
results = (
    drive_service.files()
    .list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false",
        spaces="drive",
        fields="files(id, name)",
    )
    .execute()
)
items = results.get("files", [])
if not items:
    print(f"No folders found with name: {folder_name}")
    exit()
elif len(items) > 1:
    print(f"Multiple folders found with name: {folder_name}. Using the first one.")
folder_id = items[0]["id"]


# FETCH FILE CONTENT FROM GOOGLE DRIVE
def fetch_file_content(file_name):
    try:
        # Search for the file in the shared folder
        query = f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
        results = (
            drive_service.files()
            .list(q=query, fields="files(id, name, mimeType)")
            .execute()
        )
        items = results.get("files", [])

        if not items:
            print(f"File '{file_name}' not found in the specified folder.")
            return None

        file = items[0]
        file_id = file["id"]
        mime_type = file["mimeType"]

        print(f"Found file: {file['name']} (ID: {file_id}, Type: {mime_type})")

        if mime_type == "application/vnd.google-apps.document":
            # If it's a Google Doc, export it as HTML
            request = drive_service.files().export_media(
                fileId=file_id, mimeType="text/html"
            )
        else:
            return None

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")

        html_content = fh.getvalue().decode("utf-8")
        return process_html(html_content)

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


# GET FILE CONTENT FROM DATABASE
def get_file_content(post_name):
    conn = get_db_connection()
    cursor = conn.cursor()

    selstr = "SELECT content FROM bp WHERE post_name = %s;"
    cursor.execute(selstr, (post_name,))
    result = cursor.fetchone()

    conn.commit()
    conn.close()

    return result["content"] if result else abort(404)


# INDEX.HTML ROUTE
@app.route("/")
def index():
    content = get_file_content("index")
    if content:
        return render_template(
            "base.html", title=f"{folder_name} - Home", content=content
        )
    else:
        abort(404)


# OTHER POSTS ROUTE
@app.route("/<post_name>")
def post(post_name):
    content = get_file_content(post_name)
    name_without_extension = os.path.splitext(post_name)[0]
    words = name_without_extension.replace('-', ' ').split()
    formatted_title = ' '.join(word.capitalize() for word in words)
    if formatted_title == "index":
        formatted_title = "Home"
    if content:
        return render_template(
            "base.html", title=f"{folder_name} - {formatted_title}", content=content
        )
    else:
        abort(404)

def process_glink(html_content):
    start_tag = "&lt;glink&gt;"
    end_tag = "&lt;/glink&gt;"
    start_index = html_content.find(start_tag) + len(start_tag)
    end_index = html_content.find(end_tag)
    if end_index == -1:
        return ""
    if start_index > len(start_tag) - 1 and end_index > -1:
        glink_content = html_content[start_index:end_index].strip()
        first_amp = glink_content.find("&nbsp")
        last_semi = glink_content.rfind(";")
        if first_amp > -1 and last_semi > -1:
            path = glink_content[:first_amp]
            clean_path = re.sub(r"<[^>]*>", "", path)
            name = glink_content[first_amp:]
            name = re.sub(r"<[^>]*>", "", name)
            last_semi = name.rfind(";")
            clean_name = name[last_semi + 1:]
            replacement = f'<a href="{clean_path}">{clean_name}</a>'
            return (
                html_content[: start_index - len(start_tag)]
                + replacement
                + html_content[end_index + len(end_tag) :]
            )

    return html_content

def process_html(html_content):
    while True:
        if (
            html_content.find("&lt;glink&gt;") == -1
        ):
            break
        if html_content.find("&lt;glink&gt;") != -1:
            html_content = process_glink(html_content)
    return html_content

# Fetch all files from the Google Drive folder
def get_all_files_from_drive():
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        spaces="drive",
        fields="files(id, name, mimeType, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()
    return results.get('files', [])

# Modify the admin route
@app.route("/admin", methods=["GET", "POST"])
@basic_auth.required
def admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all files from Google Drive
    drive_files = get_all_files_from_drive()
    
    # Fetch all posts from the database
    cursor.execute("SELECT post_name FROM bp;")
    db_posts = {row['post_name'] for row in cursor.fetchall()}
    
    # Combine information
    files_info = []
    for file in drive_files:
        if file['mimeType'] == 'application/vnd.google-apps.document':
            files_info.append({
                'name': file['name'],
                'active': file['name'] in db_posts,
                'in_drive': True
            })
    
    # Add files that are in the database but not in Google Drive
    orphaned_files = []
    for post_name in db_posts:
        if post_name not in [file['name'] for file in files_info]:
            orphaned_files.append({
                'name': post_name,
                'active': True,
                'in_drive': False
            })

    if request.method == "POST":
        post_name = request.form.get("post_name")
        action = request.form.get("action")
        
        if action == "activate":
            content = fetch_file_content(post_name)
            if content is not None:
                insstr = """
                    INSERT INTO bp (post_name, content)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE
                        content = VALUES(content);
                """
                cursor.execute(insstr, (post_name, content))
                conn.commit()
        elif action == "deactivate":
            cursor.execute("DELETE FROM bp WHERE post_name = %s;", (post_name,))
            conn.commit()
        elif action == "delete":
            cursor.execute("DELETE FROM bp WHERE post_name = %s;", (post_name,))
            conn.commit()
        elif action == "refresh":
            content = fetch_file_content(post_name)
            if content is not None:
                cursor.execute("UPDATE bp SET content = %s WHERE post_name = %s;", (content, post_name))
                conn.commit()
        elif action == "delete_all_orphaned":
            drive_file_names = [file['name'] for file in drive_files if file['mimeType'] == 'application/vnd.google-apps.document']
            cursor.execute("DELETE FROM bp WHERE post_name NOT IN %s;", (drive_file_names,))
            conn.commit()
        
        conn.close()
        return redirect(url_for("admin"))

    conn.close()
    return render_template("admin.html", title=f"{folder_name} - Admin", files=files_info, orphaned_files=orphaned_files)

if __name__ == "__main__":
    app.run(debug=True)