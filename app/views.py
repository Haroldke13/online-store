import os
import requests
import base64
import json
from flask import Blueprint, render_template, flash, redirect, request, jsonify, url_for,session
from flask_login import login_required, current_user
from sqlalchemy import or_
from .models import Product, Cart, Order,Customer
from .forms import ShopItemsForm,OrderForm
from faker import Faker
from . import db
from datetime import datetime
from dotenv import load_dotenv
import logging
import random
from requests.auth import HTTPBasicAuth
from flask_wtf import FlaskForm

faker = Faker()

# Load environment variables
load_dotenv()


PAYPAL_CLIENT_ID =  'AdZ38dWwRg-vOQxAjv_ZAXDRp2K6xhm2w55BwnBVW8wH9jHKZKC3BYosJqqOZ1m0cs4z9U5yHc-IxefZ'
PAYPAL_CLIENT_SECRET ='EH3ywSuqZTBoUQP9HEEOTGH7UfjPR2eGs3eVWcl1qeb3bw1q_6Cs1RDPyd-Kfl4pB0gdswzR3iFFL2UD'

PAYPAL_API_URL = "https://api.sandbox.paypal.com"


SECRET_KEY = 'do_not_show_this_to_anyone_100'
SQLALCHEMY_DATABASE_URI = 'sqlite:///database.sqite3'
SQLALCHEMY_TRACK_MODIFICATIONS = False
CORS_HEADERS = 'Content-Type'







views = Blueprint('views', __name__)


#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------


def get_access_token():
    url = f"{PAYPAL_API_URL}/v1/oauth2/token"
    data = {"grant_type": "client_credentials"}
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}
    
    try:
        response = requests.post(url, data=data, headers=headers, auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET))
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.RequestException as e:
        print(f"Error obtaining PayPal access token: {e}")
        return None

def create_order(access_token, total):
    url = f"{PAYPAL_API_URL}/v2/checkout/orders"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    order_data = {
        "intent": "CAPTURE",
        "purchase_units": [{"amount": {"currency_code": "USD", "value": str(total)}}],
        "application_context": {
            "return_url": url_for('views.payment_success', _external=True),
            "cancel_url": url_for('views.payment_cancel', _external=True)
        }
    }
    
    try:
        response = requests.post(url, json=order_data, headers=headers)
        response.raise_for_status()
        return response.json().get('id')
    except requests.RequestException as e:
        print(f"Error creating PayPal order: {e}")
        return None

def capture_payment(access_token, order_id):
    url = f"{PAYPAL_API_URL}/v2/checkout/orders/{order_id}/capture"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error capturing PayPal payment: {e}")
        return None





#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

@views.route('/cart')
@login_required
def cart():
    cart = Cart.query.filter_by(customer_link=current_user.id).all()
    amount = sum(int(item.product.current_price) * item.quantity for item in cart)  # Ensure amount is treated as an integer
    total = amount + 200  # Add shipping cost

    # Ensure correct image path is set for each cart item
    for item in cart:
        item.product.product_picture = url_for('views.media', filename=item.product.product_picture)

    return render_template('cart.html', cart=cart, amount=amount, total=total)



@views.route('/add-to-cart/<int:item_id>')
@login_required
def add_to_cart(item_id):
    item_to_add = Product.query.get(item_id)
    item_exists = Cart.query.filter_by(product_link=item_id, customer_link=current_user.id).first()
    if item_exists:
        try:
            item_exists.quantity = item_exists.quantity + 1
            db.session.commit()
            flash(f' Quantity of { item_exists.product.product_name } has been updated')
            return redirect(request.referrer)
        except Exception as e:
            print('Quantity not Updated', e)
            flash(f'Quantity of { item_exists.product.product_name } not updated')
            return redirect(request.referrer)

    new_cart_item = Cart()
    new_cart_item.quantity = 1
    new_cart_item.product_link = item_to_add.id
    new_cart_item.customer_link = current_user.id

    try:
        db.session.add(new_cart_item)
        db.session.commit()
        flash(f'{new_cart_item.product.product_name} added to cart')
    except Exception as e:
        print('Item not added to cart', e)
        flash(f'{new_cart_item.product.product_name} has not been added to cart')

    return redirect(request.referrer)



