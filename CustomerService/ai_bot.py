"""
PlagSini AI Bot — Hybrid approach:
  1. Rule-based matching for common FAQs (instant, free, no API needed)
  2. Greeting / casual conversation handling
  3. Numbered selection support
  4. Bahasa Malaysia support
  5. Google Gemini free tier for complex / natural language questions

Gemini 1.5 Flash free tier: 15 RPM, 1M TPM, 1500 RPD — more than enough.
If GEMINI_API_KEY is not set, falls back to rule-based only.
"""

import os
import re
import logging
import asyncio
from typing import Optional

from knowledge_base import (
    APP_CONTEXT, FAQ_CATEGORIES, 
    detect_category, detect_priority, find_best_faq_answer
)

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
gemini_model = None


def init_gemini():
    """Initialize Gemini model if API key is available."""
    global gemini_model
    if not GEMINI_API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY not set — bot running in rule-based mode only")
        return False
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=APP_CONTEXT,
            generation_config={
                "temperature": 0.7,
                "top_p": 0.9,
                "max_output_tokens": 500,
            }
        )
        logger.info("✅ Gemini AI initialized (free tier)")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini: {e}")
        gemini_model = None
        return False


async def ask_gemini(message: str, conversation_history: list[dict] = None) -> Optional[str]:
    """Ask Gemini for a response. Returns None if unavailable."""
    if gemini_model is None:
        return None
    
    try:
        # Build conversation context
        history = []
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                role = "user" if msg["role"] == "user" else "model"
                history.append({"role": role, "parts": [msg["content"]]})
        
        chat = gemini_model.start_chat(history=history)
        response = await asyncio.to_thread(chat.send_message, message)
        return response.text
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return None


# ═══════════════════════════════════════════
#  GREETING & CASUAL CONVERSATION DETECTION
# ═══════════════════════════════════════════

GREETINGS = {
    "en": ["hi", "hello", "hey", "yo", "sup", "hiya", "good morning", "good afternoon",
           "good evening", "good night", "howdy", "greetings", "what's up", "whats up"],
    "ms": ["hai", "helo", "oi", "assalamualaikum", "salam", "apa khabar", "selamat pagi",
           "selamat petang", "selamat tengahari", "selamat malam", "waalaikumsalam", "wslm",
           "pagi", "petang", "malam", "bro", "bang", "sis", "kak"],
}

THANKS = ["thanks", "thank you", "tq", "terima kasih", "tima kasih", "tkasih", "thx",
          "ty", "appreciate", "terbaik", "mantap", "nice", "great", "awesome", "cool",
          "bagus", "best", "hebat", "ok thanks", "okay thanks"]

GOODBYE = ["bye", "goodbye", "see you", "jumpa lagi", "assalamualaikum", "salam",
           "good night", "selamat malam", "bye bye", "later", "dah", "ok bye",
           "thanks bye", "tq bye", "done", "settle"]

AFFIRMATIVE = ["ok", "okay", "okey", "alright", "sure", "yep", "yup", "yes", "ya", "ye",
               "faham", "got it", "i see", "understood", "roger", "noted", "orait",
               "betul", "boleh", "baik", "oke"]

NEGATIVE = ["no", "nope", "tak", "tidak", "takpe", "taknak", "tak nak", "nah",
            "cancel", "batal", "nevermind", "never mind", "takde", "tak payah"]

HELP_WORDS = ["help", "tolong", "bantu", "assist", "nak tanya", "tanya",
              "macam mana", "camne", "how", "what", "kenapa", "why", "boleh tak",
              "can you", "please", "sila", "apa", "mana", "where", "bila", "when"]


def _clean(text: str) -> str:
    """Normalize text for matching."""
    return re.sub(r'[^\w\s]', '', text.strip().lower())


def _is_greeting(text: str) -> bool:
    clean = _clean(text)
    all_greetings = GREETINGS["en"] + GREETINGS["ms"]
    # Exact match or starts with greeting
    for g in all_greetings:
        if clean == g or clean.startswith(g + " ") or clean.startswith(g + ","):
            return True
    return False


