import os
import re
import json
import time
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
import markdownify
from supabase import create_client, Client

app = FastAPI(
    title="Kian AgentNet - Global Agentic Web Protocol",
    description="Foundational Infrastructure for AI-to-Web Interoperability",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")

SUPABASE_URL = "https://wexqgdkcwkzcrxgmxwkj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndleHFnZGtjd2t6Y3J4Z214d2tqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAwODUyODMsImV4cCI6MjEwNTY2MTI4M30.K7SS0Be1nNT-TMWp3021OfYiYsi7rM7f4h_3lrdN-2w"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class ProtocolRequest(BaseModel):
    url: str
    target_schema: str = "Extract core entities, prices, structured specifications, and metadata."

@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "Kian AgentNet Protocol Engine",
        "version": "3.0.0 (Stealth & Deep Scraping Enabled)"
    }

def find_price_regex(text: str) -> str | None:
    """متحقق متقدم لاستخراج صيغ الأسعار المختلفة والعملات"""
    patterns = [
        r'(?:US\s*|\$|€|£|¥|USD|EUR|GBP|SAR|AED|EGP)\s*(\d{1,5}(?:[\.,]\d{2})?)',
        r'(\d{1,5}(?:[\.,]\d{2})?)\s*(?:US\s*|\$|€|£|¥|USD|EUR|GBP|SAR|AED|EGP)',
        r'"(?:actMinPrice|minAmount|formattedAmount|price|salePrice|priceAmount)":"?(\$?[\d\.,]+)"?'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1) if match.lastindex else match.group(0)
            clean_val = re.sub(r'[^\d\.,]', '', val)
            if clean_val:
                return clean_val
    return None