@views.route('/delete-from-cart/<int:item_id>', methods=['POST'])
@login_required
def delete_from_cart(item_id):
    item_to_remove = Cart.query.filter_by(product_link=item_id, customer_link=current_user.id).first()
    
    if item_to_remove:
        db.session.delete(item_to_remove)
        db.session.commit()
        flash('Item removed from cart', 'success')
    else:
        flash('Item not found in cart', 'error')

    return redirect(url_for('views.cart'))  # Redirect back to cart



#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------


@views.route('/handle_payments', methods=['POST'])
@login_required
def handle_payments():
    try:
        product_id = request.form.get('product_id')
        product_name = request.form.get('product_name')
        product_price = request.form.get('product_price')
        
        access_token = get_access_token()
        if not access_token:
            flash("Failed to connect to PayPal. Please try again later.", "danger")
            return redirect(url_for('views.payment'))
        
        order_data = {
            'intent': 'CAPTURE',
            'purchase_units': [
                {
                    'amount': {
                        'currency_code': 'USD',
                        'value': product_price,
                        'breakdown': {
                            'item_total': {
                                'currency_code': 'USD',
                                'value': product_price
                            }
                        }
                    }
                }
            ],
            'application_context': {
                'return_url': url_for('views.payment_success', _external=True),
                'cancel_url': url_for('views.payment_cancel', _external=True)
            }
        }
        
        order_id = create_order(access_token, order_data)
        if not order_id:
            flash("Failed to create PayPal order. Please try again.", "danger")
            return redirect(url_for('views.payment'))
        
        return redirect(f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}")
    
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('views.payment'))




@views.route('/payment_success')
@login_required
def payment_success():
    order_id = request.args.get('token')
    access_token = get_access_token()
    
    if not access_token:
        flash("Failed to connect to PayPal.", "danger")
        return redirect(url_for('views.payment_cancel'))
    
    capture_response = capture_payment(access_token, order_id)
    if not capture_response:
        flash("Failed to capture payment.", "danger")
        return redirect(url_for('views.payment_cancel'))
    
    order = Order.query.filter_by(payment_id=order_id).first()
    if order:
        order.status = "Paid"
        db.session.commit()
    
    flash('Payment successful!', 'success')
    return render_template('payment_success.html')

@views.route('/payment_cancel')
@login_required
def payment_cancel():
    flash("Payment was canceled.", "warning")
    return redirect(url_for('views.cart'))

@views.route('/webhook', methods=['POST'])
def paypal_webhook():
    payload = request.get_json()
    if payload and payload.get("event_type") == "PAYMENT.CAPTURE.COMPLETED":
        payment_id = payload.get("resource", {}).get("id")
        order = Order.query.filter_by(payment_id=payment_id).first()
        if order:
            order.status = "Paid"
            db.session.commit()
    return jsonify({"status": "ok"}), 200


@views.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    order_id = request.args.get('token')
    access_token = get_access_token()
    
    if not access_token:
        flash("Failed to connect to PayPal.", "danger")
        return redirect(url_for('views.payment_cancel'))
    
    capture_response = capture_payment(access_token, order_id)
    if not capture_response:
        flash("Failed to capture payment.", "danger")
        return redirect(url_for('views.payment_cancel'))
    
    order = Order.query.filter_by(payment_id=order_id).first()
    if order:
        order.status = "Paid"
        db.session.commit()
    
    flash('Payment successful!', 'success')
    return render_template('payment_success.html')

#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------


@views.route('/')
def home():

    items = Product.query.filter_by(flash_sale=True)

    return render_template('home.html', items=items, cart=Cart.query.filter_by(customer_link=current_user.id).all()if current_user.is_authenticated else [])



@views.route('/orders')
@login_required
def order():
    orders = Order.query.filter_by(customer_link=current_user.id).all()
    return render_template('orders.html', orders=orders)

"""@app.route('/orders')
def orders():
    orders = Order.query.all()  # Fetch all orders from the database
    return render_template('orders.html', orders=orders)"""










#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------




# Load environment variables
load_dotenv()

MPESA_CONSUMER_KEY="qHh6YOPbkv5g1absVTrmWDFkA8Oy1UXi4fGrdcrGawlIcGAF"

MPESA_CONSUMER_SECRET="wUNIe8ouaJI9TUfVbzLGtB43j8WLVRJQaZtrQIxo46uKX2DVBsA2ZCbYyenhWHvF"

