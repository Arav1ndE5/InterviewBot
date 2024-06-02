from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import google.generativeai as genai
import os
import random

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/'

# Set a secret key for session management
x = random.choice([2, 1, 2, 2, 1, 1, 2, 1])
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecretkey')
gemini_api = os.getenv(f'GOOGLE_API_KEY{x}')

# Configure the API key
genai.configure(api_key=gemini_api)

# Set up the model configuration
generation_config = {
    "temperature": 0.9,
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

            # Generate content from the resume
            prompt_parts = [
                "List all the data that you observe from the resume",
                "resume: ",
                genai.upload_file(resume_path)
            ]
            response = model.generate_content(prompt_parts)
            session['resume_data'] = response.text

            return redirect(url_for('interview'))
    return render_template("upload.html")

@app.route('/interview')
def interview():
    return render_template('interview.html')


@app.route('/start-interview', methods=['POST'])
def start_interview():
    shortened_jd = session.get('shortened_jd')
    resume_data = session.get('resume_data')

    chat = model.start_chat(history=[])

    response = chat.send_message(f"""
        You are given my job description that is enclosed within '//':
        //{shortened_jd}//

        and my resume enclosed within '<>':
        <{resume_data}>

        Act as a technical interviewer for me based on the resume and job description once the candidate greets you.

        The interviewer should adapt the questions and delve deeper based on the candidate's responses and the specific requirements of the role.
        Candidate's questions are enclosed within '()'. The interviewer should not stray into topics that are not part of the interview. Also should not provide feedbacks or tips to the candidate on how to improve the interview. Don't generate content for candidate.
        """)
    interview={}
    if request.method == 'POST':
        data = request.get_json()
        if data and 'user_input' in data:
            user_input = data['user_input']
            interview["candidate"] = user_input
    
            if user_input.lower() == 'ends the interview':
                response = chat.send_message(f'''
                                            Analyze the interview given inside'<>'.
                                            <{interview}>
                                            now assess the candidate's soft skills like communication, problem-solving, attitude and teamwork and return the interview performance of the candidate on a score out of 100 based on the user messages after the start of the interview.
                                            make output in html such that they look good under a <h2> tag
                                            ''')
                response_str=response.text.strip().replace('**','').replace('. *','<br>')
                session['interview_result'] = response_str
                return jsonify({'redirect': url_for('result')})
            else:
                response = chat.send_message(f'({user_input})')
                response_str = response.text.strip().replace('"', "").replace("*", "").replace("`", "").replace(">", "").replace("Interviewer:", "")
                interview["Interviewer"] = response_str
                return jsonify({'message': response_str})
        else:
            return jsonify({'error': 'Invalid request data'})
    else:
        return jsonify({'error': 'Method not allowed'})


@app.route('/result')
def result():
    job_description = session.get('job_description')
    resume_data = session.get('resume_data')

    if job_description and resume_data:
        resume_data = session['resume_data']
        shortened_jd = session['shortened_jd']
        interview_evaluation = session.get('interview_result', 'No interview evaluation available.')

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


        make output in html such that they look good under a <h2> tag
        """

        response = model.generate_content([resume_scoring_prompt])
        response_str=response.text.strip().replace('**','').replace('. *','<br>')
        resume_score_evaluation = response_str

        return render_template('result.html', resume_score_evaluation=resume_score_evaluation, interview_evaluation=interview_evaluation)
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
