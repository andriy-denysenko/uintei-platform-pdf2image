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
	'''
	Represents a 'bbox' object for each class having it.
	'''
	def __init__(self, bbox):
		'''Initializes an instance with bbox node (a 4-tuple)'''
		self._bbox = bbox

	def get_x0(self):
		'''Gets the leftmost corner x

		Returns:
		int: the leftmost corner x
		'''
		
		return self._bbox[0]

	def get_x1(self):
		'''Gets the rightmost corner x

		Returns:
		int: the rightmost corner x
		'''

		return self._bbox[1]

	def get_y0(self):
		'''Gets the highest y

		Returns:
		int: the lowest y
		'''

		return self._bbox[2]

	def get_y1(self):
		'''Gets the lowest y

		Returns:
		int: the lowest y
		'''

		return self._bbox[3]

	def get_area(self):
		'''Calculates the box area

		Returns:
		float: box area'''
		return (self.get_x1() - self.get_x0()) * (self.get_y1() - self.get_y0())

class PDFSpan:
	'''
	Represents a 'span' object.
	'''
	def __init__(self, span):
		'''Initializes an instance with a span and a bbox'''
		self._span = span
		self._bbox = PDFBBox(self._span['bbox'])

	def get_area(self):
		'''Gets span area

		Return:
		float: span area'''
		return self._bbox.get_area()

	def get_text(self):
		'''Gets span text

		Returns:
		str: span text'''

		return self._span['text']

class PDFLine:
	'''
	Represents a 'line' object.
	'''
	def __init__(self, line):
		'''Initializes an instance with a line node and creates spans'''
		self._line = line
		self._bbox = PDFBBox(self._line['bbox'])
		self._spans = []
		for span in self._line['spans']:
			sp = PDFSpan(span)
			self._spans.append(sp)

	def get_area(self):
		'''Gets line area

		Return:
		float: line area'''

		return self._bbox.get_area()

	def get_spans(self):
		'''Gets line span list

		Return:
		list(PDFSpan): line span list'''
		return self._spans

class PDFBlock:
	'''
	Represents a 'block' object.
	'''
	def __init__(self, block):
		'''Initializes an instance

		Sets a block node and a bbox and creates lines which in turn create spans'''
		self._block = block
		self._bbox = PDFBBox(self._block['bbox'])
		self._lines = []
		for line in self._block['lines']:
			ln = PDFLine(line)
			self._lines.append(ln)

	def get_number(self):
		'''Gets block number

		Return:
		int: block number'''

		return self._block['number']

	def get_type(self):
		'''Gets block type

		Return:
		int: block type (0 for text, 1 for image)'''

		# README: the TextPage object does not return 1 for image blocks
		
		return self._block['type']

	def get_area(self):
		'''Gets block area

		Return:
		float: block area'''
		
		return self._bbox.get_area()

	def get_lines(self):
		'''Gets block line list

		Return:
		list(PDFLine): block line list'''
		
		return self._lines


class PDFPage:
	'''
	Represents a 'page' object.
	'''
	def __init__(self, page):
		'''Initializes a page instance

		Sets a page and a textpage,
		extracts child objects as a dictionary,
		gets all images
		and creates all blocks which in turn create lines and spans.
		Calculates text and image area and relation (text/image area)
		'''

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

		# README: 2021-02-11 Added check for zero image or zero text area

		# 0 means No images
		self._ratio = 0

		# Check for zero values
		if self._text_area == 0:
			if self._images_area == 0:
				self._ratio = -2
				# -2 means No images, No text
			else:
				self._ratio = -1
				# -1 means No text
		# There is text
		elif self._images_area > 0:
			self._ratio = self._text_area / self._images_area
			# > 0 means relation

	def get_width(self):
		'''Gets the width attribute

		Returns:
		float: height'''
		return self._as_dict['width']

	def get_height(self):
		'''Gets the height attribute

		Returns:
		float: height'''
		return self._as_dict['height']

	def get_number(self):
		'''Gets the page number

		Returns:
		int: page number'''
		return self._page.number

	def get_images_area(self):
		'''Gets images area

		Returns:
		float: text area'''
		return self._images_area

	def get_text_area(self):
		'''Gets the text area

		Returns:
		float: text area'''
		return self._text_area

	def get_ratio(self):
		'''Gets the text/image area ratio

		Returns:
		float: text/image area ratio'''
		return self._ratio

	def dump(self):
		'''Formats text and image statistics

		Returns HTML code with coloured statistics of text/image area relation for the page.

		Returns:
		str: HTML code with coloured statistics

		'''

		# TODO: Let the user set bounds for colouring

		# README: 2021-02-11 Added check for ratio values

		# Ratio means:
		# -2: No text, No images
		# -1: No text
		#  0: No images
		# >0: Text/Images

		color = "Orange"
		ratio = self.get_ratio()
		ratio_str = ''

		if ratio == -2:
			ratio_str = "<h4>Немає тексту та зображень</h4>"
			color = "Green"
		elif ratio == -1:
			ratio_str = "<h4>Лише зображення, немає тексту</h4>"
			color = "Red"
		elif ratio == 0:
			ratio_str = "<h4>Лише текст, немає зображень</h4>"
			color = "Green"
			print(f"Set color to Green: {color}")
		else:
			ratio_str = f'''<h4>Відношення площини тексту до площини зображень</h4>
<p>{'{:.2f}'.format(ratio)}</p>'''
			if ratio < 0.7:
				color = "Red"
			if ratio > 1.3:
				color = "Green"
		# TODO: Create styles for colouring

		print(f"Color before dumping: {color}")

		result = f'''<div style="color:{color}"><h3>Сторінка № {self.get_number() + 1}</h3>
	<h4>Площина фрагментів тексту</h4>
	<p>{'{:.2f}'.format(self.get_text_area())}</p>
	<h4>Площина зображень</h4>
	<p>{'{:.2f}'.format(self.get_images_area())}</p>
	{ratio_str}
</div>'''

		return result