MPESA_SHORTCODE="174379"

MPESA_PASSKEY="bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"

MPESA_CALLBACK_URL="https://ecommerce-ts8m.onrender.com/mpesa/callback"


def get_mpesa_access_token():
    try:
        # M-Pesa URL for token generation
        url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        
        # Encode the credentials in base64
        credentials = f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

        # Prepare the headers with the encoded credentials
        headers = {
            'Authorization': f'Basic {encoded_credentials}'
        }

        # Send the GET request to M-Pesa API to get the access token
        response = requests.get(url, headers=headers)
        
        # Print out the raw response for debugging purposes (mimicking your direct request)
        print(response.text.encode('utf8'))

        # Raise an exception for any HTTP error responses
        response.raise_for_status()

        # Extract the access token from the response JSON
        access_token = response.json().get("access_token")
        if access_token:
            logging.info("Successfully obtained M-Pesa access token.")
            return access_token
        else:
            logging.error("Access token not found in the response.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error obtaining M-Pesa token: {e}")
        return None


@views.route("/mpesa/stk_push", methods=["POST","GET"])
@login_required
def stk_push():
    """Initiate M-Pesa STK Push Payment."""
    if request.content_type != "application/json":
        return jsonify({"error": "Content-Type must be application/json"}), 415

    try:
        data = request.get_json()
        phone_number = data.get("phone_number")
        amount = data.get("amount")

        # ✅ Format and validate phone number
        
        if not phone_number:
            return jsonify({"error": "Enter a valid M-Pesa phone number (07XXXXXXXX or 2547XXXXXXXX)."}), 400

        # ✅ Validate amount
        if not amount or not str(amount).isdigit() or float(amount) <= 0:
            return jsonify({"error": "Invalid total amount."}), 400

        # ✅ Convert amount to an integer
        amount = int(float(amount))

         # ✅ Get M-Pesa Access Token
        access_token = get_mpesa_access_token()
        if not access_token:
            return jsonify({"error": "Failed to obtain M-Pesa access token"}), 500

        # ✅ Generate M-Pesa STK Push Payload
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}".encode()).decode()

        stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

        stk_push_payload = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": MPESA_CALLBACK_URL,
            "AccountReference": "OnlineStore",
            "TransactionDesc": "Payment for Order"
        }

        # ✅ Send STK Push Request
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        response = requests.post(stk_push_url, json=stk_push_payload, headers=headers)
        response.raise_for_status()  # Raise exception for any HTTP error

        # ✅ Parse response and return appropriate response
        response_data = response.json()
        if response_data.get("ResponseCode") == "0":
            return jsonify({
                "success": True,
                "message": "STK Push sent. Check your phone.",
                "ResponseCode": response_data.get("ResponseCode"),
                "CheckoutRequestID": response_data.get("CheckoutRequestID")
            })
        else:
            logging.error(f"STK Push failed: {response_data}")
            return jsonify({"error": "Failed to send STK Push"}), 500

    except requests.exceptions.RequestException as e:
        logging.error(f"Error initiating STK Push: {e}")
        return jsonify({"error": "Failed to initiate STK Push"}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500



# Handle M-Pesa Callback
@views.route("/mpesa/callback", methods=["POST"])
def mpesa_callback():
    #Handle M-Pesa Payment Callback
    callback_data = request.get_json()
    logging.info(f"M-Pesa Callback Received: {callback_data}")

    try:
        if callback_data["Body"]["stkCallback"]["ResultCode"] == 0:
            amount = callback_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][0]["Value"]
            mpesa_receipt = callback_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][1]["Value"]
            phone_number = callback_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][4]["Value"]

            return jsonify({
                "success": True,
                "message": "Payment successful",
                "amount": amount,
                "mpesa_receipt": mpesa_receipt,
                "phone_number": phone_number
            })
        else:
            logging.error("Payment failed or cancelled by user.")
            return jsonify({"error": "Payment failed or cancelled by user"}), 400
    except KeyError as e:
        logging.error(f"Error processing callback data: {e}")
        return jsonify({"error": "Invalid callback data"}), 400

#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------------------------------------------------

#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------



@views.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        search_query = request.form.get('search')
        items = Product.query.filter(Product.product_name.ilike(f'%{search_query}%')).all()

        # Ensure correct image path is set for each product
        for item in items:
            item.product_picture = url_for('views.media', filename=item.product_picture)

        return render_template('search.html', items=items, cart=Cart.query.filter_by(customer_link=current_user.id).all()
                               if current_user.is_authenticated else [])

    return render_template('search.html')

