from flask import Flask, render_template_string, request, redirect
import json
import os

DATA_FILE = "data/results.json"
def load_data():
    # read the json file, return the dict. if anything is wrong, return empty structure
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
       return {"exams": []}


def save_data(data):
    # write the dict back to the json file
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2) 
app = Flask(__name__)


homehtml = """
<h1>Exam Strategy Studio</h1>
<h2>Add a question</h2>
<form action="/api/add_question" method="post">
  <p>Question:<br><textarea name="question_text" rows="3" cols="40"></textarea></p>
  <p>Marks obtained: <input type="number" name="marks_obtained"></p>
  <p>Total marks: <input type="number" name="total_marks"></p>
  <p><button type="submit">Save question</button></p>
</form>
"""


@app.route("/")
def home():
    return render_template_string(homehtml)

@app.route("/api/add_question", methods=["POST"])
def add_question():
        data = load_data()
        entry = {
                    "question_text": request.form.get("question_text", ""),
                            "marks_obtained": request.form.get("marks_obtained", "0"),
                                    "total_marks": request.form.get("total_marks", "0"),
        }
        data["exams"].append(entry)
        save_data(data)
        return redirect("/")

if __name__ == "__main__":
    app.run(debug=True, port=5001)