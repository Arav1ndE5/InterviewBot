from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import google.generativeai as genai
import os
import random
# import cv2
import shutil
import markdown
from dotenv import load_dotenv
import fitz

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "/tmp/uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Set a secret key for session management
x = random.choice([2, 1, 3, 2, 1, 3, 2, 1, 3])
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
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
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
        session['job_title'] = request.form['jobtitle']
        session['job_description'] = request.form['job']

        # Shorten job description
        job_description = session.get('job_description')
        if job_description:
            shorten_jd_prompt = [
                f"""Make the job description given inside '//' into short and contains most meaningful parts such as experience, responsibilities, skills required and such
                /{job_description}/
                if no meaning full job description is given return just the word 'None'
                """
            ]
            response = model.generate_content(shorten_jd_prompt)
            session['shortened_jd'] = response.text
        else:
            session['shortened_jd'] = "None"

        return redirect(url_for('upload'))

    return render_template("job.html")

def convert_pdf_to_images(pdf_path, output_path):
    
    try:
        pdf_document = fitz.open(pdf_path)
        # images = []
        # for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(0)
        pix = page.get_pixmap()
        img_path = os.path.join(output_path, f"resume.png")
        pix.save(img_path)
            # images.append(cv2.imread(img_path))

        pdf_document.close()

        # if len(images) > 1:
        #     resume_image = cv2.hconcat(images)
        #     concatenated_image_path = os.path.join(output_path, "concatenated_resume.jpg")
        #     cv2.imwrite(concatenated_image_path, resume_image)
        #     return concatenated_image_path
        # else:
        #     return img_path if images else None

        return img_path if img_path else None

    except Exception as e:
        print(f"Error during PDF conversion: {e}")
        return None

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
                # Convert PDF to images using the new function
                output_path = app.config['UPLOAD_FOLDER']
                resume_path = convert_pdf_to_images(resume_path, output_path)
                
                # Check if the conversion was successful
                if not resume_path:
                    return "Conversion failed or no output generated.", 500

            # Generate content from the resume
            print(resume_path)
            prompt_parts = [
                "List all the data that you observe from the resume",
                "resume: ",
                genai.upload_file(resume_path)
            ]
            try:
                response = model.generate_content(prompt_parts)
                session['resume_data'] = response.text
            except Exception as e:
                print(f"API call failed: {e}")
                return "API call failed", 500

            # Clean up the uploaded files
            try:
                for file in os.listdir(app.config['UPLOAD_FOLDER']):
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')
        
        else:
            session['resume_data'] = 'None'

        return redirect(url_for('interview'))
    return render_template("upload.html")

@app.route('/interview')
def interview():
    return render_template('interview.html')

