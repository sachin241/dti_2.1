# ── AI Chatbot (drop-in replacement for the /api/chat route in main.py) ────────
#
# Changes vs. old version:
#  1. Accepts optional `history` list for multi-turn memory
#  2. Richer, website-aware system prompt
#  3. Graceful Gemini 503 fallback preserved
#  4. Returns structured {answer, error?} always

from pydantic import BaseModel
from typing import List, Optional


class ChatMessage(BaseModel):
    role: str        # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


@app.post("/api/chat")
def api_chat(req: ChatRequest, request: Request):
    user = current_user(request)

    # Build user context
    user_context_lines = []
    if user:
        products = get_tracked_products_by_email(user["email"])
        if products:
            items = []
            for p in products[:10]:
                name = p.get("product_name") or p.get("url", "")[:60]
                price = p.get("price", 0)
                target = p.get("target_price")
                platform = p.get("platform", "")
                gap = f", target ₹{target:,}" if target else ""
                items.append(f"  • {name} — ₹{price:,} on {platform}{gap}")
            user_context_lines.append("User's currently tracked products:\n" + "\n".join(items))
        else:
            user_context_lines.append("The user has no tracked products yet.")

    user_context = "\n".join(user_context_lines)
    user_name = user["name"] if user else "there"

    system_prompt = f"""You are Antigravity AI, a smart and friendly shopping assistant built into Price Tarcker — a multi-platform price tracking app for Indian e-commerce (Flipkart, Amazon.in, Myntra, Snapdeal).

Your role is to help users:
- Find the best deals across platforms
- Understand price trends and when to buy
- Interpret their tracked product data
- Make informed purchasing decisions
- Get recommendations for similar or better products

Personality: Conversational, analytical, concise. Be direct and helpful. Use ₹ for Indian prices. Occasionally mention you're Antigravity AI.

Website capabilities you can reference:
- /track — Add a product URL to track (with target price alerts)
- /dashboard — View all tracked products and their status
- /compare — Compare a product URL across all 4 platforms live
- /analytics — See price trend charts and statistics

{user_context}

Guidelines:
- Keep responses concise (2-4 sentences for simple answers, bullet points for lists)
- If the user asks to compare or track something, remind them they can use the Compare or Track page
- Do NOT make up prices or product data — only use what's provided in context
- Format currency as ₹X,XX,XXX (Indian notation)
- If asked about something outside shopping/prices, politely redirect"""

    # Build conversation turns for multi-turn context
    conversation_parts = []
    for turn in (req.history or [])[-6:]:  # last 6 turns max
        role = "user" if turn.role == "user" else "model"
        conversation_parts.append({"role": role, "parts": [{"text": turn.content}]})
    # Add the new user message
    conversation_parts.append({"role": "user", "parts": [{"text": req.message}]})

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key or api_key.startswith("your_"):
            return JSONResponse({
                "answer": "⚠ Antigravity AI is not configured yet. Add your GEMINI_API_KEY to the .env file to enable the assistant."
            }, status_code=503)

        client = genai.Client(api_key=api_key)

        # Try Gemini 2.5 Flash first, fall back to 1.5 Flash on 503
        for model_name in ("gemini-2.5-flash", "gemini-1.5-flash"):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=conversation_parts,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=600,
                        temperature=0.7,
                    ),
                )
                return JSONResponse({"answer": response.text})
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "UNAVAILABLE" in err_str or "demand" in err_str.lower()) \
                        and model_name != "gemini-1.5-flash":
                    continue  # try fallback
                raise e

    except Exception as e:
        return JSONResponse({
            "answer": f"Oops! Something went wrong with Antigravity AI: {str(e)[:120]}"
        }, status_code=500)
