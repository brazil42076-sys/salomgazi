from flask import Flask, request, jsonify
import asyncio
import aiohttp
import json
import re
import random
import os
import time
from urllib.parse import urlparse

app = Flask(__name__)

# ============================================================
# YOUR EXISTING SHOPIFY CHECKER FUNCTIONS GO HERE
# (process_card, fetch_products, etc. from your original api.py)
# ============================================================

# [PASTE YOUR ENTIRE EXISTING CODE HERE - all the QUERY_* variables and functions]
# Including: process_card, fetch_products, extract_between, pick_addr, Utils class, etc.

# ============================================================
# MAIN ENDPOINT (Matches old API format exactly)
# ============================================================

@app.route('/')
def api_root():
    start_time = time.time()
    
    try:
        # Get parameters - old format has no parameter name for card
        # Example: ?5455122802569146|12|26|543&url=...&proxy=...
        
        card = None
        for key, value in request.args.items():
            if '|' in value and len(value.split('|')) >= 4:
                card = value
                break
        
        # Also support new format with 'cc' parameter
        if not card:
            card = request.args.get('cc')
        
        site = request.args.get('url') or request.args.get('site')
        proxy = request.args.get('proxy')
        
        if not card or not site:
            return jsonify({
                "Response": "Missing card or URL parameter",
                "CC": card or "",
                "Price": "-",
                "Gate": "Unknown",
                "Site": site or "",
                "Charged": "False",
                "Approved": "False",
                "Time": f"{time.time() - start_time:.1f}s"
            })
        
        # Parse card
        parts = card.split('|')
        if len(parts) < 4:
            return jsonify({
                "Response": "Invalid card format. Use: CC|MM|YY|CVV",
                "CC": card,
                "Price": "-",
                "Gate": "Unknown",
                "Site": site,
                "Charged": "False",
                "Approved": "False",
                "Time": f"{time.time() - start_time:.1f}s"
            })
        
        cc = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        if len(yy) == 2:
            yy = "20" + yy
        
        if not site.startswith('http'):
            site = 'https://' + site
        
        # Call the Shopify checker
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success, message, gateway, price, currency = loop.run_until_complete(
                process_card(cc, mm, yy, cvv, site, None, proxy)
            )
        except Exception as e:
            success = False
            message = str(e)[:100]
            gateway = "Unknown"
            price = "0"
            currency = "USD"
        finally:
            loop.close()
        
        # Determine response message
        if success and message == "ORDER_PLACED":
            response_msg = "ORDER_PLACED"
            charged = "True"
            approved = "True"
        elif success and "CARD_DECLINED" in message:
            response_msg = "CARD_DECLINED"
            charged = "False"
            approved = "False"
        elif success and "3DS" in message:
            response_msg = "3DS_REQUIRED"
            charged = "False"
            approved = "False"
        elif success:
            response_msg = message[:100]
            charged = "False"
            approved = "True" if "APPROVED" in message else "False"
        else:
            response_msg = message[:100] if message else "CARD_DECLINED"
            charged = "False"
            approved = "False"
        
        # Format price
        try:
            price_float = float(price)
            price_str = f"{price_float:.2f} {currency}"
        except:
            price_str = f"{price} {currency}" if price != "0" else "0.00 USD"
        
        # Calculate time taken
        elapsed = time.time() - start_time
        
        # Return EXACT same format as old API
        return jsonify({
            "Response": response_msg,
            "CC": card,
            "Price": price_str,
            "Gate": gateway if gateway else "Shopify Payments",
            "Site": site,
            "Charged": charged,
            "Approved": approved,
            "Time": f"{elapsed:.1f}s"
        })
        
    except Exception as e:
        elapsed = time.time() - start_time
        return jsonify({
            "Response": f"ERROR: {str(e)[:100]}",
            "CC": request.args.get('cc', ''),
            "Price": "-",
            "Gate": "Unknown",
            "Site": request.args.get('url', request.args.get('site', '')),
            "Charged": "False",
            "Approved": "False",
            "Time": f"{elapsed:.1f}s"
        })

# ============================================================
# SHOPIFY ENDPOINT (Alternative format)
# ============================================================

@app.route('/shopify', methods=['GET'])
def shopify_checker():
    start_time = time.time()
    
    try:
        cc_string = request.args.get('cc')
        site = request.args.get('site') or request.args.get('url')
        proxy = request.args.get('proxy')
        
        if not cc_string or not site:
            return jsonify({
                "Response": "Missing cc or site parameter",
                "CC": cc_string or "",
                "Price": "-",
                "Gate": "Unknown",
                "Site": site or "",
                "Charged": "False",
                "Approved": "False",
                "Time": f"{time.time() - start_time:.1f}s"
            })
        
        parts = cc_string.split('|')
        if len(parts) < 4:
            return jsonify({
                "Response": "Invalid card format. Use: CC|MM|YY|CVV",
                "CC": cc_string,
                "Price": "-",
                "Gate": "Unknown",
                "Site": site,
                "Charged": "False",
                "Approved": "False",
                "Time": f"{time.time() - start_time:.1f}s"
            })
        
        cc = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        if len(yy) == 2:
            yy = "20" + yy
        
        if not site.startswith('http'):
            site = 'https://' + site
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success, message, gateway, price, currency = loop.run_until_complete(
                process_card(cc, mm, yy, cvv, site, None, proxy)
            )
        finally:
            loop.close()
        
        if success and message == "ORDER_PLACED":
            response_msg = "ORDER_PLACED"
        elif success and "CARD_DECLINED" in message:
            response_msg = "CARD_DECLINED"
        elif success and "3DS" in message:
            response_msg = "3DS_REQUIRED"
        else:
            response_msg = message[:100] if message else "CARD_DECLINED"
        
        try:
            price_float = float(price)
            price_str = f"{price_float:.2f} {currency}"
        except:
            price_str = f"{price} {currency}"
        
        elapsed = time.time() - start_time
        
        return jsonify({
            "Response": response_msg,
            "CC": cc_string,
            "Price": price_str,
            "Gate": gateway if gateway else "Shopify Payments",
            "Site": site,
            "Charged": "True" if response_msg == "ORDER_PLACED" else "False",
            "Approved": "True" if "APPROVED" in message else "False",
            "Time": f"{elapsed:.1f}s"
        })
        
    except Exception as e:
        elapsed = time.time() - start_time
        return jsonify({
            "Response": f"ERROR: {str(e)[:100]}",
            "CC": request.args.get('cc', ''),
            "Price": "-",
            "Gate": "Unknown",
            "Site": request.args.get('site', ''),
            "Charged": "False",
            "Approved": "False",
            "Time": f"{elapsed:.1f}s"
        })

# ============================================================
# RUN THE APP
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)