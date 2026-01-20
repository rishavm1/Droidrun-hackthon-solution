import asyncio
import logging
import traceback
import sys
from droidrun import DroidAgent
from app.tracker import PriceTracker
from app.tools import get_tool_definitions
from app.config import get_agent_config
from app.utils import parse_budget

import os
logging.basicConfig(level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper()))

async def main():
    print("--- [Droidrun Smart Shopper] ---")
    
    # 1. Get User Inputs (handle interruption)
    try:
        product_name = input("Enter Product Name: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        return

    if not product_name:
        print("Error: Product name is required.")
        return
        
    try:
        budget_raw = input("Enter Max Budget: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        return

    if not budget_raw:
        print("Error: Budget is required.")
        return

    # Validate budget early so we can fail fast
    try:
        budget_val = parse_budget(budget_raw)
    except Exception as e:
        print(f"Error parsing budget: {e}")
        return

    # Ask how many results to collect per platform
    try:
        results_raw = input("Enter number of results to collect per platform [default 2]: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        return

    if not results_raw:
        results_n = 2
    else:
        try:
            results_n = int(results_raw)
            if results_n < 1:
                print("Number must be at least 1")
                return
            # Cap to avoid excessive work
            if results_n > 20:
                results_n = 20
        except Exception as e:
            print(f"Invalid number provided: {e}")
            return

    print(f"\nMission: Buy '{product_name}' under {budget_raw}")
    print("Initializing Agent...")

    # 2. Setup Components
    tracker = PriceTracker()
    config = get_agent_config()
    custom_tools = get_tool_definitions(tracker)
    
    variables = {
        "product_name": product_name,
        "budget": budget_raw,
        "results_per_platform": results_n
    }

    # 3. Define Goal
    goal = f"""
    You are an automated shopping assistant. Your goal is to find the best price for "{product_name}".

    SIMPLE FLOW:
    1) Amazon: Search for "{product_name}". Collect the FIRST {results_n} non-sponsored results.
       For each non-sponsored product, log: log_price(app_name="Amazon", price_text="...", rating="...", title="...")
    2) Flipkart: Search for "{product_name}". Collect the FIRST {results_n} non-sponsored results.
       For each non-sponsored product, log: log_price(app_name="Flipkart", price_text="...", rating="...", title="...")
    3) Call tool: compare_and_decide(budget="{budget_raw}"). Use the returned dict.
    4) Open the chosen app, search for the chosen product TITLE. Open it and add to cart. STOP after adding to cart.
    5) If needed, call: ask_user(prompt="...").
    """

    # 4. Initialize Agent
    agent = DroidAgent(
        goal=goal,
        config=config,
        custom_tools=custom_tools,
        variables=variables
    )

    # 5. Run Execution
    try:
        result = await asyncio.wait_for(agent.run(), timeout=1800)
    except asyncio.TimeoutError:
        print("Error: Agent timed out.")
        return
    except Exception as e:
        logging.error(traceback.format_exc())
        print(f"Error: {e}")
        return

    # 6. After Execution: Print detailed table of collected items and add chosen product to cart
    def _print_items_table(items_dict):
        # Simple console table per platform
        for app, items in items_dict.items():
            print(f"\nPlatform: {app} - {len(items)} items")
            if not items:
                continue
            # Compute column widths
            idx_w = 3
            title_w = max(20, max((len(str(it.get('title') or '')) for it in items)))
            price_w = 10
            rating_w = 8
            hdr = f"{'#':<{idx_w}}  {'Title':<{title_w}}  {'Price':<{price_w}}  {'Rating':<{rating_w}}  Raw"
            print(hdr)
            print('-' * len(hdr))
            for i, it in enumerate(items, start=1):
                title = (it.get('title') or '')[:title_w]
                price = str(it.get('price') if it.get('price') is not None else it.get('raw_price') or '')
                rating = str(it.get('rating') or '')
                raw = str(it.get('raw_price') or '')
                print(f"{i:<{idx_w}}  {title:<{title_w}}  {price:<{price_w}}  {rating:<{rating_w}}  {raw}")

    # Print collected items
    print("\n=== Collected Items ===")
    _print_items_table(tracker.items)

    # Determine chosen product and reason (prefer agent's result, else compute)
    chosen = None
    prepare_resp = None
    chosen_reason = None

    if isinstance(result, dict) and result.get('app') and result.get('title'):
        chosen = result
        chosen_reason = result.get('reason') or result.get('error')
    else:
        try:
            chosen = tracker.compare_and_decide(budget_raw)
            # If compare_and_decide did not return a usable choice, fallback to composite scoring
            if isinstance(chosen, dict) and (chosen.get('error') or not chosen.get('title')):
                winner = tracker.choose_overall_best(budget=budget_val, sample_size=results_n)
                if winner:
                    chosen = {
                        'app': winner.get('app'),
                        'title': winner.get('item', {}).get('title'),
                        'price': winner.get('item', {}).get('price'),
                        'rating': winner.get('item', {}).get('rating'),
                        'reason': f"Fallback chosen by composite score ({winner.get('score')})"
                    }
                    chosen_reason = chosen.get('reason')
                else:
                    chosen = {'error': 'No suitable candidate found.'}
            else:
                # successful compare_and_decide
                if isinstance(chosen, dict):
                    chosen_reason = chosen.get('reason') or chosen.get('error')
        except Exception as e:
            chosen = {'error': f'Error determining choice: {e}'}

    # Attempt to prepare cart (add to cart) using the tool if available
    prepare_fn = None
    if isinstance(custom_tools, dict):
        prepare_entry = custom_tools.get('prepare_cart')
        if prepare_entry and callable(prepare_entry.get('function')):
            prepare_fn = prepare_entry.get('function')

    if isinstance(chosen, dict) and not chosen.get('error') and prepare_fn:
        try:
            prepare_resp = prepare_fn(app_name=chosen.get('app'), title=chosen.get('title'))
        except Exception as e:
            prepare_resp = {'error': f'Exception calling prepare_cart: {e}'}
    elif isinstance(chosen, dict) and chosen.get('error'):
        # nothing to do
        pass
    else:
        prepare_resp = {'error': 'prepare_cart tool not available or chosen product unknown.'}

    # Print chosen product and prepare_cart result
    print("\n=== Selected Product / Add to Cart Result ===")
    if isinstance(chosen, dict) and chosen.get('error'):
        print(f"No selection: {chosen.get('error')}")
    else:
        app_name = chosen.get('app') if isinstance(chosen, dict) else getattr(chosen, 'app', None)
        title = chosen.get('title') if isinstance(chosen, dict) else getattr(chosen, 'title', None)
        price = chosen.get('price') if isinstance(chosen, dict) else getattr(chosen, 'price', None)
        rating = chosen.get('rating') if isinstance(chosen, dict) else getattr(chosen, 'rating', None)
        print(f"Platform: {app_name}")
        print(f"Title: {title}")
        print(f"Price: {price}")
        print(f"Rating: {rating}")
        print(f"Reason: {chosen_reason}")

        if isinstance(prepare_resp, dict):
            if prepare_resp.get('ok') or prepare_resp.get('added'):
                print("\nProduct was added to cart successfully.")
                note = prepare_resp.get('note') or prepare_resp.get('message')
                if note:
                    print(f"Note: {note}")
            else:
                print("\nProduct was NOT added to cart.")
                err = prepare_resp.get('error') or prepare_resp.get('note') or str(prepare_resp)
                print(f"Details: {err}")
        else:
            print(f"\nAdd-to-cart response: {prepare_resp}")

    # 7. Final Report (support dict or object result)
    try:
        if isinstance(result, dict):
            success = result.get('success', False)
            reason = result.get('reason', result.get('error', '(no reason)'))
        else:
            success = getattr(result, 'success', False)
            reason = getattr(result, 'reason', getattr(result, 'error', '(no reason)'))

        # Consider cart addition as a success factor as well
        cart_added = isinstance(prepare_resp, dict) and (prepare_resp.get('ok') or prepare_resp.get('added'))
        if success or cart_added:
            print("\nMISSION ACCOMPLISHED")
            print(f"Outcome: {reason}")
        else:
            print(f"\nMISSION FAILED: {reason}")
    except Exception:
        logging.error(traceback.format_exc())
        print("\nMISSION FAILED: Unknown error processing result.")
        return
        
    # Debug info
    print("\nDebug: Collected items per platform:")
    for app, items in tracker.items.items():
        print(f" - {app}: {len(items)} items")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
    except RuntimeError:
        print("\nFailed to run main() - event loop issue")
        sys.exit(1)