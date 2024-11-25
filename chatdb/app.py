from flask import Flask, request, render_template, jsonify
import re
import pandas as pd
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import random
from flask_cors import CORS


app = Flask(__name__)
CORS(app) 

# Configure file upload settings
DB_TYPE=0
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'csv', 'json'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# MongoDB connection function
def get_mongo_connection():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["chatdb"]
    return db



# Test MongoDB connection
def test_mongo_connection():
    try:
        db = get_mongo_connection()
        db.list_collection_names()  # Test connection by listing collections
        print("MongoDB connection successful")
    except Exception as err:
        print(f"MongoDB connection error: {err}")

# Route to serve the main page
@app.route('/')
def index():
    return render_template('index.html')

DATABASES = {
    "chatDB": {
        "products": {
            "fields": ["_id", "name", "description", "category", "price", "stock", "brand", "createdAt", "ratings"]
        },
        "orders": {
            "fields": ["_id", "userId", "items", "totalAmount", "orderDate", "status", "shippingAddress", "itemCount"]
        },
        "reviews": {
            "fields": ["_id", "userId", "productId", "rating", "review", "createdAt"]
        }
    }
}

# Quantitative and Qualitative Attributes
QUANTITATIVE_ATTRIBUTES = {
    "products": ["price", "stock", "ratings.rating"],
    "orders": ["totalAmount", "itemCount"],
    "reviews": ["rating"]
}

QUALITATIVE_ATTRIBUTES = {
    "products": ["brand", "category", "name"],
    "orders": ["status", "userId", "shippingAddress.city", "shippingAddress.country", "orderDate"],
    "reviews": ["userId", "productId", "review", "createdAt"]
}

# Construct Keywords and Their Query Patterns
CONSTRUCT_KEYWORDS = {
    "group by": "total <A> by <B>",
    "total": "total <A> by <B>",
    "average": "average <A> by <B>",
    "count": "count of <B>",
    "greater than": "find <A> greater than a threshold",
    "sorted by": "list all <B> sorted by <A>",
    "aggregation": "aggregation construct",
    "having": "having construct"
}

# Generate MongoDB Query Based on Construct and Collection
def generate_mongo_query(template, collection):
    quantitative_attrs = QUANTITATIVE_ATTRIBUTES.get(collection, [])
    qualitative_attrs = QUALITATIVE_ATTRIBUTES.get(collection, [])

    if not quantitative_attrs or not qualitative_attrs:
        return "Error: Invalid dataset or attributes."

    quantitative_attr = random.choice(quantitative_attrs)
    qualitative_attr = random.choice(qualitative_attrs)

    # Query templates
    if template == "total <A> by <B>":
        return f'''
db.{collection}.aggregate([
    {{
        "$group": {{
            "_id": "${qualitative_attr}",
            "total_{quantitative_attr}": {{
                "$sum": "${quantitative_attr}"
            }}
        }}
    }}
])
'''
    elif template == "average <A> by <B>":
        return f'''
db.{collection}.aggregate([
    {{
        "$group": {{
            "_id": "${qualitative_attr}",
            "average_{quantitative_attr}": {{
                "$avg": "${quantitative_attr}"
            }}
        }}
    }}
])
'''
    elif template == "count of <B>":
        return f'''
db.{collection}.aggregate([
    {{
        "$group": {{
            "_id": "${qualitative_attr}",
            "count": {{
                "$sum": 1
            }}
        }}
    }}
])
'''
    elif template == "find <A> greater than a threshold":
        return f'''
db.{collection}.find({{
    "{quantitative_attr}": {{
        "$gt": 100
    }}
}})
'''
    elif template == "list all <B> sorted by <A>":
        return f'''
db.{collection}.find().sort({{
    "{quantitative_attr}": 1
}})
'''
    else:
        return "Error: Invalid query template."

# Explore Databases Functionality
def explore_databases():
    response = "Available Databases and Collections:\n"
    for db_name, collections in DATABASES.items():
        response += f"- {db_name}:\n"
        for collection, details in collections.items():
            fields = ", ".join(details["fields"])
            response += f"  - Collection: {collection}\n"
            response += f"    Fields: {fields}\n"
    return response