def _is_thanks(text: str) -> bool:
    clean = _clean(text)
    return any(t in clean for t in THANKS)


def _is_goodbye(text: str) -> bool:
    clean = _clean(text)
    return any(g == clean or clean.startswith(g + " ") for g in GOODBYE)


def _is_affirmative(text: str) -> bool:
    clean = _clean(text)
    return clean in AFFIRMATIVE or any(clean.startswith(a + " ") for a in AFFIRMATIVE)


def _is_negative(text: str) -> bool:
    clean = _clean(text)
    return clean in NEGATIVE or any(clean.startswith(n + " ") for n in NEGATIVE)


def _is_number_selection(text: str) -> Optional[int]:
    """Check if user typed a number (1-9) to select an option."""
    clean = _clean(text)
    match = re.match(r'^(\d)$', clean)
    if match:
        return int(match.group(1))
    # Also match "option 1", "pilihan 1", "number 1", "no 1"
    match = re.match(r'^(?:option|pilihan|number|no|nombor|#)\s*(\d)$', clean)
    if match:
        return int(match.group(1))
    return None


def _has_help_intent(text: str) -> bool:
    clean = _clean(text)
    return any(h in clean for h in HELP_WORDS)


# ═══════════════════════════════════════════
#  RESPONSE GENERATORS
# ═══════════════════════════════════════════

def _greeting_response() -> dict:
    return {
        "message": (
            "👋 **Hey there! Welcome to PlagSini Support!**\n\n"
            "I'm your AI assistant — here to help you with anything related to the PlagSini EV Charging app.\n\n"
            "You can:\n"
            "• **Choose a category** above to browse common issues\n"
            "• **Type your question** directly (e.g., \"I can't login\" or \"how to top up\")\n"
            "• **Create a support ticket** if you need human help\n\n"
            "What can I help you with today? 😊"
        ),
        "type": "greeting",
        "category": None,
        "priority": "low",
        "needs_ticket": False,
        "suggestions": [
            "Show me the categories",
            "I can't login",
            "How to top up credits",
            "Create a support ticket"
        ]
    }


def _thanks_response() -> dict:
    return {
        "message": (
            "😊 **You're welcome!** Glad I could help.\n\n"
            "Is there anything else you need? Feel free to ask anytime!\n\n"
            "If your issue is fully resolved, you can close this chat. "
            "If you need more help later, just come back! 👋"
        ),
        "type": "thanks",
        "category": None,
        "priority": "low",
        "needs_ticket": False,
        "suggestions": [
            "I have another question",
            "That's all, thanks!"
        ]
    }


def _goodbye_response() -> dict:
    return {
        "message": (
            "👋 **Goodbye! Thanks for using PlagSini Support.**\n\n"
            "If you need help again, I'm always here — 24/7! 🔋⚡\n\n"
            "Happy charging! 🚗💚"
        ),
        "type": "goodbye",
        "category": None,
        "priority": "low",
        "needs_ticket": False,
    }


def _affirmative_response() -> dict:
    return {
        "message": (
            "👍 **Great!** Is there anything specific you'd like help with?\n\n"
            "You can:\n"
            "• **Choose a category** above to browse common issues\n"
            "• **Type your question** directly\n"
            "• Say **\"create ticket\"** if you need human assistance"
        ),
        "type": "affirmative",
        "category": None,
        "priority": "low",
        "needs_ticket": False,
        "suggestions": [
            "Show me the categories",
            "Create a support ticket"
        ]
    }


