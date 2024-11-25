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



# Database metadata
DATABASES = {
    "products": {
        "fields": ["_id", "name", "description", "category", "price", "stock", "brand", "createdAt", "ratings"]
    },
    "orders": {
        "fields": ["_id", "userId", "items", "totalAmount", "orderDate", "status", "shippingAddress", "itemCount"]
    },
    "reviews": {
        "fields": ["_id", "userId", "productId", "rating", "review", "createdAt", "reviewLength"]
    }
}

# Define attributes for each dataset
QUANTITATIVE_ATTRIBUTES = {
    "products": ["price", "stock", "ratings.rating"],
    "orders": ["totalAmount", "itemCount"],
    "reviews": ["rating", "reviewLength"]
}

QUALITATIVE_ATTRIBUTES = {
    "products": ["brand", "category", "name", "createdAt"],
    "orders": ["status", "userId", "shippingAddress.city", "shippingAddress.state", "orderDate"],
    "reviews": ["userId", "productId", "review", "createdAt"]
}


QUERY_PATTERNS = [
    (re.compile(r"(total|sum of)\s(\w+)\sby\s(\w+) in (\w+)"), "total <A> by <B> in <dataset>"),
    (re.compile(r"(average|mean of)\s(\w+)\sby\s(\w+) in (\w+)"), "average <A> by <B> in <dataset>"),
    (re.compile(r"(count of|number of)\s(\w+) in (\w+)"), "count of <B> in <dataset>"),
    (re.compile(r"(find|list)\s(\w+)\s(greater than|>\s)(\d+) in (\w+)"), "find <A> greater than a threshold in <dataset>"),
    (re.compile(r"(list|show)\sall\s(\w+)\ssorted by\s(\w+) in (\w+)"), "list all <B> sorted by <A> in <dataset>"),
    (re.compile(r"top\s(\d+)\s(\w+)\sby\s(\w+) in (\w+)"), "top <N> <B> by <A> in <dataset>"),
    (re.compile(r"find records from the last (\d+) days in (\w+)"), "find records from the last <N> days in <dataset>"),
    (re.compile(r"list distinct values of (\w+) in (\w+)"), "list distinct values of <B> in <dataset>"),
    (re.compile(r"find minimum and maximum (\w+) in (\w+)"), "find minimum and maximum <A> in <dataset>"),
    (re.compile(r"average rating by (\w+) where rating is above 4 in (\w+)"), "average rating by <B> where rating is above 4 in <dataset>")
]


# Sample MongoDB query templates
# Updated Sample Query Function
def generate_sample_queries(dataset):
    if dataset == "products":
        sample_queries = [
            '''db.products.aggregate([
                {"$group": {"_id": "$brand", "total_stock": {"$sum": "$stock"}}}
            ])''',
            '''db.products.find({"price": {"$gt": 100}}).sort({"price": -1})''',
            '''db.products.distinct("category")''',
            '''db.products.aggregate([
                {"$group": {"_id": "$category", "average_price": {"$avg": "$price"}}}
            ])''',
            '''db.products.find({}, {"name": 1, "price": 1, "stock": 1})'''
        ]

    elif dataset == "orders":
        sample_queries = [
            '''db.orders.aggregate([
                {"$group": {"_id": "$status", "total_amount": {"$sum": "$totalAmount"}}}
            ])''',
            '''db.orders.find({"totalAmount": {"$gte": 500}}).sort({"totalAmount": -1})''',
            '''db.orders.aggregate([
                {"$group": {"_id": "$shippingAddress.city", "count": {"$sum": 1}}}
            ])''',
            '''db.orders.find({"orderDate": {"$gte": new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)}})''',
            '''db.orders.distinct("status")'''
        ]

    elif dataset == "reviews":
        sample_queries = [
            '''db.reviews.aggregate([
                {"$group": {"_id": "$productId", "average_rating": {"$avg": "$rating"}}}
            ])''',
            '''db.reviews.find({"rating": {"$gt": 4}})''',
            '''db.reviews.aggregate([
                {"$match": {"rating": {"$gte": 4}}},
                {"$group": {"_id": "$userId", "total_reviews": {"$sum": 1}}}
            ])''',
            '''db.reviews.find({}, {"userId": 1, "productId": 1, "rating": 1})''',
            '''db.reviews.distinct("productId")'''
        ]

    else:
        return "Invalid dataset specified. Please choose from 'products', 'orders', or 'reviews'."

    # Randomly select 3 sample queries
    return "\n\n".join(random.sample(sample_queries, 3))

# Define quantitative and categorical attributes
QUANTITATIVE_ATTRIBUTES = ["price", "stock", "sales", "totalAmount"]
CATEGORICAL_ATTRIBUTES = ["brand", "category", "product category"]

