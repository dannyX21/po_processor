from flask_wtf import Form
from wtforms import StringField, IntegerField, SubmitField, BooleanField, TextAreaField, SelectField, FileField, DateField
from ..models import User, Role, Customer, Serie
from wtforms.validators import Required, NumberRange, Optional, Email, URL, Length, Regexp
from wtforms import ValidationError

class NewCustomerForm(Form):
    code = StringField('Customer code',validators=[Required()])
    name = StringField('Name', validators=[Required()])
    submit = SubmitField('submit')

class NewSeriesForm(Form):
    customer_id = SelectField('Customer',coerce=int)
    pn_format = StringField('P/N Format', validators=[Required(), Length(1,64)])
    regex = StringField('Regular Expression', validators=[Required()])
    description = StringField('Description', validators=[Required(),Length(1,64)])
    rev_level = StringField('Rev. Level', validators=[Required(), Length(1,2)])
    submit = SubmitField('submit')

    def __init__(self, *args, **kwargs):
        super(NewSeriesForm, self).__init__(*args, **kwargs)
        self.customer_id.choices = [(customer.id, customer.name) for customer in Customer.query.order_by(Customer.name).all()]

    def validate_pn_format(self, field):
        if Serie.query.filter_by(pn_format=field.data).first():
            raise ValidationError("Serie: '{}' is already registered.".format(field.data))

    def validate_regex(self, field):
        if Serie.query.filter_by(regex=field.data).first():
            raise ValidationError("There's a serie already registered with the same Regular Expression.".format(field.data))

class FileUpload_Form(Form):
    fileUpload = FileField('Select file: ')
    submit = SubmitField('Submit')