def _number_selection_response(num: int) -> dict:
    """Handle when user types a number to select an option."""
    # Map numbers to common actions based on the fallback message pattern
    actions = {
        1: {
            "message": (
                "📂 **Here are the categories I can help with:**\n\n"
                "• 🔐 **Login & Account** — Registration, password, OTP issues\n"
                "• ⚡ **Charging Issues** — Starting, stopping, billing problems\n"
                "• 💳 **Wallet & Payment** — Top up, balance, refunds\n"
                "• 🚗 **Vehicle Management** — Adding/removing vehicles\n"
                "• 🎁 **Rewards & Points** — Earning and redeeming points\n"
                "• 📱 **App Problems** — Crashes, slow, GPS issues\n"
                "• ❓ **General Questions** — Other inquiries\n\n"
                "Which category matches your issue? Tap one above or type the topic! 👆"
            ),
            "type": "category_list",
        },
        2: {
            "message": (
                "✍️ **Sure! Please describe your issue in detail.**\n\n"
                "For example:\n"
                "• \"I can't login, it says wrong password\"\n"
                "• \"My top up payment is pending\"\n"
                "• \"The charger stopped unexpectedly\"\n\n"
                "The more details you provide, the better I can help! 😊"
            ),
            "type": "prompt_detail",
        },
        3: {
            "message": (
                "📩 **I'll create a support ticket for you!**\n\n"
                "A real human from our team will follow up with you via email.\n"
                "Let me open the ticket form for you..."
            ),
            "type": "escalate",
            "needs_ticket": True,
        },
    }

    if num in actions:
        result = actions[num]
        return {
            "message": result["message"],
            "type": result.get("type", "number_select"),
            "category": None,
            "priority": "low",
            "needs_ticket": result.get("needs_ticket", False),
            "suggestions": ["Show me the categories", "Create a support ticket"] if not result.get("needs_ticket") else None,
        }
    
    return {
        "message": f"I'm not sure what option **{num}** refers to. Could you try describing your issue instead?",
        "type": "fallback",
        "category": None,
        "priority": "low",
        "needs_ticket": False,
        "suggestions": ["Show me the categories", "Create a support ticket"]
    }


# ═══════════════════════════════════════════
#  WELCOME & CATEGORY HANDLERS
# ═══════════════════════════════════════════

def get_welcome_message() -> dict:
    """Generate the bot's welcome message with quick action buttons."""
    categories = []
    for key, cat in FAQ_CATEGORIES.items():
        categories.append({
            "id": key,
            "label": cat["label"],
            "description": cat["description"],
            "icon": cat["icon"],
        })
    
    return {
        "message": (
            "👋 **Hi! I'm PlagSini Assistant.**\n\n"
            "I can help you with common questions about the app, charging, payments, and more.\n\n"
            "**How can I help you today?** Choose a category below or just type your question:"
        ),
        "categories": categories,
        "type": "welcome"
    }


def get_category_questions(category_id: str) -> dict:
    """Get available questions for a specific category."""
    cat = FAQ_CATEGORIES.get(category_id)
    if not cat:
        return {"message": "Category not found.", "questions": [], "type": "error"}
    
    questions = []
    for qa in cat["questions"]:
        questions.append({
            "text": qa["q"],
            "keywords": qa["keywords"][:2],
        })
    
    return {
        "message": f"**{cat['label']}**\n\nHere are common issues I can help with. Tap one or describe your problem:",
        "questions": questions,
        "category": category_id,
        "type": "category_questions"
    }


# ═══════════════════════════════════════════
#  MAIN MESSAGE PROCESSOR
# ═══════════════════════════════════════════