class PDFDocument:
	'''
	Implements a pdf document object.
	'''
	def __init__(self, pdf_filename):
		'''Initializes a document instance

		Creates a list PDFPage objects which do the magic
		of all child objects creation and area calculation.
		Calculates text and image area and relation (text/image area)
		'''
		
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

		# README: 2021-02-11 Added check for zero image or zero text area

		# 0 means No images
		self._ratio = 0

		# Check for zero values
		if self._text_area == 0:
			if self._images_area == 0:
				self._ratio = -2
				# -2 means No images, No text
			else:
				self._ratio = -1
				# -1 means No text
		# There is text
		elif self._images_area > 0:
			self._ratio = self._text_area / self._images_area
			# > 0 means relation

	def get_page_count(self):
		'''Gets page count

		Returns:
		int: page count'''
		return self._doc.page_count

	def get_pages(self):
		'''Gets PDFPage list

		Returns:
		list(PDFPage): list of page objects'''

		return self._pages

	def get_images_area(self):
		'''Gets images area

		Returns:
		float: text area'''
		return self._images_area

	def get_text_area(self):
		'''Gets the text area

		Returns:
		float: text area'''
		return self._text_area

	def get_ratio(self):
		'''Gets the text/image area ratio

		Returns:
		float: text/image area ratio'''
		return self._ratio

	def get_name(self):
		'''Gets the document name

		Returns:
		str: document name'''
		return self._doc.name

	def dump(self):
		'''Formats text and image statistics

		Returns HTML code with coloured statistics of text/image area relation
		for a document as a whole, and for each individual page.

		Returns:
		str: HTML code with coloured statistics

		'''

		# README: 2021-02-11 Added check for ratio values
		# TODO: Let the user set bounds for colouring

		# Ratio means:
		# -2: No text, No images
		# -1: No text
		#  0: No images
		# >0: Text/Images

		color = "Orange"
		ratio = self.get_ratio()
		ratio_str = ''

		if ratio == -2:
			ratio_str = "<h2>Немає тексту та зображень</h2>"
			color = "Green"
		elif ratio == -1:
			ratio_str = "<h2>Лише зображення, немає тексту</h2>"
			color = "Red"
		elif ratio == 0:
			ratio_str = "<h2>Лише текст, немає зображень</h2>"
			color = "Green"
		else:
			ratio_str = f'''<h2>Відношення площини тексту до площини зображень</h2>
<p>{'{:.2f}'.format(ratio)}</p>'''
			if ratio < 0.7:
				color = "Red"
			if ratio > 1.3:
				color = "Green"
		# TODO: Create styles for colouring

		result = f'''<div style="color:{color}"><h1>{self.get_name()}</h1>
	<h2>Площина фрагментів тексту</h2>
	<p>{'{:.2f}'.format(self.get_text_area())}</p>
	<h2>Площина зображень</h2>
	<p>{'{:.2f}'.format(self.get_images_area())}</p>
	{ratio_str}
</div>'''
		return result

	def close(self):
		'''Releases the resources and the file'''
		self._doc.close()
		self._is_closed = True

	def is_closed(self):
		'''Tells if the document is closed

		Returns:
		bool: True of the document is closed, False otherwise'''

		return self._is_closed


@CELERY.task()
def process_pdf(pdf_filename):
	'''Formats text and image statistics

	Returns HTML code with coloured statistics of text/image area relation
	for a document as a whole, and for each individual page.

	Returns:
	str: HTML code with coloured statistics

	'''

	doc = PDFDocument(pdf_filename)
	result = doc.dump()
	for page in doc.get_pages():
		result += page.dump()
	
	# Release the file and its resources
	doc.close()

	return result