# Categories
CATEGORIES = {
    "supermarket": [
        "Milk", "Bread", "Sugar", "Cereal", "Rice", "Eggs", "Cheese", "Butter", "Yogurt", "Juice", 
        "Flour", "Vegetables", "Fruits", "Meat", "Frozen Food", "Pasta", "Coffee", "Tea", "Snacks", "Canned Goods"
    ],
    "health_beauty": [
        "Lotion", "Shampoo", "Toothpaste", "Perfume", "Soap", "Deodorant", "Hair Gel", "Conditioner", 
        "Face Mask", "Makeup", "Toothbrush", "Hand Sanitizer", "Nail Polish", "Sunscreen", "Body Scrub", "Lip Balm"
    ],
    "home_office": [
        "Chair", "Desk", "Lamp", "Bookshelf", "File Cabinet", "Printer", "Scanner", "Notebooks", "Pen", 
        "Stapler", "Whiteboard", "Corkboard", "Organizer", "Computer Monitor", "Keyboard", "Mouse", "Paper Clips"
    ],
    "fashion": [
        "Shirt", "Dress", "Shoes","shoes","Ladies", "Hat", "Jacket", "Jeans", "Skirt", "Sweater", "T-shirt", "Scarf", 
        "Gloves", "Coat", "Boots", "Sneakers", "Belt", "Socks", "Blouse", "Shorts", "Pants", "Sunglasses"
    ],
    "electronics": [
        "Phone", "Laptop", "Headphones", "Speaker", "Smartwatch", "Tablet", "Camera", "Smart TV", "Router", 
        "Microwave", "Washing Machine", "Refrigerator", "Air Conditioner", "Drone", "Smart Bulb", "Game Console", 
        "Keyboard", "Mouse", "Charger", "Power Bank"
    ],
    "gaming": [
        "PS5", "Xbox", "Gaming Mouse", "Keyboard", "Monitor", "Gaming Chair", "Game Controller", "Gaming Headset", 
        "Console", "Gaming Laptop", "Graphics Card", "Gaming Router", "Gaming Speakers", "VR Headset", 
        "Gamepad", "Game Disk", "PC Game", "Video Game", "Action Figure", "Game Poster"
    ],
    "baby_products": [
        "Diapers", "Baby Formula", "Baby Wipes", "Baby Shampoo", "Baby Lotion", "Baby Clothes", "Baby Shoes", 
        "Stroller", "Car Seat", "Pacifier", "Baby Blanket", "Baby Bottle", "Teething Ring", "Baby Carrier", 
        "Baby Toys", "Baby Monitor", "Baby Food", "Nappy Cream", "Baby Bath", "Baby Books"
    ],
    "sporting_goods": [
        "Bicycle", "Tennis Racket", "Football", "Basketball", "Yoga Mat", "Running Shoes", "Swimwear", "Gym Bag", 
        "Dumbbells", "Kettlebells", "Tennis Balls", "Soccer Ball", "Football Helmet", "Hiking Boots", 
        "Baseball Glove", "Golf Clubs", "Fishing Rod", "Camping Tent", "Fishing Gear", "Jump Rope"
    ],
    "garden_outdoor": [
        "Lawn Mower", "Garden Tools", "Planters", "Outdoor Furniture", "Grill", "Patio Heater", "Umbrella", 
        "Fertilizer", "Gardening Gloves", "Watering Can", "Garden Hose", "Bird Feeder", "Outdoor Rug", "Trellis", 
        "Solar Lights", "Garden Statues", "Fire Pit", "Outdoor Cushion", "Deck Chairs", "Gazebo"
    ],
    "books": [
        "Fiction", "Non-Fiction", "Science", "Biography", "Fantasy", "Mystery", "Romance", "Horror", 
        "History", "Self-help", "Cookbooks", "Travel", "Children's Books", "Textbooks", "Graphic Novels", 
        "Poetry", "Philosophy", "Art", "Psychology", "Business"
    ],
    "automotive": [
        "Car Tires", "Engine Oil", "Car Battery", "Brake Pads", "Wipers", "Car Interior Accessories", "Car Exterior Accessories", 
        "Car Cleaning Supplies", "Air Fresheners", "Car Covers", "Jumper Cables", "Car Seats", "Floor Mats", 
        "Car GPS", "Car Audio System", "Rims", "Car Jack", "Fuel Additives", "Motorcycle Helmet", "Windshield Fluid"
    ]
}




