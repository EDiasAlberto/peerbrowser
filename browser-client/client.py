from flask import Flask, request, render_template_string, redirect, url_for
import requests
import os

TRACKER_SERVER_URL = "http://trackers.ediasalberto.com"
MEDIA_DOWNLOAD_DIR = "./media/"
app = Flask(__name__)

@app.route("/", methods=["GET"])
def network_load():
    # Simple HTML form for user input
    html_form = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>Peernet Browser</title>
        <style>
            body {
                font-family: sans-serif;
                background: #111;
                color: #eee;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }
            form {
                background: #222;
                padding: 2em;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(255, 255, 255, 0.1);
                width: 350px;
            }
            input[type=text] {
                width: 100%;
                padding: 0.6em;
                margin: 0.5em 0 1em;
                border-radius: 5px;
                border: none;
                outline: none;
            }
            input[type=submit] {
                background: #08f;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 0.6em 1em;
                cursor: pointer;
            }
            input[type=submit]:hover {
                background: #06c;
            }
        </style>
    </head>
    <body>
        <h2>Access Peernet Site</h2>
        <form action="{{ url_for('fetch_page') }}" method="get">
            <label for="site_title">Domain / Site Title:</label><br>
            <input type="text" id="site_title" name="site_title" placeholder="example.peernet" required><br>

            <label for="page_dir">Page Path (optional):</label><br>
            <input type="text" id="page_dir" name="page_dir" value="index.html"><br>

            <input type="submit" value="Fetch Page">
        </form>
    </body>
    </html>
    """
    return render_template_string(html_form)


@app.route("/get-page", methods=["GET"])
def fetch_page():
    site_title = request.args.get("site_title")
    page_dir = request.args.get("page_dir", "index.html")

    # TODO: your logic to query tracker + fetch file
    filepath = site_title + "/" + page_dir
    response = requests.get(TRACKER_SERVER_URL + f"/peers?filename={filepath}")
    print(response)
    return f"<h3>Fetching <code>{page_dir}</code> from <code>{site_title}</code>...</h3>"

def post_site_pages(project_name: str):
    existing_pages = []
    for path, subdirs, files in os.walk(f"{MEDIA_DOWNLOAD_DIR}{project_name}"):
        for name in files:
            filepath = os.path.join(path, name).replace(MEDIA_DOWNLOAD_DIR, "")
            response = requests.get(TRACKER_SERVER_URL + f"/peers?filename={filepath}")
            if len(response.json()["peers"]) > 0:
                existing_pages.append(filepath)
                continue
            response = requests.post(TRACKER_SERVER_URL + f"/add?filename={filepath}")

    return existing_pages 

@app.route("/publish", methods=["GET", "POST"])
def publish():
    if request.method == "GET":
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Publish to Peernet</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 60px auto;
                    padding: 20px;
                    background: #fafafa;
                    border-radius: 10px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }
                h1 { text-align: center; }
                h3 { color: #555; font-weight: normal; }
                label { display: block; margin-top: 15px; font-weight: bold; }
                input[type=text] {
                    width: 100%;
                    padding: 10px;
                    margin-top: 5px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
                input[type=submit] {
                    margin-top: 20px;
                    background-color: #0066cc;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                }
                input[type=submit]:hover {
                    background-color: #004d99;
                }
            </style>
        </head>
        <body>
            <h1>Publish a Website to Peernet</h1>
            <h3>Your local files will be fetched from <code>./media/{websiteName}/</code> (HTML, CSS, JS)</h3>
            
            <form action="/publish" method="POST">
                <label for="websiteName">Website Name:</label>
                <input type="text" id="websiteName" name="websiteName" placeholder="e.g. mycoolsite" required>
                
                <label for="startPage">Start Page (optional):</label>
                <input type="text" id="startPage" name="startPage" placeholder="index.html" value="index.html">
                
                <input type="submit" value="Publish">
            </form>
        </body>
        </html>
        """

    elif request.method == "POST":
        website_name = request.form.get("websiteName")
        start_page = request.form.get("startPage", "index.html")
        # TODO: Implement logic to register or publish the site to the peernet
        # TODO: Sanitise user directory input. Furthermore, generate hashes

        startpage_path = f"{website_name}/{start_page}"
        existing_pages = post_site_pages(website_name)


        outputText = f"<p>Publishing site <b>{website_name}</b> with start page <b>{start_page}</b>...</p>"
        if len(existing_pages) > 0:
            outputText += f"<p>ERROR: These sites already existed: {existing_pages}</p>"
        return outputText
if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
