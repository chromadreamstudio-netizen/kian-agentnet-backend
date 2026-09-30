import os
import re
import json
import time
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
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
        "version": "3.0.0 (Stealth & Semantic Markdown Enabled)"
    }

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
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York"
            )
            page = context.new_page()
            
            # 1. تفعيل طبقة التخفي لمنع حظر البوتات من مواقع مثل AliExpress
            stealth_sync(page)
            
            try:
                page.goto(url, timeout=45000, wait_until="networkidle")
            except Exception:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
            
            # 2. التفاعل الذكي: التمرير ببطء لتحميل الأسعار الديناميكية المخفية (Lazy Load)
            page.evaluate("""
                const scrollInterval = setInterval(() => { window.scrollBy(0, 500); }, 200);
                setTimeout(() => { clearInterval(scrollInterval); }, 3000);
            """)
            page.wait_for_timeout(4000) 
            
            html_content = page.content()
            browser.close()
            
            soup = BeautifulSoup(html_content, "html.parser")
            
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
            
            for element in soup(["script", "style", "noscript", "svg", "iframe"]):
                element.extract()
            
            # 3. التحويل الدلالي: تحويل الصفحة إلى Markdown للحفاظ على علاقة الأسعار بالعناوين
            clean_html = str(soup.body) if soup.body else str(soup)
            markdown_text = markdownify.markdownify(clean_html, heading_style="ATX")
            markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text).strip()
            
            return {
                "semantic_markdown": markdown_text[:40000],
                "meta_tags": meta_data,
                "structured_json_ld": json_ld_data
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
        
        Context provided is Semantic Markdown (which preserves tables, lists, and prices next to titles), Metadata, and hidden JSON-LD.
        
        Metadata: {json.dumps(execution_result["meta_tags"])}
        Hidden JSON-LD: {json.dumps(execution_result.get("structured_json_ld", []))}
        Semantic Markdown Corpus:
        {execution_result["semantic_markdown"]}
        
        Output strictly valid JSON without any markdown formatting wrappers.
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
        new_credits = current_credits - 1
        supabase.table("api_keys").update({"credits": new_credits}).eq("id", developer_record["id"]).execute()
        
        return {
            "status": "success",
            "model_used": used_model,
            "data": structured_payload
        }
    except Exception as e:
        return {"status": "fatal_error", "message": str(e)}