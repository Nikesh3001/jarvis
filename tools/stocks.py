import json
import re


class StockTool:
    def __init__(self):
        self._httpx = None

    @property
    def httpx(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    def get_stock_price(self, symbol):
        try:
            symbol = symbol.strip().upper()
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            r = self.httpx.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            data = r.json()
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = meta.get("regularMarketPrice", "N/A")
            prev_close = meta.get("chartPreviousClose", "N/A")
            currency = meta.get("currency", "USD")
            change = round(price - prev_close, 2) if isinstance(price, (int, float)) and isinstance(prev_close, (int, float)) else "N/A"
            pct = round((change / prev_close) * 100, 2) if isinstance(change, (int, float)) and prev_close else "N/A"
            return f"{symbol}: ${price} ({change:+}, {pct}%) [{currency}]"
        except Exception as e:
            try:
                url2 = f"https://finance.yahoo.com/quote/{symbol}"
                r2 = self.httpx.get(url2, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                price_m = re.search(r'data-price="([^"]+)"', r2.text)
                name_m = re.search(r'data-field="longName"[^>]*>([^<]+)', r2.text)
                name = name_m.group(1) if name_m else symbol
                price = price_m.group(1) if price_m else "N/A"
                return f"{name} ({symbol}): ${price}"
            except Exception:
                return f"Could not fetch data for '{symbol}'. Try a different symbol (e.g. AAPL, GOOGL, TSLA)"

    def search_stock(self, query):
        try:
            url = f"https://query1.finance.yahoo.com/v1/finance/search?q={__import__('urllib').parse.quote(query)}"
            r = self.httpx.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            data = r.json()
            quotes = data.get("quotes", [])
            if not quotes:
                return f"No stock results for '{query}'."
            results = []
            for q in quotes[:5]:
                sym = q.get("symbol", "?")
                name = q.get("longName", q.get("shortName", "?"))
                exch = q.get("exchange", "?")
                results.append(f"  {sym} — {name} ({exch})")
            return "Stock search results:\n" + "\n".join(results)
        except Exception as e:
            return f"Stock search error: {e}"

    def get_market_summary(self):
        try:
            indices = ["^GSPC", "^DJI", "^IXIC"]
            names = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "NASDAQ"}
            lines = []
            for sym in indices:
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                    r = self.httpx.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    data = r.json()
                    meta = data["chart"]["result"][0]["meta"]
                    price = meta.get("regularMarketPrice", "N/A")
                    prev = meta.get("chartPreviousClose", "N/A")
                    name = names.get(sym, sym)
                    if isinstance(price, (int, float)) and isinstance(prev, (int, float)):
                        chg = price - prev
                        pct = (chg / prev) * 100
                        lines.append(f"  {name}: {price:,.2f} ({chg:+,.2f}, {pct:+.2f}%)")
                    else:
                        lines.append(f"  {name}: {price}")
                except Exception:
                    lines.append(f"  {names.get(sym, sym)}: unavailable")
            return "Market Summary:\n" + "\n".join(lines)
        except Exception as e:
            return f"Market summary error: {e}"

    def get_tool_definitions(self):
        return [
            {"type": "function", "function": {"name": "get_stock_price", "description": "Stock price by symbol (AAPL, TSLA)", "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Symbol"}}, "required": ["symbol"]}}},
            {"type": "function", "function": {"name": "search_stock", "description": "Find ticker by company name", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Name"}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "get_market_summary", "description": "S&P 500, Dow Jones, NASDAQ", "parameters": {"type": "object", "properties": {}}}},
        ]

    def get_handler(self, name):
        handlers = {
            "get_stock_price": self.get_stock_price,
            "search_stock": self.search_stock,
            "get_market_summary": self.get_market_summary,
        }
        return handlers.get(name)
