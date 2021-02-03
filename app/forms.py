from wtforms import Form
from wtforms import FileField
from wtforms.validators import Required

class SelectPdfForm(Form):
    pdf_file = FileField('pdf_file', validators = [Required()])
    