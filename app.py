from flask import Flask, request, render_template, redirect, url_for, session
import google.generativeai as genai
import os


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/'

# Set a secret key for session management
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecretkey')
gemini_api = os.getenv('GOOGLE_API_KEY1')


# Configure the API key
genai.configure(api_key=gemini_api)

# Set up the model configuration
generation_config = {
    "temperature": 0,
    "top_p": 0.95,
    "top_k": 32,
    "max_output_tokens": 1024,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings,
)

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/job', methods=['GET', 'POST'])
def job():
    if request.method == 'POST':
        session['job_description'] = request.form['job']

        # Shorten job description
        job_description = session.get('job_description')
        shorten_jd_prompt = [
            f"""Make the job description given inside '//'
            /{job_description}/
            into short and contains most meaningful parts such as experience, responsibilities"""
        ]
        response = model.generate_content(shorten_jd_prompt)
        session['shortened_jd'] = response.text
        return redirect(url_for('upload'))

    return render_template("job.html")

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        resume_file = request.files['resume']
        # Save the uploaded file to the resources folder
        if resume_file:
            filename = resume_file.filename
            resume_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume_file.save(resume_path)

            session['resume_path'] = resume_path
            return redirect(url_for('result'))
    return render_template("upload.html")

@app.route('/result')
def result():
    job_description = session.get('job_description')
    resume_path = session.get('resume_path')

    if job_description and resume_path:

        # Extract text from the resume
        resume_data = extract_text_from_image(resume_path)

        shortened_jd = session['shortened_jd']

        # Resume scoring
        resume_scoring_prompt = f"""
        You are given a job description that is enclosed within '//':
        //{shortened_jd}//

        The candidate walks in and hands you their resume enclosed within '<>':
        <{resume_data}>

        Compare both job description and resume and return the following:
        Resume score: a score out of 100 based on the requirements met by resume for the job description.
        Evaluation: how the scores are awarded.
        Strengths:
        Areas of improvement:
        Overall assessment:
        """

        response = model.generate_content([resume_scoring_prompt])
        resume_score_evaluation = response.text

        return render_template('result.html', resume_score_evaluation=resume_score_evaluation)
    return redirect(url_for('home'))

def extract_text_from_image(image_path):
    # Generate content from the resume
    prompt_parts = [
        "List all the data that you observe from the resume",
        "resume: ",
        genai.upload_file(image_path)
    ]
    response = model.generate_content(prompt_parts)
    resume_data = response.text
    return resume_data


if __name__ == '__main__':
    # app.run(debug=True,host='0.0.0.0')
    app.run(debug=True)
