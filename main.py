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

# SET FOLDER NAME
folder_name = "<folder name>"

app = Flask(__name__)

# SET UP AUTH FOR ADMIN
app.config["BASIC_AUTH_USERNAME"] = "<admin username>"
app.config["BASIC_AUTH_PASSWORD"] = "<admin password>"
app.config["BASIC_AUTH_FORCE"] = False  # We only want to force auth on specific routes
basic_auth = BasicAuth(app)

# SET UP GOOGLE DRIVE CREDENTIALS
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_ACCOUNT_FILE = "<path to service account key json>"
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=credentials)

# SET UP DATABASE
db_config = {
    "host": "<database host>",
    "user": "<database user>",
    "password": "<database password>",
    "db": "<database name>",
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
    content = get_file_content("index.html")
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


# ADMIN ROUTE
@app.route("/admin", methods=["GET", "POST"])
@basic_auth.required  # This decorator enforces basic authentication
def admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, post_name FROM bp;")
    posts = cursor.fetchall()
    conn.close()

    if request.method == "POST":
        if request.form.get("action") == "Delete":
            post_ids = request.form.getlist("post_ids")
            conn = get_db_connection()
            cursor = conn.cursor()
            for post_id in post_ids:
                cursor.execute("DELETE FROM bp WHERE id = %s;", (post_id,))
            conn.commit()
            conn.close()
            return redirect(url_for("admin"))

    return render_template("admin.html", title=f"{folder_name} - Admin", posts=posts)


# ADMIN UPDATE API
@app.route("/admin/update", methods=["POST"])
def update_posts():
    post_names = request.form.getlist("post_names")
    csv_post_names = request.form.get("csv_post_names", "")

    # Add post names from CSV input
    if csv_post_names:
        post_names.extend([name.strip() for name in csv_post_names.split(",")])

    conn = get_db_connection()
    cursor = conn.cursor()

    for post_name in post_names:
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
    conn.close()

    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run()
