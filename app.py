from flask import Flask, request, jsonify, render_template
import requests
from flask_cors import CORS
from collections import defaultdict
from operator import itemgetter

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Airtable Configuration
AIRTABLE_BASE_ID = "appnn99jgToBwbm1z"
AIRTABLE_TABLE_NAME = "transactions"
AIRTABLE_GOODS_TABLE_NAME = "Goods"
AIRTABLE_PAT = "patfXdToct2gCXGXy.763b0a7356e1977fb5d26d3993564a14df0d9821494a49e2c51dbfcccd1ce877"

# Airtable API URL
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

# Headers for Airtable API
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_PAT}",
    "Content-Type": "application/json"
}

# Stock Prices (per kg)
STOCK_PRICES = {
    "rice": 2,    # ₹2 per kg
    "wheat": 10,  # ₹10 per kg
    "sugar": 20,  # ₹20 per kg
    "dal": 15     # ₹15 per kg
}

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/central", methods=["GET"])
def central():
    return render_template("committee.html")

@app.route("/transactions", methods=["GET"])
def get_transactions():
    user_id = request.args.get('user_id')
    shop_id = request.args.get('shop_id')
    year = request.args.get('year')
    month = request.args.get('month')

    if not (year and month):
        return jsonify({"error": "Year and Month are required"}), 400

    if not (user_id or shop_id):
        return jsonify({"error": "User ID or Shop ID is required"}), 400

    # Build filter formula
    filter_conditions = [
        f"YEAR({{date}}) = {year}",
        f"MONTH({{date}}) = {month}"
    ]
    
    if user_id:
        filter_conditions.append(f"{{user_id}} = '{user_id}'")
    if shop_id:
        filter_conditions.append(f"{{shop_id}} = '{shop_id}'")

    filter_formula = "AND(" + ", ".join(filter_conditions) + ")"
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}?filterByFormula={filter_formula}"

    # Fetch data from Airtable
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch data from Airtable"}), 500

    records = response.json().get("records", [])
    
    # Extract relevant data
    transactions = []
    total_bill = 0
    stock_totals = {}
    user_transactions = defaultdict(list)

    for record in records:
        fields = record["fields"]
        date = fields.get("date", "")
        user_id = fields.get("user_id", "Unknown User")
        stocks = fields.get("stocks", "").strip()
        quantity = fields.get("quantity_taken", 0)
        price = fields.get("price", 0)

        # Skip records with empty stocks
        if not stocks:
            continue

        # Append to transactions list
        transactions.append({
            "user_id": user_id,
            "date": date,
            "stocks": stocks,
            "quantity_taken": quantity,
            "price": price
        })

        # Calculate total bill
        total_bill += price

        # Track stock-wise totals
        if stocks in stock_totals:
            stock_totals[stocks] += quantity
        else:
            stock_totals[stocks] = quantity

        # Track transactions per user
        user_transactions[user_id].append({
            "date": date,
            "stocks": stocks,
            "quantity_taken": quantity,
            "price": price
        })

    # Sort transactions for each user by date
    for user_id in user_transactions:
        user_transactions[user_id] = sorted(user_transactions[user_id], key=itemgetter('date'))

    return jsonify({
        "transactions": transactions,
        "total_bill": total_bill,
        "stock_totals": stock_totals,
        "user_transactions": user_transactions
    })

@app.route("/committee/sales", methods=["GET"])
def get_committee_sales():
    shop_id = request.args.get('shop_id')
    year = request.args.get('year')
    month = request.args.get('month')

    if not (shop_id and year and month):
        return jsonify({"error": "Shop ID, Year and Month are required"}), 400

    filter_formula = f"AND({{shop_id}} = '{shop_id}', YEAR({{date}}) = {year}, MONTH({{date}}) = {month})"
    url = f"{AIRTABLE_URL}?filterByFormula={filter_formula}"
    
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch sales data from Airtable"}), 500

    records = response.json().get("records", [])
    
    stock_totals = {}
    total_sales = 0

    for record in records:
        fields = record["fields"]
        stocks = fields.get("stocks", "").strip()
        quantity = fields.get("quantity_taken", 0)
        price = fields.get("price", 0)

        if not stocks:
            continue

        if stocks in stock_totals:
            stock_totals[stocks] += quantity
        else:
            stock_totals[stocks] = quantity

        total_sales += price

    return jsonify({
        "stock_totals": stock_totals,
        "total_sales": total_sales
    })

@app.route("/committee/current-stock", methods=["GET"])
def get_current_stock():
    shop_id = request.args.get('shop_id')
    
    if not shop_id:
        return jsonify({"error": "Shop ID is required"}), 400

    try:
        # Fetch quantity_update details from the Goods table
        goods_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_GOODS_TABLE_NAME}?filterByFormula={{shop_id}}='{shop_id}'"
        goods_response = requests.get(goods_url, headers=HEADERS, timeout=10)
        
        if goods_response.status_code != 200:
            return jsonify({"error": "Failed to fetch goods data from Airtable"}), 500
        
        goods_records = goods_response.json().get("records", [])
        stock_quantities = defaultdict(float)
        
        for record in goods_records:
            fields = record.get("fields", {})
            stock_name = fields.get("stocks", "").strip().lower()
            quantity_update = float(fields.get("quantity_update", 0))
            if stock_name:
                stock_quantities[stock_name] += quantity_update

        # Fetch transactions for the shop_id and stocks
        transactions_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}?filterByFormula={{shop_id}}='{shop_id}'"
        transactions_response = requests.get(transactions_url, headers=HEADERS, timeout=10)
        
        if transactions_response.status_code != 200:
            return jsonify({"error": "Failed to fetch transactions data from Airtable"}), 500
        
        transactions_records = transactions_response.json().get("records", [])
        
        for record in transactions_records:
            fields = record.get("fields", {})
            stock_name = fields.get("stocks", "").strip().lower()
            quantity_taken = float(fields.get("quantity_taken", 0))
            if stock_name:
                stock_quantities[stock_name] -= quantity_taken

        # Prepare response data
        inventory_data = []
        for stock, quantity in stock_quantities.items():
            inventory_data.append({
                "stock_name": stock.capitalize(),
                "current_quantity": max(quantity, 0),  # Don't show negative values
                "is_low": quantity < 10  # Mark as low if less than 10kg
            })
        
        return jsonify({
            "current_stock": sorted(inventory_data, key=lambda x: x['stock_name'])
        })

    except requests.exceptions.RequestException as e:
        print(f"Network error: {str(e)}")
        return jsonify({"error": "Network error connecting to Airtable"}), 500
    except Exception as e:
        print(f"Error calculating current stock: {str(e)}")
        return jsonify({"error": "Server error processing stock data"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)