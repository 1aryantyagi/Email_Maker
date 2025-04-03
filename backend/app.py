from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
import os
import pandas as pd
import boto3
from main import process_excel_to_csv

from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# JWT Configuration
app.config['JWT_SECRET_KEY'] = 'super-secret-key'  # Change this in production!

# File upload configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'csv'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Create uploads directory if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class User(db.Model):
    __tablename__ = 'users'  # Ensure the table is named correctly

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class CSVData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), db.ForeignKey('users.username'), nullable=False)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    url = db.Column(db.String(512))
    email_text = db.Column(db.Text)

# Ensure the table exists before the app starts
def ensure_tables():
    with app.app_context():
        inspector = inspect(db.engine)
        if "users" not in inspector.get_table_names():
            print("Creating users table...")
            db.create_all()
        else:
            print("Users table already exists.")

ensure_tables()

# Authentication routes
@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"msg": "Bad username or password"}), 401
    
    access_token = create_access_token(identity=username)
    return jsonify(token=access_token)

# Protected routes
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    current_user = get_jwt_identity()
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        output_filename = f"processed_{filename.split('.')[0]}.csv"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        try:
            # Process file and get data
            data = process_excel_to_csv(filepath, output_path)
            
            # Store data in database
            for item in data:
                csv_entry = CSVData(
                    username=current_user,
                    name=item['Name'],
                    email=item['Email'],
                    url=item['URL'],
                    email_text=item['Email_Text']
                )
                db.session.add(csv_entry)
            db.session.commit()
            
            return jsonify({"filename": output_filename}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error processing file: {str(e)}"}), 500
    
    return jsonify({"error": "Invalid file type"}), 400

@app.route('/download-file/<filename>')
def download_file(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(path, as_attachment=True)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    name = data.get('name')
    password = data.get('password')

    if User.query.filter_by(username=username).first():
        return jsonify({"msg": "Username already exists"}), 400

    user = User(username=username, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"msg": "User created successfully"}), 201


@app.route('/send-emails', methods=['POST'])
@jwt_required()
def send_emails():
    current_user = get_jwt_identity()
    data = request.get_json()
    emails = data.get('emails', [])

    if not emails:
        return jsonify({"error": "No emails provided"}), 400

    records = CSVData.query.filter_by(username=current_user).filter(CSVData.email.in_(emails)).all()

    # Check for missing emails...
    
    try:
        ses_client = boto3.client('ses', region_name=os.getenv('AWS_REGION'))
        sender_email = os.getenv('AWS_SES_SENDER_EMAIL')
        for record in records:
            # Extract subject from email_text
            email_text = record.email_text
            subject = "No Subject"  # Default
            if email_text.startswith('Subject: '):
                subject_line = email_text.split('\n', 1)[0]
                subject = subject_line[len('Subject: '):].strip()
            
            # Send email with extracted subject
            ses_client.send_email(
                Source=sender_email,
                Destination={'ToAddresses': [record.email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': email_text, 'Charset': 'UTF-8'}
                    }
                }
            )
        return jsonify({"msg": "Emails sent successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)