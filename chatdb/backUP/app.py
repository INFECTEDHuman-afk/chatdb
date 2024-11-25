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
        "customers": {
            "fields": ["_id", "customerId", "name", "email", "phone"]
        },
        "orders": {
            "fields": ["_id", "orderId", "customerId", "status", "totalAmount", "orderDate"]
        }
    }
}

QUERY_PATTERNS = [
    (re.compile(r"(total|sum of)\s(\w+)\sby\s(\w+)"), "total <A> by <B>"),
    (re.compile(r"(average|mean of)\s(\w+)\sby\s(\w+)"), "average <A> by <B>"),
    (re.compile(r"(count of|number of)\s(\w+)"), "count of <B>"),
    (re.compile(r"(find|list)\s(\w+)\s(greater than|>\s)(\d+)"), "find <A> greater than a threshold"),
    (re.compile(r"(list|show)\sall\s(\w+)\ssorted by\s(\w+)"), "list all <B> sorted by <A>"),
    (re.compile(r"top\s(\d+)\s(\w+)\sby\s(\w+)"), "top <N> <B> by <A>")
]

# Sample MongoDB query templates
SAMPLE_QUERIES = [
    '''db.products.aggregate([
    {
        "$group": {
            "_id": "$brand",
            "averagePrice": {
                "$avg": "$price"
            }
        }
    }
])''',

    '''db.products.find({
    "price": {
        "$gt": 100
    }
}).sort({
    "price": -1
})''',

    '''db.products.aggregate([
    {
        "$match": {
            "stock": {
                "$lt": 50
            }
        }
    },
    {
        "$group": {
            "_id": "$brand",
            "totalStock": {
                "$sum": "$stock"
            }
        }
    }
])''',

    '''db.products.aggregate([
    {
        "$lookup": {
            "from": "categories",
            "localField": "category",
            "foreignField": "_id",
            "as": "categoryDetails"
        }
    }
])''',

    '''db.products.find({
    "ratings.rating": {
        "$gte": 4
    }
})''',

    '''db.products.aggregate([
    {
        "$unwind": "$ratings"
    },
    {
        "$group": {
            "_id": "$name",
            "averageRating": {
                "$avg": "$ratings.rating"
            }
        }
    }
])'''
]

# Define quantitative and categorical attributes
QUANTITATIVE_ATTRIBUTES = ["price", "stock", "sales", "totalAmount"]
CATEGORICAL_ATTRIBUTES = ["brand", "category", "product category"]

# Define construct keywords and patterns
CONSTRUCT_KEYWORDS = {
    "group by": "total <A> by <B>",
    "total": "total <A> by <B>",
    "average": "average <A> by <B>",
    "count": "count of <B>",
    "greater than": "find <A> greater than a threshold",
    "sorted by": "list all <B> sorted by <A>"
}



def generate_mongo_query(construct):
    pattern = CONSTRUCT_KEYWORDS.get(construct, None)
    if not pattern:
        return {"mongo_query": "Error: Unrecognized construct."}

    quantitative_attr = random.choice(QUANTITATIVE_ATTRIBUTES)
    categorical_attr = random.choice(CATEGORICAL_ATTRIBUTES)

    if pattern == "total <A> by <B>":
        mongo_query = f'''
db.products.aggregate([
    {{
        "$group": {{
            "_id": "${categorical_attr}",
            "total_{quantitative_attr}": {{
                "$sum": "${quantitative_attr}"
            }}
        }}
    }}
])
'''
    elif pattern == "average <A> by <B>":
        mongo_query = f'''
db.products.aggregate([
    {{
        "$group": {{
            "_id": "${categorical_attr}",
            "average_{quantitative_attr}": {{
                "$avg": "${quantitative_attr}"
            }}
        }}
    }}
])
'''
    elif pattern == "count of <B>":
        mongo_query = f'''
db.products.aggregate([
    {{
        "$group": {{
            "_id": "${categorical_attr}",
            "count": {{
                "$sum": 1
            }}
        }}
    }}
])
'''
    elif pattern == "find <A> greater than a threshold":
        mongo_query = f'''
db.products.find({{
    "{quantitative_attr}": {{
        "$gt": 100
    }}
}})
'''
    elif pattern == "list all <B> sorted by <A>":
        mongo_query = f'''
db.products.find().sort({{
    "{quantitative_attr}": 1
}})
'''
    elif pattern == "top 5 <B> by <A>":
        mongo_query = f'''
db.products.aggregate([
    {{
        "$group": {{
            "_id": "${categorical_attr}",
            "total_{quantitative_attr}": {{
                "$sum": "${quantitative_attr}"
            }}
        }}
    }},
    {{
        "$sort": {{
            "total_{quantitative_attr}": -1
        }}
    }},
    {{
        "$limit": 5
    }}
])
'''
    elif pattern == "filter by <A> and group by <B>":
        mongo_query = f'''
db.products.aggregate([
    {{
        "$match": {{
            "{quantitative_attr}": {{
                "$gt": 50
            }}
        }}
    }},
    {{
        "$group": {{
            "_id": "${categorical_attr}",
            "total_{quantitative_attr}": {{
                "$sum": "${quantitative_attr}"
            }}
        }}
    }}
])
'''
    else:
        mongo_query = "Invalid query"

    return {"mongo_query": mongo_query.strip()}

# Function to generate MongoDB query based on natural language input
def generate_mongo_query_from_natural_language(message):
    message = message.lower()

    for pattern, template in QUERY_PATTERNS:
        match = pattern.search(message)
        if match:
            return generate_mongo_query(template)

    return {"mongo_query": "Error: Could not interpret the request."}

# Function to explore databases (without sample data)
def explore_databases():
    response = "Available Databases and Collections:\n"
    for db_name, collections in DATABASES.items():
        response += f"- {db_name}:\n"
        for collection, details in collections.items():
            fields = ", ".join(details["fields"])
            response += f"  - Collection: {collection}\n"
            response += f"    Fields: {fields}\n"
    return response

# Function to generate sample queries
def generate_sample_queries():
    random_queries = random.sample(SAMPLE_QUERIES, min(len(SAMPLE_QUERIES), 3))
    return "\n\n".join(SAMPLE_QUERIES[:3])

# Function to determine user response based on input
def determine_response(message):
    message = message.lower()

    # Handle explore request
    if "explore" in message:
        return explore_databases()

    # Handle sample queries request with construct keyword detection
    for construct in CONSTRUCT_KEYWORDS.keys():
        if construct in message:
            return  generate_mongo_query(construct)

    # Handle general sample query request
    if "sample" in message or "example queries" in message:
        return "\n\n".join(random.sample(SAMPLE_QUERIES, 3))

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