# Define construct keywords and patterns
CONSTRUCT_KEYWORDS = {
    "group by": "total <A> by <B>",
    "average": "average <A> by <B>",
    "count": "count of <B>",
    "greater than": "find <A> greater than a threshold",
    "sorted by": "list all <B> sorted by <A>",
    "top": "top <N> <B> by <A>",
    "date filter": "find records from the last <N> days",
    "distinct": "list distinct values of <B>",
    "min and max": "find minimum and maximum <A>",
    "filter by rating": "average rating by <B> where rating is above 4"
}



def generate_mongo_query(template, dataset):
    quantitative_attrs = QUANTITATIVE_ATTRIBUTES[dataset]
    qualitative_attrs = QUALITATIVE_ATTRIBUTES[dataset]

    quantitative_attr = random.choice(quantitative_attrs)
    qualitative_attr = random.choice(qualitative_attrs)

    # Template 1: Total <A> by <B>
    if template == "total <A> by <B> in <dataset>":
        return f'''
db.{dataset}.aggregate([
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

    # Template 2: Average <A> by <B>
    elif template == "average <A> by <B> in <dataset>":
        return f'''
db.{dataset}.aggregate([
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

    # Template 3: Count of <B>
    elif template == "count of <B> in <dataset>":
        return f'''
db.{dataset}.aggregate([
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

    # Template 4: Find <A> Greater Than Threshold
    elif template == "find <A> greater than a threshold in <dataset>":
        return f'''
db.{dataset}.find({{
    "{quantitative_attr}": {{
        "$gt": 100
    }}
}})
'''

    # Template 5: List All <B> Sorted by <A>
    elif template == "list all <B> sorted by <A> in <dataset>":
        return f'''
db.{dataset}.find().sort({{
    "{quantitative_attr}": 1
}})
'''

    # Template 6: Top N <B> by <A>
    elif template == "top <N> <B> by <A> in <dataset>":
        return f'''
db.{dataset}.aggregate([
    {{
        "$group": {{
            "_id": "${qualitative_attr}",
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

    # Template 7: Filter by Date Range
    elif template == "find records from the last <N> days in <dataset>":
        return f'''
db.{dataset}.find({{
    "createdAt": {{
        "$gte": new Date(Date.now() - <N> * 24 * 60 * 60 * 1000)
    }}
}})
'''

    # Template 8: Distinct Values of <B>
    elif template == "list distinct values of <B> in <dataset>":
        return f'''
db.{dataset}.distinct("{qualitative_attr}")
'''
    
    # Template 9: Minimum and Maximum <A>
    elif template == "find minimum and maximum <A> in <dataset>":
        return f'''
db.{dataset}.aggregate([
    {{
        "$group": {{
            "_id": null,
            "min_{quantitative_attr}": {{ "$min": "${quantitative_attr}" }},
            "max_{quantitative_attr}": {{ "$max": "${quantitative_attr}" }}
        }}
    }}
])
'''

    # Template 10: Average Rating by <B> with Condition
    elif template == "average rating by <B> where rating is above 4 in <dataset>":
        return f'''
db.{dataset}.aggregate([
    {{
        "$match": {{
            "rating": {{ "$gt": 4 }}
        }}
    }},
    {{
        "$group": {{
            "_id": "${qualitative_attr}",
            "average_rating": {{ "$avg": "$rating" }}
        }}
    }}
])
'''

    return "Invalid query"


# Function to generate MongoDB query based on natural language input
def generate_mongo_query_from_natural_language(message):
    message = message.lower()

    for pattern, template in QUERY_PATTERNS:
        match = pattern.search(message)
        if match:
            dataset = match.group(len(match.groups()))
            if dataset in DATABASES:
                return generate_mongo_query(template, dataset)

    return "Error: Could not interpret the request."

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



# Function to determine user response based on input
def determine_response(message):
    message = message.lower()

    # Handle explore request
    if "explore" in message:
        return explore_databases()

    # Handle sample queries request with specified dataset
    if "sample" in message or "example queries" in message:
        for dataset in DATABASES.keys():
            if dataset in message:
                return generate_sample_queries(dataset)
        return "Please specify a valid dataset: 'products', 'orders', or 'reviews'."

    # Handle construct keywords
    for construct in CONSTRUCT_KEYWORDS.keys():
        if construct in message:
            dataset = message.split(" in ")[-1].strip()
            if dataset in DATABASES:
                return generate_mongo_query(CONSTRUCT_KEYWORDS[construct], dataset)

    # Handle natural language query
    return generate_mongo_query_from_natural_language(message)
        



@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Invalid request, message key missing'}), 400

        message = data['message']
        response = determine_response(message)

        return jsonify({'response': response}), 200
    except Exception as e:
        return jsonify({'error': f"Internal Server Error: {str(e)}"}), 500





if __name__ == '__main__':
    app.run(debug=True)