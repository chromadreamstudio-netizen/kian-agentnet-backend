import os
import re
import json
import time
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from supabase import create_client, Client

app = FastAPI(
    title="Kian AgentNet - Global Agentic Web Protocol",
    description="Foundational Infrastructure for AI-to-Web Interoperability",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# مفتاح Gemini
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# === إعدادات اتصال Supabase ===
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
        "version": "2.0.0",
        "interactive_docs": "http://127.0.0.1:8000/docs"
    }

def execute_browser_protocol(url: str) -> dict:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, 
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            page.goto(url, timeout=50000, wait_until="domcontentloaded")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight/2);")
            page.wait_for_timeout(3000)
            
            html_content = page.content()
            browser.close()
            
            soup = BeautifulSoup(html_content, "html.parser")
            
            meta_data = {}
            for meta in soup.find_all("meta"):
                prop = meta.get("property") or meta.get("name")
                content = meta.get("content")
                if prop and content:
                    meta_data[str(prop)] = str(content).replace('"', "'")
            
            for element in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "iframe", "button"]):
                element.extract()
            
            text = soup.get_text(separator=" | ", strip=True)
            text = re.sub(r'\|\s*\|', '|', text)
            
            return {
                "raw_dom_text": text[:15000],
                "meta_tags": meta_data
            }
    except Exception as e:
        return {"protocol_error": str(e)}

@app.post("/v1/gateway/execute")
def gateway_execute(payload: ProtocolRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key is missing. Please provide X-API-Key header.")
    
    if not GEMINI_KEY or GEMINI_KEY == "PUT_YOUR_GEMINI_KEY_HERE":
        return {"status": "fatal_error", "message": "Please set your real GEMINI_API_KEY environment variable in Render."}
        
    try:
        key_res = supabase.table("api_keys").select("*").eq("api_key", x_api_key).eq("is_active", True).execute()
        if not key_res.data or len(key_res.data) == 0:
            raise HTTPException(status_code=403, detail="Invalid or inactive API Key.")
        
        developer_record = key_res.data[0]
        current_credits = developer_record["credits"]
        if current_credits <= 0:
            raise HTTPException(status_code=402, detail="Insufficient credits.")
        
        execution_result = execute_browser_protocol(payload.url)
        if "protocol_error" in execution_result:
            return {
                "status": "gateway_error",
                "error_code": "TARGET_UNREACHABLE_OR_BLOCKED",
                "message": execution_result["protocol_error"]
            }
            
        raw_text = execution_result["raw_dom_text"]
        meta_tags = execution_result["meta_tags"]
        
        protocol_prompt = f"""
        You are the core intelligence processor of the Kian AgentNet Protocol. 
        Your mission is to translate unstructured human-readable web DOM text into a rigid, machine-executable JSON schema for AI Agents.
        
        Target Extraction Schema Instructions: "{payload.target_schema}"
        
        Page Metadata:
        {json.dumps(meta_tags)}
        
        Raw DOM Corpus:
        {raw_text}
        
        STRICT PROTOCOL RULES:
        - Output MUST be strictly a valid JSON object.
        - No markdown wrapping, no introductory text.
        """
        
        # النماذج الرسمية المستقرة في Google GenAI API
        candidate_models = [
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-2.0-flash-lite'
        ]
        
        response = None
        used_model = None
        errors_log = []
        client = genai.Client(api_key=GEMINI_KEY)

        for model_name in candidate_models:
            for attempt in range(2): 
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=protocol_prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    if res and res.text:
                        response = res
                        used_model = model_name
                        print(f"[Kian AgentNet] SUCCESS with model: {used_model}")
                        break
                except Exception as model_err:
                    err_str = str(model_err)
                    errors_log.append(f"{model_name} (Attempt {attempt+1}): {err_str}")
                    print(f"[Kian AgentNet] {model_name} Error: {err_str}")
                    
                    if "503" in err_str:
                        time.sleep(2)
                        continue
                    else:
                        break
            
            if response:
                break 

        if not response or not response.text:
            return {
                "status": "gateway_error",
                "error_code": "ALL_MODELS_UNAVAILABLE",
                "message": f"تعذر الاتصال بجميع النماذج. تفاصيل المحاولات: {errors_log}"
            }
        
        structured_payload = json.loads(response.text)
        
        new_credits = current_credits - 1
        supabase.table("api_keys").update({"credits": new_credits}).eq("id", developer_record["id"]).execute()
        
        supabase.table("api_usage_logs").insert({
            "api_key_id": developer_record["id"],
            "target_url": payload.url,
            "status": "success"
        }).execute()
        
        return {
            "status": "success",
            "protocol_version": "2.0.0",
            "model_used": used_model,
            "remaining_credits": new_credits,
            "data": structured_payload
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        return {
            "status": "fatal_error",
            "message": str(e)
        }