@views.route('/search_random/<category>')
def search_random(category):
    """Search for products in a given category"""
    if category not in CATEGORIES:
        return jsonify({"error": "Invalid category"})

    # Get the list of items in the category
    category_items = CATEGORIES[category]

    # Search for products that match any item in the category (case-insensitive)
    items = Product.query.filter(
        or_(*[Product.product_name.ilike(f"%{item}%") for item in category_items])
    ).all()

    # Ensure correct image path is set for each product
    for item in items:
        item.product_picture = url_for('views.media', filename=item.product_picture)
        print("Product:", item.product_name, "Image Path:", item.product_picture)  # Debugging

    return render_template('search.html', items=items, category_items=category_items, category=category, 
                           cart=Cart.query.filter_by(customer_link=current_user.id).all() if current_user.is_authenticated else [])

#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------


AIRTEL_MONEY_CLIENT_ID="ce72420b-3508-40e7-974a-8adbe509bfe6"
AIRTEL_MONEY_CLIENT_SECRET="ce72420b-3508-40e7-974a-8adbe509bfe6"
AIRTEL_MONEY_API_URL="https://openapiuat.airtel.africa"
AIRTEL_MONEY_CALLBACK_URL="https://ecommerce-ts8m.onrender.com/airtelmoney/callback"
AIRTEL_MONEY_HASH_KEY="4dc91b70ce884c42ac6caa49b6de9aa"


import hashlib
import hmac




# Airtel Money Configs (Environment Variables)
AIRTEL_MONEY_CLIENT_ID = os.getenv("AIRTEL_MONEY_CLIENT_ID")
AIRTEL_MONEY_CLIENT_SECRET = os.getenv("AIRTEL_MONEY_CLIENT_SECRET")
AIRTEL_MONEY_API_URL = os.getenv("AIRTEL_MONEY_API_URL")
AIRTEL_MONEY_CALLBACK_URL = os.getenv("AIRTEL_MONEY_CALLBACK_URL")
AIRTEL_MONEY_HASH_KEY = os.getenv("AIRTEL_MONEY_HASH_KEY")

# Generate AES Key
AES_KEY = base64.b64encode(os.urandom(32)).decode()

# Logger Setup
logging.basicConfig(level=logging.DEBUG)


def generate_signature(payload, secret):
    """Generate HMAC-SHA256 signature"""
    message = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()


def get_airtel_money_access_token():
    """Function to obtain the Airtel Money access token"""
    url = f"{AIRTEL_MONEY_API_URL}/auth/oauth2/token"
    credentials = f"{AIRTEL_MONEY_CLIENT_ID}:{AIRTEL_MONEY_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}

    try:
        logging.debug(f"Requesting access token from: {url}")
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.RequestException as e:
        logging.error(f"Error obtaining Airtel Money access token: {e}")
        return None


@views.route("/airtel/pay", methods=["POST"])
def handle_airtel():
    try:
        data = request.get_json(force=True)

        access_token = get_airtel_money_access_token()
        if not access_token:
            return jsonify({"error": "Failed to obtain access token"}), 400

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Country": data["subscriber"]["country"],
            "X-Currency": data.get("transaction", {}).get("currency", ""),
            "Authorization": f"Bearer {access_token}",
            "x-signature": generate_signature(data, AIRTEL_MONEY_HASH_KEY),
            "x-key": AES_KEY,
        }

        url = f"{AIRTEL_MONEY_API_URL}/merchant/v2/payments/"
        response = requests.post(url, headers=headers, json=data)
        return jsonify(response.json()), response.status_code

    except Exception as e:
        logging.error(f"Error in Airtel Money payment: {e}")
        return jsonify({"error": str(e)}), 500


