import os
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns # Added seaborn for a different charting style
from flask import Flask, request, render_template, jsonify
import google.generativeai as genai
 
# ----------------------------
# Load environment variables
# ----------------------------
# Direct API key (⚠️ Not recommended for production)
genai.configure(api_key="AIzaSyAkoaMZMzceR1xaffziROk05iFw3jN8V00")
 
app = Flask(__name__)
uploaded_df = None
 
# ----------------------------
# Home Page
# ----------------------------
@app.route("/")
def index():
    return render_template("index.html")
 
# ----------------------------
# Upload Excel/CSV
# ----------------------------
@app.route("/upload", methods=["POST"])
def upload():
    global uploaded_df
    try:
        file = request.files["file"]
        if file.filename.endswith(".csv"):
            uploaded_df = pd.read_csv(file)
        else:
            uploaded_df = pd.read_excel(file)
        return jsonify({"status": "success", "message": "File uploaded successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"An error occurred during upload: {str(e)}"}), 500
 
 
# ----------------------------
# Ask Question
# ----------------------------
@app.route("/ask", methods=["POST"])
def ask():
    global uploaded_df
    try:
        if uploaded_df is None:
            return jsonify({"error": "No file uploaded yet!"})
 
        user_question = request.json.get("question", "")
 
        # Convert the entire dataframe to a string representation for the model
        df_string = uploaded_df.to_string(max_rows=500, max_cols=20)
 
        prompt = f"""
        You are a highly skilled and professional data analyst AI. Your primary role is to analyze the provided dataset and answer user questions accurately and concisely.
 
        Your analysis and visualization instructions:
        - Provide Python code for a high-quality visualization using `matplotlib.pyplot` or `seaborn` ONLY when a chart is explicitly requested or is the best way to represent the data (e.g., for distributions, comparisons, or trends).
        - When a chart   is generated, include a brief, one-sentence description of the chart.
        - The generated chart must be fully labeled, including a title, axis labels, and data labels (counts or percentages) where appropriate.
        - Do NOT include any Python code or data frame output in your final response to the user. The code is for internal use by the system to generate the chart.
        - The code must be self-contained and runnable, using the provided DataFrame variable `df`.
        - If the question can be answered with a simple value or text (e.g., an average, a count, or a direct greeting), provide the answer directly without any Python code.
 
        Your conversational instructions:
        - Maintain a helpful, polite, and professional tone.
        - If the user says "hi" or a similar greeting, respond with a friendly greeting like "Hi! How can I help you?".
 
        Dataset (full data):
        {df_string}
        User question: {user_question}
        """
       
        response = genai.GenerativeModel("gemini-2.5-flash").generate_content(prompt)
       
        if not hasattr(response, 'text'):
            return jsonify({"answer": "The AI model did not return a text response."})
           
        answer = response.text
 
        # Check if the response contains Python code
        if "```python" in answer:
            try:
                # Extracting the descriptive part of the answer
                code_block_start = answer.find("```python")
                description = answer[:code_block_start].strip()
 
                # Extracting the code block
                code_block_end = answer.find("```", code_block_start + 1)
               
                if code_block_start != -1 and code_block_end != -1:
                    code_block = answer[code_block_start + 9:code_block_end].strip()
                   
                    # Pre-process the code to make it compatible with the current setup
                    code_block = code_block.replace("pd.compat.StringIO", "io.StringIO")
                    code_block = code_block.replace("pd.read_csv(", "uploaded_df = ")
                    code_block = code_block.replace("pd.read_excel(", "uploaded_df = ")
                    code_block = code_block.replace("pd.DataFrame(", "uploaded_df = pd.DataFrame(")
                    code_block = code_block.replace("sns.load_dataset(", "uploaded_df = pd.DataFrame(")
                   
                    # Define the local variables that the code can use
                    exec_locals = {"uploaded_df": uploaded_df, "plt": plt, "sns": sns, "pd": pd, "io": io}
                    exec_locals['df'] = uploaded_df # Make uploaded_df available as 'df'
                   
                    # Execute the code and capture the output
                    output_stream = io.StringIO()
                    exec(code_block, {}, exec_locals)
                   
                    # If the code produced a plot, save it
                    if "plt." in code_block or "sns." in code_block:
                        buf = io.BytesIO()
                        plt.savefig(buf, format="png")
                        plt.close()
                        buf.seek(0)
                        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
                        return jsonify({"answer": description, "graph": img_base64})
                    else:
                        # If it's not a plot, capture the final result
                        result = eval(code_block.strip().split('\n')[-1], {}, exec_locals)
                        return jsonify({"answer": str(result)})
                else:
                    return jsonify({"answer": answer, "graph_error": "No valid Python code block found."})
 
            except Exception as e:
                # This handles errors specifically within the executed code
                return jsonify({"answer": answer, "graph_error": f"Failed to execute graph code: {str(e)}"}), 500
        else:
            # If no Python code block is found, return the answer directly
            return jsonify({"answer": answer})
       
    except Exception as e:
        # This handles any other unexpected server-side errors
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500
 
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)

