import logging
import traceback
import subprocess
import time
from typing import Any, Dict
from app.utils import gemini_query

try:
    import uiautomator2 as u2
except ImportError:
    u2 = None

def get_tool_definitions(tracker) -> Dict[str, Any]:
    """
    Returns the custom tools dictionary expected by DroidAgent.
    We inject the 'tracker' instance into these closures.
    """

    def safe_log_price(app_name: str, price_text: str = None, rating: Any = None, title: str = None, asin: str = None, **kwargs):
        logging.debug("Tool: log_price app=%s title=%s price=%s", app_name, title, price_text)
        try:
            # Filter sponsored items
            combined = (str(title or '') + ' ' + str(price_text or '')).lower()
            if any(x in combined for x in ['sponsored', 'ad', 'advertisement', 'promoted']):
                return "skipped_sponsored"
            return tracker.log_price(app_name, price_text, rating=rating, title=title)
        except Exception as e:
            logging.error(traceback.format_exc())
            return {"error": str(e)}

    def safe_compare_and_decide(budget: str = None, **kwargs):
        logging.debug("Tool: compare_and_decide budget=%s", budget)
        try:
            return tracker.compare_and_decide(budget=budget)
        except Exception as e:
            logging.error(traceback.format_exc())
            return {"error": str(e)}

    def safe_ask_gemini(prompt: str = None, **kwargs):
        try:
            return gemini_query(prompt or '')
        except Exception as e:
            logging.error(traceback.format_exc())
            return {"error": str(e)}

    def safe_ask_user(prompt: str = None, **kwargs):
        try:
            return input((prompt or "Input required: "))
        except Exception as e:
            logging.error(traceback.format_exc())
            return {"error": str(e)}

    def safe_prepare_cart(app_name: str, title: str = None, device_serial: str = None, wait: float = 1.0, **kwargs):
        logging.info("Tool: prepare_cart app=%s title=%s", app_name, title)
        if not title:
            return {"error": "No product title provided."}
        
        pkgs = {
            'amazon': ['com.amazon.mShop.android.shopping', 'in.amazon.mShop.android.shopping'],
            'flipkart': ['com.flipkart.android']
        }.get((app_name or '').lower(), [])

        if u2 is None:
            return {"error": f"uiautomator2 missing. Please add '{title}' manually."}

        try:
            d = u2.connect(device_serial) if device_serial else u2.connect()
            
            # Start App
            for pkg in pkgs:
                try:
                    d.app_start(pkg)
                    break
                except Exception as e:
                    logging.debug(f"Failed to start {pkg}: {e}")
                    continue
            time.sleep(wait)

            # Search Interaction
            try:
                if d(resourceIdMatches='.*search.*').exists(timeout=1):
                    d(resourceIdMatches='.*search.*').click()
                elif d(textMatches='(?i)search').exists(timeout=1):
                    d(textMatches='(?i)search').click()
            except Exception as e:
                logging.debug(f"Search interaction failed: {e}")

            # ADB Input (Faster/Reliable)
            try:
                safe_text = str(title)
                safe_text = safe_text.replace('%', '')
                safe_text = safe_text.replace(' ', '%s')
                cmd_base = ['adb'] + (['-s', device_serial] if device_serial else [])
                subprocess.run(cmd_base + ['shell', 'input', 'text', safe_text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                subprocess.run(cmd_base + ['shell', 'input', 'keyevent', '66'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False) # Enter
                time.sleep(wait)
            except Exception as e:
                logging.debug('ADB input failed: %s', e)

            # Add to Cart Logic
            added = False
            try:
                if d(resourceIdMatches='.*result.*').exists(timeout=1):
                    d(resourceIdMatches='.*result.*')[0].click()
                elif d(className='android.widget.FrameLayout').exists(timeout=1):
                    d(className='android.widget.FrameLayout')[0].click()
                
                time.sleep(0.6)
                
                if d(textMatches='(?i)add to cart').exists(timeout=2):
                    d(textMatches='(?i)add to cart').click()
                    added = True
                elif d(resourceIdMatches='.*add_to_cart.*').exists(timeout=1):
                    d(resourceIdMatches='.*add_to_cart.*').click()
                    added = True
            except Exception: 
                pass

            return {"ok": bool(added), "added": added, "note": "Attempted add to cart via UIAutomator."}
        except Exception as e:
            return {"error": str(e)}

    def safe_mark_failed_open(app_name: str, identifier: str = None, **kwargs):
        return tracker.mark_failed_open(app_name, identifier)

    def safe_should_try(identifier: str = None, **kwargs):
        return tracker.should_try(identifier)

    def safe_next_candidate(app_name: str = None, identifier: str = None, budget: str = None, **kwargs):
        return tracker.next_after_failed(app_name or '', identifier or '', budget=budget)

    # Return the dictionary mapping
    return {
        "log_price": {
            "arguments": ["app_name", "price_text", "rating", "title"],
            "description": "Save the price found. Pass raw text like '₹14,999', rating '4.3', title.",
            "function": safe_log_price
        },
        "compare_and_decide": {
            "arguments": ["budget"],
            "description": "Compare prices and decide which app to buy from.",
            "function": safe_compare_and_decide
        },
        "ask_gemini": {
            "arguments": ["prompt"],
            "description": "Ask Gemini (LLM) for assistance.",
            "function": safe_ask_gemini
        },
        "ask_user": {
            "arguments": ["prompt"],
            "description": "Ask the operator for input.",
            "function": safe_ask_user
        },
        "prepare_cart": {
            "arguments": ["app_name", "title"],
            "description": "Search product and add to cart (best-effort).",
            "function": safe_prepare_cart
        },
        "mark_failed_open": {
            "arguments": ["app_name", "identifier"],
            "description": "Record failed product open.",
            "function": safe_mark_failed_open
        },
        "should_try": {
            "arguments": ["identifier"],
            "description": "Check if product should be tried.",
            "function": safe_should_try
        },
        "next_candidate": {
            "arguments": ["app_name", "identifier", "budget"],
            "description": "Get next best candidate after a failure.",
            "function": safe_next_candidate
        }
    }