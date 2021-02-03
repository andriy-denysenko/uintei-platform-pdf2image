import os
import json

from datetime import datetime

from flask import Flask, request
from flask import render_template, flash, redirect, make_response

from PIL import Image

import tasks
from forms import SelectPdfForm

APP = Flask(__name__)
APP.config.from_object('config')

@APP.route('/',methods = ['GET','POST'])
def index(): 
    '''
    Render Home Template and Post request to Upload the image to Celery task.
    '''
    form = SelectPdfForm()

    if request.method == 'GET':
        return render_template("index.html",
            title = 'Select PDF file',
            form = form)

    if request.method == 'POST':
        f = request.files['pdf_file']
        loc_filename = os.path.join(APP.config['UPLOAD_FOLDER'],f.filename)
        f.save(loc_filename)

        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        job = tasks.process_pdf.delay(loc_filename)

        return render_template("process.html", title='PDF processing',JOBID=job.id)


@APP.route('/progress')
def progress():
    '''
    Get the progress of our task and return it using a JSON object
    '''
    jobid = request.values.get('jobid')
    if jobid:
        job = tasks.get_job(jobid)
        if job.state == 'PROGRESS':
            return json.dumps(dict(
                state=job.state,
                progress=job.result['current'],
            ))
        elif job.state == 'SUCCESS':
            return json.dumps(dict(
                state=job.state,
                progress=1.0,
            ))
    return '{}'

@APP.route('/result.pdf')
def result():
    '''
    Pull our pdf text from redis and return it
    '''
    jobid = request.values.get('jobid')
    if jobid:
        job = tasks.get_job(jobid)
        pdf_output = job.get()
        return pdf_output
    else:
        return 404




if __name__ == '__main__':
    APP.run(host='0.0.0.0')
