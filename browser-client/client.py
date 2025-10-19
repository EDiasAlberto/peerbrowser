from flask import Flask, request, render_template_string, redirect, url_for
from dotenv import load_dotenv
import requests
import os
import hashlib
import time  # temporary solution

from utils import generate_hash, TRACKER_SERVER_URL, MEDIA_DOWNLOAD_DIR
from holepunch_server import UDPClient
from tracker_api import APIClient

load_dotenv()
apiClient = APIClient(base_url=TRACKER_SERVER_URL)
udpClient = UDPClient(server_host=os.getenv("MATCHMAKER_HOST"), server_port=os.getenv("MATCHMAKER_PORT"))
udpClient.start()
app = Flask(__name__)

# --- Shared nav HTML for both pages ---
NAV_HTML = """
<nav>
    <a href="{{ url_for('network_load') }}" class="nav-link">🏠 Home</a>
    <a href="{{ url_for('publish') }}" class="nav-link">📤 Publish</a>
</nav>
"""

def download_page(domain: str, page: str):
    # TODO:
    # scan file for imported css or js
    # request and download similarly
    filepath = os.path.join(domain, page)
    res = apiClient.get_peers(domain, page)
    if res:
        peers = res.json()["peers"]
        for peer in peers:
            state = udpClient.request_connect(peer)
            time.sleep(2) # temporary solution to wait until receive peer
            print("requesting file")
            udpClient.send_file_request(filepath)
            time.sleep(5) # temporary solution to delay until download complete/failed
            if os.path.isfile(os.path.join(MEDIA_DOWNLOAD_DIR, filepath)):
                hash = generate_hash(filepath)
                apiClient.add_tracker(domain, page, hash)
                break
            else:
                # peer does not work for file
                apiClient.remove_tracker(peer, domain, page)

    else:
        print("ERROR: no peers for file")


@app.route("/get-page", methods=["GET"])
def fetch_page():
    site_title = request.args.get("site_title")
    page_dir = request.args.get("page_dir", "index.html")

    if os.path.isfile(os.path.join(MEDIA_DOWNLOAD_DIR, site_title, page_dir)):
        return f"<h4>Skipped file {page_dir} of site {site_title} as it already exists locally"
    download_page(site_title, page_dir)
    response = apiClient.get_peers(site_title, page_dir)
    return f"<h3>Fetching <code>{page_dir}</code> from <code>{site_title}</code>...</h3>"

def is_malicious_filepath(filepath: str):
    has_dir_traversal = (filepath.find("..")) != -1
    attempted_root_access = (filepath.strip()[0] == "/")
    return has_dir_traversal or attempted_root_access


def post_site_pages(project_name: str):
    existing_or_malicious_pages = []
    for path, subdirs, files in os.walk(f"{MEDIA_DOWNLOAD_DIR}{project_name}"):
        for name in files:
            filepath = os.path.join(path, name)
            hash = generate_hash(filepath) 
            filepath = filepath.replace(MEDIA_DOWNLOAD_DIR, "")
            if is_malicious_filepath(filepath):
                existing_or_malicious_pages.append(filepath)
                continue
            response = apiClient.get_peers(path, name)
            if len(response.json()["peers"]) > 0:
                existing_or_malicious_pages.append(filepath)
                continue
            response = apiClient.add_tracker(path, name, hash)

    return existing_or_malicious_pages 

@app.route("/", methods=["GET"])
def network_load():
    html_form = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>Peernet Browser</title>
        <style>
            body {{
                font-family: sans-serif;
                background: #111;
                color: #eee;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                height: 100vh;
                margin: 0;
                padding-top: 60px;
            }}
            nav {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                background: #222;
                display: flex;
                justify-content: center;
                gap: 1em;
                padding: 0.8em 0;
                box-shadow: 0 2px 5px rgba(0,0,0,0.4);
                z-index: 10;
            }}
            .nav-link {{
                color: #eee;
                text-decoration: none;
                background: #333;
                padding: 0.4em 0.8em;
                border-radius: 6px;
                transition: background 0.2s;
            }}
            .nav-link:hover {{
                background: #08f;
            }}
            form {{
                background: #222;
                padding: 2em;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(255, 255, 255, 0.1);
                width: 350px;
            }}
            input[type=text] {{
                width: 100%;
                padding: 0.6em;
                margin: 0.5em 0 1em;
                border-radius: 5px;
                border: none;
                outline: none;
            }}
            input[type=submit] {{
                background: #08f;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 0.6em 1em;
                cursor: pointer;
            }}
            input[type=submit]:hover {{
                background: #06c;
            }}
        </style>
    </head>
    <body>
        {NAV_HTML}
        <h2>Access Peernet Site</h2>
        <form action="{{{{ url_for('fetch_page') }}}}" method="get">
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

@app.route("/publish", methods=["GET", "POST"])
def publish():
    if request.method == "GET":
        html_page = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Publish to Peernet</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 80px auto;
                    padding: 20px;
                    background: #fafafa;
                    border-radius: 10px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                    color: #222;
                }}
                nav {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    background: #333;
                    display: flex;
                    justify-content: center;
                    gap: 1em;
                    padding: 0.8em 0;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                    z-index: 10;
                }}
                .nav-link {{
                    color: #eee;
                    text-decoration: none;
                    background: #444;
                    padding: 0.4em 0.8em;
                    border-radius: 6px;
                    transition: background 0.2s;
                }}
                .nav-link:hover {{
                    background: #06c;
                }}
                h1 {{ text-align: center; }}
                h3 {{ color: #555; font-weight: normal; }}
                label {{ display: block; margin-top: 15px; font-weight: bold; }}
                input[type=text] {{
                    width: 100%;
                    padding: 10px;
                    margin-top: 5px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }}
                input[type=submit] {{
                    margin-top: 20px;
                    background-color: #0066cc;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                }}
                input[type=submit]:hover {{
                    background-color: #004d99;
                }}
            </style>
        </head>
        <body>
            {NAV_HTML}
            <h1>Publish a Website to Peernet</h1>
            <h3>Your local files will be fetched from <code>./media/{{{{websiteName}}}}/</code> (HTML, CSS, JS)</h3>
            
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
        return render_template_string(html_page)

    elif request.method == "POST":
        website_name = request.form.get("websiteName")
        start_page = request.form.get("startPage", "index.html")

        startpage_path = f"{website_name}/{start_page}"
        existing_pages = post_site_pages(website_name)

        outputText = f"<p>Publishing site <b>{website_name}</b> with start page <b>{start_page}</b>...</p>"
        if len(existing_pages) > 0:
            outputText += f"<p>WARN: These sites already existed (and so skipped upload): {existing_pages}</p>"
        return outputText

@app.get("/test-download")
def test_download():
    download_page("epic-site", "index.html")
    return {"status": "triggered"}

if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