@views.route("/airtel-money/callback", methods=["POST"])
def airtel_money_callback():
    """Callback function to process Airtel Money's response"""
    data = request.get_json()
    received_signature = request.headers.get("x-signature")  # Airtel's signature

    if AIRTEL_MONEY_HASH_KEY:
        computed_signature = hmac.new(
            AIRTEL_MONEY_HASH_KEY.encode(),
            request.data,
            hashlib.sha256
        ).hexdigest()

        if computed_signature != received_signature:
            return jsonify({"error": "Invalid signature"}), 403  # Unauthorized

    logging.info(f"Received Airtel Money Callback: {data}")
    return jsonify({"message": "Callback received successfully"}), 200


def initiate_airtel_money_payment(access_token, phone_number, amount):
    """Function to initiate Airtel Money payment"""
    url = f"{AIRTEL_MONEY_API_URL}/merchant/v1/payments/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "reference": f"REF{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "subscriber": {
            "country": "UG",  # Change to your country code
            "currency": "KES",  # Change to your currency code
            "msisdn": phone_number
        },
        "transaction": {
            "amount": amount,
            "country": "UG",  # Change to your country code
            "currency": "KES",  # Change to your currency code
            "id": f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}"
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error initiating Airtel Money payment: {e}")
        return None
    
    
    
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

from werkzeug.utils import secure_filename
from flask import send_from_directory
import os

# Ensure UPLOAD_FOLDER is an absolute path


UPLOAD_FOLDER = os.path.join(os.getcwd(), 'media')

@views.route('/media/<path:filename>')
def media(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

    



ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}




def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@views.route('/add-shop-items', methods=['GET', 'POST'])
@login_required
def add_shop_item():
    form = ShopItemsForm()

    if form.validate_on_submit():
        product_name = form.product_name.data
        previous_price = form.previous_price.data
        current_price = form.current_price.data
        in_stock = form.in_stock.data
        product_picture = form.product_picture.data
        flash_sale = form.flash_sale.data

        # Handle file upload
        if product_picture and allowed_file(product_picture.filename):
            filename = secure_filename(product_picture.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            product_picture.save(file_path)

            # Store only the filename, not the full path
            saved_filename = filename  
        else:
            saved_filename = None  # If no file, store NULL

        # Create new product entry
        new_product = Product(
            product_name=product_name,
            previous_price=previous_price,
            current_price=current_price,
            in_stock=in_stock,
            product_picture=saved_filename,  # Save filename in the database
            flash_sale=flash_sale
        )

        db.session.add(new_product)
        db.session.commit()

        flash("Product added successfully!", "success")
        return redirect(url_for('views.add_shop_item'))

    return render_template('add_shop_items.html', form=form)
    
@views.route('/admin')
def admin():
    return render_template('admin.html')


@views.route('/customers')
def customers():
    customers = Customer.query.all()  # Fetch all customers from the database
    return render_template('customers.html', customers=customers)

@views.route('/update-order/<int:order_id>', methods=['GET', 'POST'])
def update_order(order_id):
    # Fetch the order by ID, or return a 404 if not found
    order = Order.query.get_or_404(order_id)
    
    form = OrderForm()  # Assuming you're using a WTForms form
    
    # Handle form submission to update order status
    if form.validate_on_submit():
        try:
            order.status = form.order_status.data  # Set the new status
            db.session.commit()  # Commit changes to the database
            flash("Order updated successfully!", "success")
            return redirect(url_for('views.order'))  # Redirect to orders page
        except Exception as e:
            flash(f"Error updating the order: {e}", "danger")
            return redirect(url_for('views.order'))

    # Render the order update template if the form is not submitted
    return render_template('order_update.html', form=form, order=order)



@views.route('/shop-items')
def shop_items():
    try:
        items = Product.query.all()  # Fetch all shop items from the database
        if not items:
            flash('No shop items available', 'info')  # Optional flash message
        return render_template('shop_items.html', items=items)
    except Exception as e:
        flash(f"An error occurred while fetching shop items: {e}", 'danger')
        return redirect(url_for('views.home'))  # or wherever you want to redirect on error


@views.route('/delete-item/<int:item_id>', methods=['POST', 'GET'])
def delete_item(item_id):
    try:
        item = Product.query.get_or_404(item_id)  # Find the item or 404
        db.session.delete(item)  # Delete the item from the database
        db.session.commit()  # Commit the transaction
        flash('Item successfully deleted', 'success')  # Flash success message
        return redirect(url_for('views.shop_items'))  # Redirect to the shop items page
    except Exception as e:
        flash(f"An error occurred: {e}", 'danger')
        return redirect(url_for('views.shop_items'))