def execute_browser_protocol(url: str) -> dict:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, 
                args=[
                    "--disable-blink-features=AutomationControlled", 
                    "--no-sandbox", 
                    "--disable-dev-shm-usage",
                    "--disable-web-security"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                }
            )
            page = context.new_page()
            
            stealth = Stealth()
            stealth.apply_stealth_sync(page)
            
            try:
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
            except Exception:
                page.goto(url, timeout=30000)
            
            # التمرير البطئي الشامل لتفعيل السكربتات والـ Lazy Load
            page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 400;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if(totalHeight >= scrollHeight || totalHeight > 3000){
                                clearInterval(timer);
                                window.scrollTo(0, 0);
                                resolve();
                            }
                        }, 150);
                    });
                }
            """)
            page.wait_for_timeout(3000) 
            
            raw_html = page.content()
            browser.close()
            
            soup = BeautifulSoup(raw_html, "html.parser")
            
            meta_data = {}
            for meta in soup.find_all("meta"):
                prop = meta.get("property") or meta.get("name")
                content = meta.get("content")
                if prop and content:
                    meta_data[str(prop)] = str(content).replace('"', "'")
            
            json_ld_data = []
            for script in soup.find_all("script", type="application/ld+json"):
                if script.string:
                    json_ld_data.append(script.string.strip())
            
            # استخراج أسعار أكواد السكربت المخفية في منصات التجزئة قبل تنظيف الـ HTML
            script_price_snippets = []
            for script in soup.find_all("script"):
                stext = script.string or ""
                if any(k in stext for k in ["runParams", "actMinPrice", "formatedAmount", "skuModule", "priceModule"]):
                    matches = re.findall(r'("(?:actMinPrice|formatedAmount|minAmount|discountPrice|price)":\s*"?[^"\}]+"?)', stext)
                    if matches:
                        script_price_snippets.extend(matches[:10])

            for element in soup(["script", "style", "noscript", "svg", "iframe"]):
                element.extract()
            
            clean_html = str(soup.body) if soup.body else str(soup)
            markdown_text = markdownify.markdownify(clean_html, heading_style="ATX")
            markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text).strip()
            
            return {
                "raw_html": raw_html,
                "semantic_markdown": markdown_text[:40000],
                "meta_tags": meta_data,
                "structured_json_ld": json_ld_data,
                "script_price_snippets": script_price_snippets
            }
    except Exception as e:
        return {"protocol_error": str(e)}

@app.post("/v1/gateway/execute")
def gateway_execute(payload: ProtocolRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key is missing.")
    
    if not GEMINI_KEY or GEMINI_KEY == "PUT_YOUR_GEMINI_KEY_HERE":
        return {"status": "fatal_error", "message": "Missing GEMINI_API_KEY"}
        
    try:
        key_res = supabase.table("api_keys").select("*").eq("api_key", x_api_key).eq("is_active", True).execute()
        if not key_res.data or len(key_res.data) == 0:
            raise HTTPException(status_code=403, detail="Invalid API Key.")
        
        developer_record = key_res.data[0]
        current_credits = developer_record["credits"]
        if current_credits <= 0:
            raise HTTPException(status_code=402, detail="Insufficient credits.")
        
        execution_result = execute_browser_protocol(payload.url)
        if "protocol_error" in execution_result:
            return {"status": "gateway_error", "message": execution_result["protocol_error"]}
            
        protocol_prompt = f"""
        You are the core intelligence processor of the Kian AgentNet Protocol (V3 Stealth Architecture). 
        Extract structured JSON matching exactly this schema instruction: "{payload.target_schema}"
        
        CRITICAL EXTRACTION INSTRUCTIONS:
        1. NEVER return null or empty for "price" if ANY price numeric/currency hint exists in Metadata, Script Price Hints, JSON-LD or Markdown.
        2. If multiple prices exist, pick the active sale/discount price or lowest min price.
        3. Return clean price values or formatted numbers.
        
        Metadata: {json.dumps(execution_result["meta_tags"])}
        Hidden JSON-LD: {json.dumps(execution_result.get("structured_json_ld", []))}
        Script Price Hints: {json.dumps(execution_result.get("script_price_snippets", []))}
        Semantic Markdown Corpus:
        {execution_result["semantic_markdown"]}
        
        Output strictly valid JSON matching target schema without markdown wrappers.
        """
        
        candidate_models = [
            'gemini-3.8-flash',
            'gemini-3.6-flash',
            'gemini-3.5-flash',
            'gemini-3.5-flash-lite'
        ]
        
        response = None
        used_model = None
        client = genai.Client(api_key=GEMINI_KEY)

        for model_name in candidate_models:
            for attempt in range(3): 
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=protocol_prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    if res and res.text:
                        response = res
                        used_model = model_name
                        break
                except Exception as model_err:
                    if "503" in str(model_err): 
                        time.sleep(3)
                    else:
                        break
            if response:
                break 

        if not response:
            return {"status": "gateway_error", "message": "All models are currently overloaded. Please try again."}
        
        structured_payload = json.loads(response.text)
        
        # === مسار طوارئ رباعي لتصحيح السعر في حال إرجاع null ===
        if isinstance(structured_payload, dict):
            for key, val in list(structured_payload.items()):
                if "price" in key.lower() and (val is None or str(val).lower() in ["null", "none", ""]):
                    meta_tags = execution_result.get("meta_tags", {})
                    
                    # 1. فحص الـ Meta Tags
                    fallback_price = (
                        meta_tags.get("og:price:amount") or 
                        meta_tags.get("product:price:amount") or 
                        meta_tags.get("price") or
                        meta_tags.get("twitter:data1")
                    )
                    
                    # 2. فحص مقاطع الجافاسكريبت المحقونة
                    if not fallback_price and execution_result.get("script_price_snippets"):
                        snippets_text = " ".join(execution_result["script_price_snippets"])
                        fallback_price = find_price_regex(snippets_text)
                        
                    # 3. فحص نص الـ Markdown
                    if not fallback_price:
                        fallback_price = find_price_regex(execution_result.get("semantic_markdown", ""))
                        
                    # 4. فحص كود الـ HTML الخالص
                    if not fallback_price:
                        fallback_price = find_price_regex(execution_result.get("raw_html", ""))
                        
                    if fallback_price:
                        structured_payload[key] = fallback_price

        new_credits = current_credits - 1
        supabase.table("api_keys").update({"credits": new_credits}).eq("id", developer_record["id"]).execute()
        
        return {
            "status": "success",
            "model_used": used_model,
            "data": structured_payload
        }
    except Exception as e:
        return {"status": "fatal_error", "message": str(e)}