@app.route('/start-interview', methods=['GET', 'POST'])
def start_interview():
    shortened_jd = session.get('shortened_jd')
    resume_data = session.get('resume_data')
    job_title = session.get('job_title')
    

    chat = model.start_chat(history=[])
    # Initial question setup for GET request
    if shortened_jd == 'None' and resume_data == 'None':
        print('No JD and Resume')
        response = chat.send_message(f"""
            Your name is Theo. You are an Interviewer that helps candidates to prepare for interviews.
            Interview is for the post of {job_title}..
            Once the candidate greets you introduce yourself and start the interview. Interview should have techncial round and HR round. 
            points to remember and breaking them is strictly prohibited:
            1. The interviewer should adapt the questions and delve deeper based on the candidate's responses and the specific requirements of the role.
            2. The interviewer should not answer topics that are not part of the interview. Also should not provide feedbacks or tips to the candidate on how to improve the interview. 
            3. Candidate's questions are enclosed within '()'. Don't take into account other special characters in the candidate's questions.
            4. If interview has ended return "Click end interview to get result.". Don't return anything else. 
            5. Don't answers in behalf of the candidate and wait for the candidates response.
            6. If the candidate replies 'ok' when asked a question, prompt the candidate to go on and complete his/her answer.
            """)
    elif shortened_jd == 'None' and resume_data != 'None':
        print('No JD')
        response = chat.send_message(f"""
            Your name is Theo. You are an Interviewer that helps candidates to prepare for interviews.
            Interview is for the post of {job_title}.
            and my resume enclosed within '<>':
            <{resume_data}>
            based on the resume and job title once the candidate greets you introduce yourself and start the interview. Interview should have techncial round and HR round. 
            points to remember and breaking them is strictly prohibited:
            1. The interviewer should adapt the questions and delve deeper based on the candidate's responses and the specific requirements of the role.
            2. The interviewer should not answer topics that are not part of the interview. Also should not provide feedbacks or tips to the candidate on how to improve the interview. 
            3. Candidate's questions are enclosed within '()'. Don't take into account other special characters in the candidate's questions.
            4. If interview has ended return "Click end interview to get result.". Don't return anything else. 
            5. Don't answers in behalf of the candidate and wait for the candidates response.
            6. If the candidate replies 'ok' when asked a question, prompt the candidate to go on and complete his/her answer.
            """)
    elif shortened_jd != 'None' and resume_data == 'None':
        print('No Resume')
        response = chat.send_message(f"""
            Your name is Theo. You are an Interviewer that helps candidates to prepare for interviews.
            Interview is for the post of {job_title}.
            You are given my job description that is enclosed within '//':
            //{job_title}:{shortened_jd}//
            based on the job description once the candidate greets you introduce yourself and start the interview. Interview should have techncial round and HR round. 
            points to remember and breaking them is strictly prohibited:
            1. The interviewer should adapt the questions and delve deeper based on the candidate's responses and the specific requirements of the role.
            2. The interviewer should not answer topics that are not part of the interview. Also should not provide feedbacks or tips to the candidate on how to improve the interview. 
            3. Candidate's questions are enclosed within '()'. Don't take into account other special characters in the candidate's questions.
            4. If interview has ended return "Click end interview to get result.". Don't return anything else. 
            5. Don't answers in behalf of the candidate and wait for the candidates response.
            6. If the candidate replies 'ok' when asked a question, prompt the candidate to go on and complete his/her answer.
            """)
    else:
        print('Jd and Resume found')
        response = chat.send_message(f"""
            Your name is Theo. You are an Interviewer that helps candidates to prepare for interviews.
            Interview is for the post of {job_title}.
            You are given my job description that is enclosed within '//':
            //{job_title}:{shortened_jd}//
            and my resume enclosed within '<>':
            <{resume_data}>
            based on the job description and my resume, once the candidate greets you introduce yourself and start the interview. Interview should have techncial round and HR round. 
            points to remember and breaking them is strictly prohibited:
            1. The interviewer should adapt the questions and delve deeper based on the candidate's responses and the specific requirements of the role.
            2. The interviewer should not answer topics that are not part of the interview. Also should not provide feedbacks or tips to the candidate on how to improve the interview. 
            3. Candidate's questions are enclosed within '()'. Don't take into account other special characters in the candidate's questions.
            4. If interview has ended return "Click end interview to get result.". Don't return anything else. 
            5. Don't answers in behalf of the candidate and wait for the candidates response.
            6. If the candidate replies 'ok' when asked a question, prompt the candidate to go on and complete his/her answer.
            """)

    # initial_question = response.text.strip().replace('"', "").replace("*", "").replace("`", "").replace(">", "").replace("Interviewer:", "")

    if request.method == 'POST':
        data = request.get_json()
        if data:
            user_input = data.get('user_input')
            get_result = data.get('get_result')
            print(get_result)
            print(user_input)

            
            # Initialize the interview dictionary with lists for candidate and interviewer responses
            if 'interview' not in session:
                session['interview'] = "interviewer: Let's Start the interview"
            interview = session['interview']

            response_str=''
            print(interview)
            print(response_str)

            
            if user_input:
                # interview["candidate"].append(user_input)
                interview += f", candidate: {user_input}"
                response = chat.send_message(f'({user_input})')
                response_str = response.text.strip().replace('"', "").replace("*", "").replace("`", "").replace(">", "").replace("Interviewer:", "").replace("Theo:", "")
                interview += f", interviewer: {response_str}"
                session['interview'] = interview  # Update the session with the latest interview data
                print(response_str)
                return jsonify({'message': response_str})
            
            if get_result or response_str == "Click end interview to get result.":
                response = chat.send_message(f'''
                    Analyze the following transcript that contains interviewer's questions and candidate's responses.
                    The interview is given inside '<>'.
                    <{interview}>
                    now create assessment for the candidates technical knowledge based on the interview. Also assess the candidate's soft skills like communication, problem-solving, attitude and teamwork and return the interview performance of the candidate on a score out of 100 based on the user messages after the start of the interview.
                    if transcript isnt avilable or incomplete, return 'Please retake the interview to provide interview assessment'.
                    make output in html such that they look good under a <h2> tag
                    ''')
                # response_str = response.text.strip().replace('**', '').replace('. *', '<br>').replace('*','<br>')
                response_str = markdown.markdown(response.text)
                response_str = response.text.strip().replace('**','')
                print(response_str)
                session['interview_result'] = response_str
                session['interview'] = "interviewer: Let's Start the interview"
                return jsonify({'redirect': url_for('result')})
        else:
            return jsonify({'error': 'Invalid request data'})



