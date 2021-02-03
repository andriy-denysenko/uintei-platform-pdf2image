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

class PDFBBox:
	def __init__(self, bbox):
		self._bbox = bbox

	def get_x0(self):
		return self._bbox[0]

	def get_x1(self):
		return self._bbox[1]

	def get_y0(self):
		return self._bbox[2]

	def get_y1(self):
		return self._bbox[3]

	def get_area(self):
		return (self.get_x1() - self.get_x0()) * (self.get_y1() - self.get_y0())

class PDFSpan:
	def __init__(self, span):
		self._span = span
		self._bbox = PDFBBox(self._span['bbox'])

	def get_area(self):
		return self._bbox.get_area()

	def get_text(self):
		return self._span['text']

class PDFLine:
	def __init__(self, line):
		self._line = line
		self._bbox = PDFBBox(self._line['bbox'])
		self._spans = []
		for span in self._line['spans']:
			sp = PDFSpan(span)
			self._spans.append(sp)

	def get_area(self):
		return self._bbox.get_area()

	def get_spans(self):
		return self._spans

class PDFBlock:
	def __init__(self, block):
		self._block = block
		self._bbox = PDFBBox(self._block['bbox'])
		self._lines = []
		for line in self._block['lines']:
			ln = PDFLine(line)
			self._lines.append(ln)

	def get_number(self):
		return self._block['number']

	def get_type(self):
		return self._block['type']

	def get_area(self):
		return self._bbox.get_area()

	def get_lines(self):
		return self._lines


class PDFPage:
	def __init__(self, page):
		self._page = page
		self._text_page = self._page.get_textpage()
		self._as_dict = self._text_page.extractDICT()
		self._images = self._page.get_images()
		
		self._images_area = 0
		for image in self._images:
			self._images_area += image[2] * image[3]

		self._text_area = 0

		self._blocks = []
		for b in self._as_dict['blocks']:
			blk = PDFBlock(b)
			self._blocks.append(blk)
			for line in blk.get_lines():
				for span in line.get_spans():
					self._text_area += span.get_area()

		self._ratio = self._text_area / self._images_area

	def get_width(self):
		return self._as_dict['width']

	def get_height(self):
		return self._as_dict['height']

	def get_number(self):
		return self._page.number

	def get_images_area(self):
		return self._images_area

	def get_text_area(self):
		return self._text_area

	def get_ratio(self):
		return self._ratio

	def dump(self):
		# TODO: Let the user set bounds for colouring
		color = "Yellow"
		if self.get_ratio() < 0.7:
			color = "Red"
		if self.get_ratio() > 1.3:
			color = "Green"
		# TODO: Create styles for colouring

		result = f'''<div style="color:{color}"><h3>Страница № {self.get_number() + 1}</h3>
<h4>Площадь фрагментов текста</h4>
<p>{'{:.2f}'.format(self.get_text_area())}</p>
<h4>Площадь изображений</h4>
<p>{'{:.2f}'.format(self.get_images_area())}</p>
<h4>Отношение площади текста к площади изображений</h4>
<p>{'{:.2f}'.format(self.get_ratio())}</p></div>'''
		return result

class PDFDocument:
	def __init__(self, pdf_filename):
		
		# Open the document
		self._doc = fitz.open(pdf_filename)
		self._is_closed = False

		# Create pages
		self._pages = []
		for i in range(self.get_page_count()):
			self._pages.append(
				PDFPage(self._doc.loadPage(i))
			);

		# Calculate text and image areas
		self._text_area = 0
		self._images_area = 0

		for page in self._pages:
			self._text_area += page.get_text_area()
			self._images_area += page.get_images_area()

		# Determine if text prevails ove images:
		# Calculate relation of text area to image area
		self._ratio = self._text_area / self._images_area

	def get_page_count(self):
		return self._doc.page_count

	def get_pages(self):
		return self._pages

	def get_text_area(self):
		return self._text_area

	def get_images_area(self):
		return self._images_area

	def get_ratio(self):
		return self._ratio

	def get_name(self):
		return self._doc.name

	def dump(self):
		result = f'''<h1>{self.get_name()}</h1>
<h2>Площадь фрагментов текста</h2>
<p>{'{:.2f}'.format(self.get_text_area())}</p>
<h2>Площадь изображений</h2>
<p>{'{:.2f}'.format(self.get_images_area())}</p>
<h2>Отношение площади текста к площади изображений</h2>
<p>{'{:.2f}'.format(self.get_ratio())}</p>'''
		return result

	def close(self):
		# Release resources and the file
		self._doc.close()
		self._is_closed = True

	def is_closed(self):
		return self._is_closed


@CELERY.task()
def process_pdf(pdf_filename):
	doc = PDFDocument(pdf_filename)
	result = doc.dump()
	for page in doc.get_pages():
		result += page.dump()
	doc.close()
	return result

