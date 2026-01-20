import re
import logging
import html
from typing import Dict, Any, List, Set, Optional
from app.utils import parse_budget

class PriceTracker:
    def __init__(self):
        # Stores a quick best price and a full list of observed items per app
        self.prices: Dict[str, float] = {}
        # items: {'amazon': [{'price': 1299.0, ...}], ...}
        self.items: Dict[str, List[Dict[str, Any]]] = {}
        self.failed_opens: Set[str] = set()

    def _norm_title(self, title: Any) -> str:
        if not title:
            return ''
        # Sanitize input to prevent XSS
        return html.escape(str(title).strip().lower())

    def log_price(self, app_name: str, price_text: str, rating: Any = None, title: str = None) -> str:
        logging.info("log_price called for app=%s title=%s price=%s", app_name, title, price_text)
        if price_text is None and rating is None and not title:
            return f"Error: No price, rating or title provided for {app_name}."

        clean_name = app_name.lower().strip()
        price_val = None
        def _parse_number(x):
            try:
                if x is None:
                    return None
                s = re.sub(r"[^0-9.]", "", str(x))
                return float(s) if s else None
            except (ValueError, TypeError):
                return None

        price_val = _parse_number(price_text)
        rating_val = _parse_number(rating)

        rec_title = html.escape(title or '(unknown)')
        record = {"price": price_val, "rating": rating_val, "title": rec_title, "raw_price": html.escape(str(price_text) if price_text else '')}
        self.items.setdefault(clean_name, []).append(record)

        if price_val is not None:
            prev = self.prices.get(clean_name)
            if prev is None or (price_val < prev):
                self.prices[clean_name] = price_val

        return f"Logged item for {app_name}: title={rec_title}, price={price_val}, rating={rating_val}"

    def _score_item(self, item: Dict[str, Any]) -> float:
        rating = item.get('rating') if item.get('rating') is not None else 0.0
        price = item.get('price') if item.get('price') is not None else 1e9
        try:
            score = float(rating) * 10000.0 - float(price)
        except Exception:
            score = float(rating) * 10000.0 - 1e9
        return score

    def choose_overall_best(self, budget: float = None, sample_size: int = 2) -> Optional[Dict[str, Any]]:
        candidates = []
        for app, items in self.items.items():
            if not items:
                continue
            sample = items[:sample_size]
            best_item = max(sample, key=self._score_item)
            score = self._score_item(best_item)
            candidates.append({"app": app, "item": best_item, "score": score})

        if not candidates:
            return None

        if budget is not None:
            filtered = [c for c in candidates if (c['item'].get('price') is None or c['item'].get('price') <= budget)]
            if filtered:
                candidates = filtered

        return max(candidates, key=lambda c: c['score'])

    def compare_and_decide(self, budget: str) -> Dict[str, Any]:
        if not self.items:
            return {"error": "No collected items."}

        try:
            clean_budget = float(budget) if isinstance(budget, (int, float)) else parse_budget(str(budget))
        except Exception as e:
            return {"error": f"Could not parse budget: {e}"}

        # Build per-app best among first 2 items
        per_app = {}
        for app, items in self.items.items():
            sample = items[:2]
            if not sample:
                continue
            per_app[app] = max(sample, key=self._score_item)

        if not per_app:
            return {"error": "No candidates found."}

        # Strategy: Lowest price first, fallback to score
        price_candidates = [(app, it.get('price')) for app, it in per_app.items() 
                           if it.get('price') is not None and it.get('price') <= clean_budget]
        
        if price_candidates:
            price_candidates = sorted(price_candidates, key=lambda x: x[1])
            chosen_app = price_candidates[0][0]
            chosen_item = per_app[chosen_app]
            chosen_score = self._score_item(chosen_item)
            reason_text = f"Selected by lower price: {chosen_item.get('price')} on {chosen_app}"
        else:
            winner = self.choose_overall_best(budget=clean_budget, sample_size=2)
            if not winner:
                return {"error": "Could not determine a best candidate."}
            chosen_app = winner.get('app')
            chosen_item = winner.get('item')
            chosen_score = winner.get('score')
            reason_text = f"Selected by composite score: {chosen_score} on {chosen_app}"

        price = chosen_item.get('price')
        
        if price is not None and price > clean_budget:
            return {"error": f"STOP: Cheapest found {price} on {chosen_app} exceeds budget {clean_budget}."}

        return {
            "app": chosen_app,
            "title": chosen_item.get('title'),
            "price": price,
            "rating": chosen_item.get('rating'),
            "score": chosen_score,
            "reason": reason_text
        }

    def mark_failed_open(self, app_name: str, identifier: str) -> str:
        if not identifier:
            return "Error: No product title provided."
        self.failed_opens.add(self._norm_title(identifier))
        return f"Marked '{identifier}' as failed to open for {app_name}."

    def should_try(self, identifier: str) -> bool:
        if not identifier:
            return True
        return self._norm_title(identifier) not in self.failed_opens

    def next_after_failed(self, app_name: str, identifier: str, budget: float = None) -> Dict[str, Any]:
        try:
            self.mark_failed_open(app_name, identifier)
        except Exception as e:
            logging.error(f"Error marking failed open: {e}")
            
        exclude = set(self.failed_opens)
        candidates = []
        
        for app, items in self.items.items():
            filtered = [it for it in items if not (it.get('title') and self._norm_title(it.get('title')) in exclude)]
            if not filtered: 
                continue
            best_item = max(filtered, key=self._score_item)
            score = self._score_item(best_item)
            candidates.append({"app": app, "item": best_item, "score": score})

        if not candidates:
            return {"error": "No candidates available after filtering failed items"}
            
        # Budget filter
        budget_val = float(budget) if budget else None
        if budget_val:
            filtered = [c for c in candidates if (c['item'].get('price') is None or c['item'].get('price') <= budget_val)]
            if filtered: candidates = filtered

        return max(candidates, key=lambda c: c['score'])