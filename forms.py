from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, PasswordField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=80, message="Username must be between 3 and 80 characters.")
    ])
    email = StringField('Email', validators=[
        DataRequired(), 
        Email(message="Invalid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message="Password must be at least 6 characters long.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match.')
    ])
    bio = TextAreaField('Bio', validators=[Length(max=500)])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is already taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already registered. Please login or use a different email.')

class LoginForm(FlaskForm):
    login_id = StringField('Username or Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RepositoryForm(FlaskForm):
    name = StringField('Repository Name', validators=[
        DataRequired(), 
        Length(min=1, max=100, message="Repository name must be 1 to 100 characters.")
    ])
    description = TextAreaField('Description', validators=[Length(max=500)])
    is_private = BooleanField('Private Repository')
    submit = SubmitField('Create Repository')

class FileUploadForm(FlaskForm):
    file = FileField('Select File', validators=[FileRequired()])
    submit = SubmitField('Upload File')

class IssueForm(FlaskForm):
    title = StringField('Issue Title', validators=[
        DataRequired(), 
        Length(min=3, max=200, message="Title must be between 3 and 200 characters.")
    ])
    description = TextAreaField('Description', validators=[DataRequired()])
    submit = SubmitField('Create Issue')

class ProfileEditForm(FlaskForm):
    bio = TextAreaField('Bio', validators=[Length(max=500)])
    submit = SubmitField('Update Profile')

class SearchForm(FlaskForm):
    query = StringField('Search', validators=[DataRequired()])
    submit = SubmitField('Search')