@app.route('/result')
def result():
    job_title = session.get('job_title')
    candidate = session.get('candidate')
    job_description = session.get('job_description')
    resume_data = session.get('resume_data')
    interview_evaluation = session.get('interview_result', 'No interview evaluation available.')

    if job_description!='None' and resume_data!='None':
        shortened_jd = session['shortened_jd']

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
        if resume or job description is not available return "Please provide a valid resume." or "Please enter a valid Job description" without mentioning about designated tags.
        make output in html such that they look good under a <h2> tag
        """

        response = model.generate_content([resume_scoring_prompt])
        response_str = markdown.markdown(response.text)
        # response_str = response.text.strip().replace('**', '').replace('. *', '<br>').replace('*','<br>')
        response_str = response.text.strip().replace('**','')
        resume_score_evaluation = response_str

        return render_template('result.html',candidate=candidate, job_title=job_title, resume_score_evaluation=resume_score_evaluation, interview_evaluation=interview_evaluation)
    
    elif job_description=='None' and resume_data!='None':

        resume_scoring_prompt = f"""
        You are given a job title that is enclosed within '//':
        //{job_title}//
        The candidate walks in and hands you their resume enclosed within '<>':
        <{resume_data}>
        Compare both job title and resume and return the following:
        Resume score: a score out of 100 based on the requirements met by resume for the job description.
        Evaluation: how the scores are awarded.
        Strengths:
        Areas of improvement:
        Overall assessment:
        if resume or job description is not available return "Please provide a valid resume." or "Please enter a valid Job description" without mentioning about designated tags.
        make output in html such that they look good under a <h2> tag
        """

        response = model.generate_content([resume_scoring_prompt])
        response_str = markdown.markdown(response.text)
        # response_str = response.text.strip().replace('**', '').replace('. *', '<br>').replace('*','<br>')
        response_str = response.text.strip().replace('**','')
        resume_score_evaluation = response_str

        return render_template('result.html',candidate=candidate, job_title=job_title, resume_score_evaluation=resume_score_evaluation, interview_evaluation=interview_evaluation)

    else:
        return render_template('result.html',candidate=candidate, job_title=job_title, resume_score_evaluation='<h2>Resume not available<h2>', interview_evaluation=interview_evaluation)



if __name__ == '__main__':
    app.run(debug=True)