# Generate Sample Queries for Collections
def generate_sample_queries(collection):
    if collection == "products":
        return [
            '''db.products.aggregate([{"$group": {"_id": "$brand", "total_stock": {"$sum": "$stock"}}}])''',
            '''db.products.find({"price": {"$gt": 100}}).sort({"price": -1})''',
            '''db.products.distinct("category")'''
        ]
    elif collection == "orders":
        return [
            '''db.orders.aggregate([{"$group": {"_id": "$status", "total_amount": {"$sum": "$totalAmount"}}}])''',
            '''db.orders.find({"totalAmount": {"$gte": 500}}).sort({"totalAmount": -1})''',
            '''db.orders.distinct("status")'''
        ]
    elif collection == "reviews":
        return [
            '''db.reviews.aggregate([{"$group": {"_id": "$productId", "average_rating": {"$avg": "$rating"}}}])''',
            '''db.reviews.find({"rating": {"$gt": 4}})''',
            '''db.reviews.distinct("productId")'''
        ]
    else:
        return ["Invalid collection specified."]

QUERY_PATTERNS = [
    (re.compile(r"(find|show|list)\s+total\s+(\w+)\s+by\s+(\w+)\s+in\s+(\w+)"), "total <A> by <B>"),
    (re.compile(r"(find|show|list)\s+average\s+(\w+)\s+by\s+(\w+)\s+in\s+(\w+)"), "average <A> by <B>"),
    (re.compile(r"(find|show|list)\s+count\s+of\s+(\w+)\s+in\s+(\w+)"), "count of <B>"),
    (re.compile(r"(find|list)\s+(\w+)\s+greater\s+than\s+(\d+)\s+in\s+(\w+)"), "find <A> greater than a threshold"),
    (re.compile(r"(list|show)\s+all\s+(\w+)\s+sorted\s+by\s+(\w+)\s+in\s+(\w+)"), "list all <B> sorted by <A>"),
    (re.compile(r"top\s+(\d+)\s+(\w+)\s+by\s+(\w+)\s+in\s+(\w+)"), "top <N> <B> by <A>")
]

# Parse natural language and generate MongoDB query
def generate_mongo_query_from_natural_language(message):
    message = message.lower()

    for pattern, template in QUERY_PATTERNS:
        match = pattern.search(message)
        if match:
            groups = match.groups()
            if template in ["total <A> by <B>", "average <A> by <B>", "count of <B>"]:
                collection = groups[-1]
                if collection in DATABASES["chatDB"]:
                    return generate_mongo_query(template, collection)
            elif template == "find <A> greater than a threshold":
                collection = groups[-1]
                if collection in DATABASES["chatDB"]:
                    threshold = int(groups[-2])
                    return f'''
db.{collection}.find({{
    "{groups[1]}": {{
        "$gt": {threshold}
    }}
}})
'''
            elif template in ["list all <B> sorted by <A>", "top <N> <B> by <A>"]:
                collection = groups[-1]
                if collection in DATABASES["chatDB"]:
                    return generate_mongo_query(template, collection)
    return "Error: Could not interpret the request."

# Modified Response Determination
def determine_response(message):
    message = message.lower()

    # Handle explore request
    if "explore" in message:
        return explore_databases()

    # Handle sample queries request
    if "sample" in message:
        for collection in DATABASES["chatDB"].keys():
            if collection in message:
                return "\n".join(generate_sample_queries(collection))
        return "Please specify a valid collection: 'products', 'orders', or 'reviews'."

    # Handle construct keywords and specific collections
    for construct in CONSTRUCT_KEYWORDS.keys():
        if construct in message:
            for collection in DATABASES["chatDB"].keys():
                if collection in message:
                    return generate_mongo_query(CONSTRUCT_KEYWORDS[construct], collection)

    # Handle natural language query
    return generate_mongo_query_from_natural_language(message)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        print("Received JSON payload:", data)

        if not data or 'message' not in data:
            return jsonify({'error': 'Invalid request, message key missing'}), 400

        message = data['message']
        response = determine_response(message)

        return jsonify({'response': response}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f"Internal Server Error: {str(e)}"}), 500




if __name__ == '__main__':
    app.run(debug=True)