''' Tasks related to our celery functions '''

import time
import random
import datetime

from io import BytesIO
from celery import Celery, current_task
from celery.result import AsyncResult

from PIL import Image  
import os
import time

import fitz

from app import APP

CELERY = Celery('tasks',
                backend=APP.config['REDIS_URL'],
                broker=APP.config['BROKER_URL'])

CELERY.conf.accept_content = ['json', 'msgpack']
CELERY.conf.result_serializer = 'msgpack'

def get_job(job_id):
    '''
    To be called from our web app.
    The job ID is passed and the celery job is returned.
    '''
    return AsyncResult(job_id, app=CELERY)

# TODO: refactor using class which will have an 'area' field

@CELERY.task()
def process_pdf(pdf_filename):

    # Declare a variable to output the data
    log = ""

    # Open a document
    doc = fitz.open(pdf_filename)

    # TODO: Loop through pages and collect info by pages
    # Load the 1st page
    page = doc.loadPage(0)

    # Calculate total area of images on the page
    page_image_area = 0
    images = doc.get_page_images(0)
    log += 'Found {} images<br>'.format(len(images))
    for image in images:
        log += 'W: {}; H: {}; SQ: {}'.format(image[2], image[3], image[2] * image[3])
        page_image_area += image[2] * image[3]

    # Get full data with images in Python dictionary
    text_page = page.get_textpage()
    tp = text_page.extractDICT()

    # Calculate total area of text spans on the page
    text_span_area = 0
    block_image_area = 0
    text_block_area = 0
    text_line_area = 0
    page_area = tp['width'] * tp['height']

    for block in tp['blocks']:
        # If text
        log += 'Block {}: '.format(block['number'])
        if block['type'] == 0:
            log += 'Text block<br>'
            if 'image' in block:
                log += 'HAS KEY IMAGE<br>'
            bbox = block['bbox']
            text_block_area += area(bbox[0], bbox[1], bbox[2], bbox[3])
            log += 'Text block area: {}<br>'.format(area(bbox[0], bbox[1], bbox[2], bbox[3]))
            for line in block['lines']:
                bbox = line['bbox']
                text_line_area += area(bbox[0], bbox[1], bbox[2], bbox[3])
                for span in line['spans']:
                    bbox = span['bbox']
                    text_span_area += area(bbox[0], bbox[1], bbox[2], bbox[3])
        # If image
        # elif block['type'] == 1:
        # else:
        #     log += 'Image block'
        #     bbox = block['bbox']
        #     block_image_area += area(bbox[0], bbox[1], bbox[2], bbox[3])
        #     log += 'Area: {}'.format(area(bbox[0], bbox[1], bbox[2], bbox[3]))
    
    page_content = '''<h2>{}</h2>
<h3>Площадь страницы:</h3>
<p>
    {} * {} = {}
</p>
<h3>Площадь текста:</h3>
<p>
    По площади блоков: {}
</p>
<p>
    По площади строк: {}
</p>
<p>
    По площади фрагментов: {}
</p>
<h3>Площадь изображений:</h3>
<p>
    <!--По типам блоков (1 = изображение): {}<br>-->
    Расчет с помощью get_page_images()): {}
</p>
<h3>Отношение площади текста (всех span) к площади изображений:</h3>
<p>
    {}
</p>
<!--<h3>Log</h3>
<p>
{}
</p>-->'''.format(doc.name,
    tp['width'], tp['height'], page_area,
    text_block_area,
    text_line_area, text_span_area,
    block_image_area, page_image_area,
    (text_span_area / page_image_area),
    log)

    # Close the document to release resources,
    # and close the file releasing control to the OS
    doc.close()

    return page_content

def area(x0, y0, x1, y1):
    a = x1 - x0
    b = y1 - y0
    return a * b

# def walk_dict(d,depth=0):
#     result = ""
#     for k,v in sorted(d.items(),key=lambda x: x[0]):
#         if isinstance(v, dict):
#             result += ("&nbsp;&nbsp;&nbsp;&nbsp;")*depth + ("%s" % k)
#             walk_dict(v,depth+1)
#         else:
#             result += ("&nbsp;&nbsp;&nbsp;&nbsp;")*depth + "%s %s" % (k, v)

#     return result

    # Get just text
    # page_content = page.getText("text")
    # Get HTML with images in binary representation and all data about text
    # page_content = page.getText("html")