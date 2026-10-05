import os
import telebot
import requests
from flask import Flask
from threading import Thread

# ================= 1. SERVIDOR WEB EN SEGUNDO PLANO PARA RENDER =================
app = Flask("")

@app.route("/")
def home():
    return "🤖 Bot activo 24/7 en Render"

port = int(os.environ.get("PORT", 8080))
Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()

# ================= 2. CLAVES DE ACCESO =================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "PEGA_AQUI_TU_TOKEN_DE_TELEGRAM")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "PEGA_AQUI_TU_API_KEY_DE_GEMINI")

PROMPT_SISTEMA = """
Eres un consultor de IA, facilitador de ideas y asistente de proyectos para Esteban y su equipo. Actúas como un miembro activo del grupo para debatir, analizar y ejecutar cualquier proyecto, idea o decisión.
Conoces el proyecto de modernización, inventario físico progresivo (espaciado por zonas para no frenar ventas ni duplicar esfuerzos) y selección de software (POS, facturación electrónica DIAN, ERP tipo Alegra, Siigo, Loggro, Odoo) para los almacenes familiares en Colombia.
Respuestas concisas, con estructura clara (viñetas o listas) y orientadas a la acción.
"""

bot = telebot.TeleBot(TELEGRAM_TOKEN)
bot_info = bot.get_me()
BOT_USERNAME = bot_info.username.lower()

def obtener_modelos_flash():
    """Obtiene los modelos Flash gratuitos disponibles en tu cuenta."""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            flash = [
                m["name"] for m in data.get("models", [])
                if "flash" in m["name"].lower() and "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            if flash:
                flash.sort(reverse=True)
                return flash
    except Exception as e:
        print(f"Aviso al listar modelos: {e}")
    return ["models/gemini-2.0-flash", "models/gemini-1.5-flash-latest", "models/gemini-1.5-flash"]

MODELOS_DISPONIBLES = obtener_modelos_flash()
print(f"⚡ Modelos Flash detectados: {MODELOS_DISPONIBLES}")

def consultar_gemini(prompt_usuario):
    payload = {
        "system_instruction": {"parts": [{"text": PROMPT_SISTEMA}]},
        "contents": [{"role": "user", "parts": [{"text": prompt_usuario}]}]
    }

    for modelo in MODELOS_DISPONIBLES:
        url = f"https://generativelanguage.googleapis.com/v1beta/{modelo}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                print(f"Fallo con {modelo} ({response.status_code}), probando siguiente...")
        except Exception as e:
            print(f"Error con {modelo}: {e}")

    return "⚠️ Los modelos están temporalmente saturados. Intenta en unos segundos."

@bot.message_handler(func=lambda message: True)
def manejar_mensajes(message):
    texto = message.text or ""
    es_privado = message.chat.type == "private"
    es_mencion = f"@{BOT_USERNAME}" in texto.lower()
    es_respuesta_al_bot = (
        message.reply_to_message is not None 
        and message.reply_to_message.from_user.id == bot_info.id
    )

    if es_privado or es_mencion or es_respuesta_al_bot:
        prompt_limpio = texto.replace(f"@{bot_info.username}", "").strip()
        if not prompt_limpio or prompt_limpio == "/start":
            prompt_limpio = "Hola, preséntate brevemente y dime en qué podemos arrancar hoy con el proyecto o ideas."

        bot.send_chat_action(message.chat.id, "typing")
        respuesta = consultar_gemini(prompt_limpio)
        bot.reply_to(message, respuesta)

# Limpiar conexiones anteriores
bot.delete_webhook()

print(f"🤖 Bot @{bot_info.username} en línea y listo en Render.")
bot.infinity_polling()
