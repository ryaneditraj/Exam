from flask import Flask, render_template_string
import json
import os

DATA_FILE = "data/results.json"
app = Flask(__name__)


@app.route("/")
def home():
 # super simple first page just to check Flask works
    return render_template_string("<h1>Exam Strategy Studio</h1><p>It works!</p>")


if __name__ == "__main__":
    app.run(debug=True)