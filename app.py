from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import google.generativeai as genai
import os
import random
from pdf2jpg import pdf2jpg
import cv2
import shutil


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

@app.before_request
def clear_session():
    session.clear()

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/job', methods=['GET', 'POST'])
def job():
    if request.method == 'POST':
        session['job_title'] = request.form['jobtitle']
        session['job_description'] = request.form['job']

        # Shorten job description
        job_description = session.get('job_description')
        shorten_jd_prompt = [
            f"""Make the job description given inside '//' into short and contains most meaningful parts such as experience, responsibilities
            /{job_description}/
            """
        ]
        response = model.generate_content(shorten_jd_prompt)
        session['shortened_jd'] = response.text
        return redirect(url_for('upload'))

    return render_template("job.html")

@app.route('/upload', methods=['GET', 'POST'])
def upload():
 
    if request.method == 'POST':
        session['candidate'] = request.form['candidate']
        resume_file = request.files['resume']
        # Save the uploaded file to the resources folder
        if resume_file:
            filename = resume_file.filename
            resume_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume_file.save(resume_path)

            # Check if the file is a PDF
            if filename.lower().endswith('.pdf'):
                # Convert PDF to images using pdf2jpg
                output_path = os.path.join(app.config['UPLOAD_FOLDER'])
                result = pdf2jpg.convert_pdf2jpg(resume_path, output_path, pages="ALL", dpi=200)

                # Check if the result is as expected
                if not isinstance(result, list) or not result:
                    print("Conversion failed or no output generated.")
                else:

                    # Concatenate images horizontally if there are images to concatenate
                    if len(result[0]['output_jpgfiles'])>1:
                        # Extract the list of generated image files
                        images = []
                        for img in result[0]['output_jpgfiles']:
                            images.append(cv2.imread(img))
                        resume_image = cv2.hconcat(images)
                        concatenated_image_path = os.path.join(output_path, "concatenated_resume.jpg")
                        cv2.imwrite(concatenated_image_path, resume_image)
                        print(f"Concatenated image saved at: {concatenated_image_path}")
                        resume_path = concatenated_image_path  # Use the concatenated image path for processing
                    else:
                        resume_path=result[0]['output_jpgfiles'][0]
                        print(result)
                        print(result[0]['output_jpgfiles'][0])

            # Generate content from the resume
            print(resume_path)
            prompt_parts = [
                "List all the data that you observe from the resume",
                "resume: ",
                genai.upload_file(resume_path)
            ]
            response = model.generate_content(prompt_parts)
            session['resume_data'] = response.text
            
             # Clean up the uploaded files
            for file in os.listdir(app.config['UPLOAD_FOLDER']):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'Failed to delete {file_path}. Reason: {e}')

        return redirect(url_for('interview'))
    return render_template("upload.html")


@app.route('/interview')
def interview():
    return render_template('interview.html')


@app.route('/start-interview', methods=['GET', 'POST'])
def start_interview():
    shortened_jd = session.get('shortened_jd')
    resume_data = session.get('resume_data')

    chat = model.start_chat(history=[])
    # Initial question setup for GET request
    response = chat.send_message(f"""
        You are given my job description that is enclosed within '//':
        //{shortened_jd}//

        and my resume enclosed within '<>':
        <{resume_data}>

        Act as a technical interviewer for me based on the resume and job description once the candidate greets you.
        points to remember and breaking them is prohibited:
        1. The interviewer should adapt the questions and delve deeper based on the candidate's responses and the specific requirements of the role.
        2. The interviewer should not stray into topics that are not part of the interview. Also should not provide feedbacks or tips to the candidate on how to improve the interview. Don't answers in behalf of the candidate and wait for the candidates response.
        3. Candidate's questions are enclosed within '()'.
        4. If interview has ended return "Click end interview to get result". Don't return anything else. 
        """)
    # initial_question = response.text.strip().replace('"', "").replace("*", "").replace("`", "").replace(">", "").replace("Interviewer:", "")

    if request.method == 'POST':
        data = request.get_json()
        if data:
            user_input = data.get('user_input')
            get_result = data.get('get_result')
            print(get_result)
            print(user_input)

            #add message number:
            message = 1
            # Initialize the interview dictionary with lists for candidate and interviewer responses
            if 'interview' not in session:
                session['interview'] = {"candidate": [], "interviewer": []}
            interview = session['interview']
            print(interview)
            print(interview['interviewer'][-1])


            if get_result or interview['interviewer'][-1] == "Click end interview to get result":
                response = chat.send_message(f'''
                    Analyze the interview given inside '<>'.
                    <{interview}>
                    now assess the candidate's soft skills like communication, problem-solving, attitude and teamwork and return the interview performance of the candidate on a score out of 100 based on the user messages after the start of the interview.
                    make output in html such that they look good under a <h2> tag
                ''')
                response_str = response.text.strip().replace('**', '').replace('. *', '<br>')
                print(response_str)
                session['interview_result'] = response_str

                return jsonify({'redirect': url_for('result')})
            
            if user_input:
                interview["candidate"].append(user_input)
                response = chat.send_message(f'({user_input})')
                response_str = response.text.strip().replace('"', "").replace("*", "").replace("`", "").replace(">", "").replace("Interviewer:", "")
                interview["interviewer"].append(response_str)
                session['interview'] = interview  # Update the session with the latest interview data
                print(response_str)
                return jsonify({'message': response_str})
            
        else:
            return jsonify({'error': 'Invalid request data'})



@app.route('/result')
def result():
    job_title = session.get('job_title')
    candidate = session.get('candidate')
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
        response_str = response.text.strip().replace('**', '').replace('. *', '<br>')
        resume_score_evaluation = response_str

        return render_template('result.html',candidate=candidate, job_title=job_title, resume_score_evaluation=resume_score_evaluation, interview_evaluation=interview_evaluation)
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
