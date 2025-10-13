from flask import Flask, request, render_template_string, redirect, url_for
import requests

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
    return f"<h3>Fetching <code>{page_dir}</code> from <code>{site_title}</code>...</h3>"


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
