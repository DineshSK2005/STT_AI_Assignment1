import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.trace import SpanKind
from datetime import datetime
from threading import Lock

class Metrics:
    def __init__(self):  # Corrected constructor method
        self.requests_count = 0
        self.error_count = 0
        self.lock = Lock()  # Lock initialization

    def increment_requests(self):
        with self.lock:  # Lock to ensure thread safety
            self.requests_count += 1
            return self.requests_count

    def increment_errors(self):
        with self.lock:  # Lock to ensure thread safety
            self.error_count += 1
            return self.error_count

# Usage
metrics = Metrics()  # Creating the Metrics object

# Configure structured logging (JSON output)
def configure_logging():
    log_formatter = logging.Formatter('%(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(log_formatter)

    logging.basicConfig(level=logging.INFO, handlers=[handler])
        
# Utility function for logging successful page rendering
def log_page_rendered(page_name):
    timestamp = datetime.now().isoformat()  # Generate timestamp dynamically
    log_message = {
        "timestamp": timestamp,
        "level": "INFO",
        "message": f"Page '{page_name}' rendered successfully.",
        "page": page_name
    }
    logging.info(json.dumps(log_message))
    
def course_success_info(course):
    timestamp = datetime.now().isoformat()
    log_message = {
        "timestamp": timestamp,
        "status": "success",
        "message": f"Course '{course['name']}' added successfully.",
        "course_code": course['code']
    }
    logging.info(json.dumps(log_message))
    
def missing_fields_error(missing_field):
    timestamp = datetime.now().isoformat()
    log_message = {
        "timestamp": timestamp,
        "status": "error",
        "message": f"Course addition failed, missing field: {missing_field}."
    }
    logging.error(json.dumps(log_message))
    
def error_message(message):
    timestamp = datetime.now().isoformat()
    log_message = {
        "timestamp": timestamp,
        "status": "error",
        "message": message
    }
    logging.error(json.dumps(log_message))
    
# Flask App Initialization
app = Flask(__name__)
app.secret_key = 'secret'
COURSE_FILE = 'course_catalog.json'

# Configure OpenTelemetry Tracing and Metrics
trace.set_tracer_provider(TracerProvider(resource=Resource.create({"service.name": "course-catalog-service"})))
# meter_provider = MeterProvider()
# metrics.set_meter_provider(meter_provider)
tracer = trace.get_tracer(__name__)

# Instrument Flask with OpenTelemetry
FlaskInstrumentor().instrument_app(app)

# Configure Jaeger Exporter for Tracing
jaeger_exporter = JaegerExporter(agent_host_name="localhost", agent_port=6831)
span_processor = BatchSpanProcessor(jaeger_exporter)
# span_processor = BatchSpanProcessor(ConsoleSpanExporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Utility Functions
def load_courses():
    """Load courses from the JSON file."""
    if not os.path.exists(COURSE_FILE):
        return []  # Return an empty list if the file doesn't exist
    with open(COURSE_FILE, 'r') as file:
        return json.load(file)


def save_courses(data):
    """Save new course data to the JSON file."""
    courses = load_courses()  # Load existing courses
    courses.append(data)  # Append the new course
    with open(COURSE_FILE, 'w') as file:
        json.dump(courses, file, indent=4)


# Routes
@app.route('/')
def index():
    with tracer.start_as_current_span("Rendering index page", kind=SpanKind.SERVER) as span:
        current_requests = metrics.increment_requests()
        span.set_attribute("requests_count", current_requests)
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.set_attribute("user id",request.remote_addr)
        # route_requests_counter.add(1, {"route": "index"})  # Increment the counter for this route
        log_page_rendered("index") 
        return render_template('index.html')

@app.route('/catalog')
def course_catalog():
    courses = load_courses()
    with tracer.start_as_current_span("Rendering course catalog", kind=SpanKind.SERVER) as span:
        current_requests = metrics.increment_requests()
        span.set_attribute("requests_count", current_requests)
        log_page_rendered("course_catalog")
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.set_attribute("user id",request.remote_addr)
        return render_template('course_catalog.html', courses=courses)

@app.route('/add/course' , methods=['GET', 'POST'])
def add_course():
    if request.method == 'POST':
        with tracer.start_as_current_span("Add Course", kind=SpanKind.SERVER) as span:
            current_requests = metrics.increment_requests()
            span.set_attribute("requests_count", current_requests)
            log_page_rendered("add_course")
            course = {
                'code': request.form['code'],
                'name': request.form['name'],
                'instructor': request.form['instructor'],
                'semester': request.form['semester'],
                'schedule': request.form['schedule'],
                'classroom': request.form['classroom'],
                'prerequisites': request.form['prerequisites'],
                'grading': request.form['grading'],
                'description': request.form['description']
            }
            # spanning meta data
            
            span.set_attribute("http.url", request.url)
            span.set_attribute("http.method", request.method)
            span.set_attribute("course.code", course['code'])
            span.set_attribute("course.name", course['name'])
            span.set_attribute("course.instructor", course['instructor'])
            span.set_attribute("course.semester",course['semester'])
            span.set_attribute("course.schedule", course['schedule'])
            span.set_attribute("course.classroom",course['classroom'])
            span.set_attribute("course.prerequisites",course['prerequisites'])
            span.set_attribute("course.grading", course['grading'])
            span.set_attribute("course.description",course['description'])
            p=1
            for key in ['code','name','schedule','prerequisites']:
                if(course[key]==""):
                    p=0
                    missing_fields_error(key)
                    flash(f"course addition failed as {key} field was empty", "error")
                    span.set_attribute("error", True)
                    span.set_attribute("missing_field", key)
                    error_count = metrics.increment_errors()
                    span.set_attribute("error_count", error_count)
                    break
            if(p==1):
                save_courses(course)
                span.set_attribute("http.method", request.method)
                span.set_attribute("user id",request.remote_addr)
                course_success_info(course)
                flash(f"Course '{course['name']}' added successfully!", "success")
            return redirect(url_for('course_catalog'))
    return render_template('add_course.html')

@app.route('/course/<code>')
def course_details(code):
    with tracer.start_as_current_span("Browsing Course Details", kind=SpanKind.SERVER) as span:
        current_requests = metrics.increment_requests()
        span.set_attribute("requests_count", current_requests)
        log_page_rendered("course_details")
        courses = load_courses()
        course = next((course for course in courses if course['code'] == code), None)
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.set_attribute("user id", request.remote_addr)  # User IP
        span.set_attribute("course_code", code)
        # route_requests_counter.add(1, {"route": "course_details"})  # Increment counter for this route

        if not course:
            # error_counter.add(1, {"error_type": "course_not_found", "code": code})  # Increment error counter
            flash(f"No course found with code '{code}'.", "error")
            error_message(f"No course found with code '{code}'.")
            span.set_attribute("error", True)
            span.set_attribute("error_message", "Course not found")
            return redirect(url_for('course_catalog'))

        span.set_attribute("course.name", course['name'])
        return render_template('course_details.html', course=course)


if __name__ == '__main__':
    configure_logging()
    app.run(debug=True)