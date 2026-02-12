import requests
import json

def get_access_token(client_id, client_secret):
    url = "https://api.sandbox.paypal.com/v1/oauth2/token"
    data = {"grant_type": "client_credentials"}
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}

    try:
        response = requests.post(url, data=data, headers=headers, auth=(client_id, client_secret))
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.RequestException as e:
        print(f"Error obtaining PayPal access token: {e}")
        return None

def create_order(access_token, order_data):
    url = "https://api.sandbox.paypal.com/v2/checkout/orders"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.post(url, json=order_data, headers=headers)
        response.raise_for_status()
        return response.json().get('id')
    except requests.RequestException as e:
        print(f"Error creating PayPal order: {e}")
        return None

def capture_payment(access_token, order_id):
    url = f"https://api.sandbox.paypal.com/v2/checkout/orders/{order_id}/capture"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error capturing PayPal payment: {e}")
        return None
