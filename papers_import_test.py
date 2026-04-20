import sys
import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

def p(msg):
    print(msg)
    sys.stdout.flush()

p("Importing os...")
import os
p("Importing uuid...")
import uuid
p("Importing datetime...")
from datetime import datetime
p("Importing flask...")
from flask import Blueprint, request, jsonify, current_app
p("Importing get_jwt_identity...")
from flask_jwt_extended import get_jwt_identity
p("Importing ObjectId...")
from bson import ObjectId
p("Importing secure_filename...")
from werkzeug.utils import secure_filename
p("Importing auth_middleware...")
from backend.middleware.auth_middleware import jwt_required_custom
p("Importing db...")
from backend.models.db import papers
p("Importing parse_service...")
from backend.services import parse_service
p("Importing nlp_service...")
from backend.services import nlp_service
p("Importing search_service...")
from backend.services import search_service
p("Importing compare_service...")
from backend.services import compare_service
p("Importing plagiarism_service...")
from backend.services import plagiarism_service
p("Importing ai_detect_service...")
from backend.services import ai_detect_service

p("All papers.py imports successful!")