async def process_message(
    user_message: str, 
    conversation_history: list[dict] = None,
    selected_category: str = None
) -> dict:
    """
    Process a user message and generate a response.
    """
    if not user_message or not user_message.strip():
        return {
            "message": "I didn't catch that. Could you rephrase your question?",
            "type": "error"
        }
    
    text = user_message.strip()
    
    # ── Step 0: Handle greetings, casual, numbered selections ──
    
    # Greeting check
    if _is_greeting(text):
        return _greeting_response()
    
    # Thanks check
    if _is_thanks(text):
        return _thanks_response()
    
    # Goodbye check
    if _is_goodbye(text):
        return _goodbye_response()
    
    # Number selection check
    num = _is_number_selection(text)
    if num is not None:
        return _number_selection_response(num)
    
    # Simple affirmative (ok, yes) — only if short message
    if len(text) < 10 and _is_affirmative(text):
        return _affirmative_response()
    
    # ── Step 1: Detect category and priority ──
    category = selected_category or detect_category(text)
    priority = detect_priority(text)
    
    # ── Step 2: Check for escalation keywords ──
    escalation_words = [
        "human", "agent", "person", "manusia", "real person", "talk to someone",
        "ticket", "tiket", "create ticket", "buat tiket", "staff", "support team",
        "nak cakap dengan orang", "nak bercakap", "call", "phone"
    ]
    wants_escalation = any(w in text.lower() for w in escalation_words)
    
    if wants_escalation:
        return {
            "message": (
                "I understand you'd like to speak with our support team. "
                "Let me create a ticket for you.\n\n"
                "**Please provide:**\n"
                "1. Your email address\n"
                "2. A brief description of your issue\n\n"
                "Or I can create one right now based on our conversation."
            ),
            "type": "escalate",
            "category": category,
            "priority": priority,
            "needs_ticket": True,
        }
    
    # ── Step 3: Try rule-based FAQ match ──
    faq_answer = find_best_faq_answer(text, category)
    
    if faq_answer:
        return {
            "message": faq_answer,
            "type": "faq",
            "category": category,
            "priority": priority,
            "needs_ticket": False,
            "suggestions": [
                "Did this solve your problem?",
                "I need more help",
                "Create a support ticket"
            ]
        }
    
    # ── Step 4: Try without category filter (wider search) ──
    if selected_category:
        faq_answer_wide = find_best_faq_answer(text, None)
        if faq_answer_wide:
            return {
                "message": faq_answer_wide,
                "type": "faq",
                "category": category,
                "priority": priority,
                "needs_ticket": False,
                "suggestions": [
                    "Did this solve your problem?",
                    "I need more help",
                    "Create a support ticket"
                ]
            }
    
    # ── Step 5: Try Gemini AI ──
    gemini_response = await ask_gemini(text, conversation_history)
    
    if gemini_response:
        return {
            "message": gemini_response,
            "type": "ai_answer",
            "category": category,
            "priority": priority,
            "needs_ticket": False,
            "suggestions": [
                "That helped, thanks!",
                "I need more help",
                "Create a support ticket"
            ]
        }
    
    # ── Step 6: Smart fallback — try to suggest based on keywords ──
    
    # If user seems to be asking for help, give them a more guided response
    if _has_help_intent(text):
        return {
            "message": (
                "I'd love to help! Here are the topics I can assist with:\n\n"
                "🔐 **Login/Account** — \"I can't login\", \"forgot password\", \"OTP issue\"\n"
                "⚡ **Charging** — \"can't start charging\", \"QR not working\"\n"
                "💳 **Payment** — \"top up not reflected\", \"refund\"\n"
                "🚗 **Vehicle** — \"how to add vehicle\"\n"
                "🎁 **Rewards** — \"how do points work\"\n"
                "📱 **App Issues** — \"app crashing\", \"GPS not working\"\n\n"
                "Try describing your issue and I'll do my best! 😊"
            ),
            "type": "guided_help",
            "category": category,
            "priority": priority,
            "needs_ticket": False,
            "suggestions": [
                "I can't login",
                "Top up issue",
                "Charging problem",
                "Create a support ticket"
            ]
        }
    
    # Generic fallback
    return {
        "message": (
            "Hmm, I'm not quite sure how to help with that. "
            "Let me suggest a few things:\n\n"
            "1. **Browse categories** — Tap a category button above\n"
            "2. **Be more specific** — e.g., \"I can't login\" or \"how to top up\"\n"
            "3. **Create a ticket** — Our team will help you personally\n\n"
            "What would you like to do? 😊"
        ),
        "type": "fallback",
        "category": category,
        "priority": priority,
        "needs_ticket": False,
        "suggestions": [
            "Show me the categories",
            "Create a support ticket"
        ]
    }
