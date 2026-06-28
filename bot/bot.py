from functools import wraps
import os
from telegram import Update
import requests
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv


load_dotenv()  # ← LA LIGNE MAGIQUE

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL")
AUTHORIZED_USERS = {int(id) for id in os.getenv("AUTHORIZED_USERS").split(",")}

# --- Configuration Mammouth ---
MAMMOUTH_API_KEY = os.getenv("MAMMOUTH_API_KEY")
MAMMOUTH_URL = "https://api.mammouth.ai/v1/chat/completions"

def ask_mammouth(question):
    """Envoie une question à l'IA Mammouth et retourne la réponse."""
    headers = {
        "Authorization": f"Bearer {MAMMOUTH_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistral-small-2603",  # PAS CHER : 0.15$/M tokens
        "messages": [
            {
                "role": "system",
                "content": "Tu es un assistant utile et concis. Réponds en français."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "max_tokens": 500,        # limite le coût
        "temperature": 0.7
    }
    
    try:
        response = requests.post(MAMMOUTH_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "⏱️ L'IA met trop de temps à répondre. Réessayez."
    except Exception as e:
        return f"❌ Erreur IA : {e}"

# Liste des utilisateurs autorisés (IDs Telegram)
def restricted(func):
    """Décorateur : bloque les utilisateurs non autorisés."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in AUTHORIZED_USERS:
            await update.message.reply_text(
                "🚫 Accès refusé. Vous n'êtes pas autorisé."
            )
            print(f"⚠️ Tentative refusée : {user_id}")
            return
        
        # ✅ Autorisé → exécuter la fonction
        return await func(update, context)
    
    return wrapper


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bonjour ! Posez-moi n'importe quelle question, je suis propulsé par l'IA."
    )

# Tout message texte → IA
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text
    
    # Montre que le bot "réfléchit"
    await update.message.chat.send_action("typing")
    
    # Demande à l'IA
    reponse = ask_mammouth(user_question)
    
    # Envoie la réponse
    await update.message.reply_text(reponse)

# --- Enregistrement ---
app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()



# /produits → appelle l'API Django
async def produits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 1️⃣ Requête GET vers Django
        response = requests.get(API_URL)

        # 2️⃣ Vérifier le status
        if response.status_code != 200:
            await update.message.reply_text(
                f"❌ Erreur API : {response.status_code}"
            )
            return

        # 3️⃣ Convertir la réponse JSON en liste Python
        products = response.json()

        # 4️⃣ Si vide
        if not products:
            await update.message.reply_text("📦 Aucun produit disponible.")
            return

        # 5️⃣ Construire le message
        message = "🛍️ *Liste des produits :*\n\n"
        for p in products:
            message += f"• *{p['name']}* — {p['price']}fcfa\n"

        # 6️⃣ Envoyer
        await update.message.reply_text(message, parse_mode="Markdown")

    except requests.exceptions.ConnectionError:
        await update.message.reply_text(
            "❌ Impossible de joindre l'API. Django est-il lancé ?"
        )


async def produit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1️⃣ Récupérer l'argument après la commande
    if not context.args:
        await update.message.reply_text(
            "❌ Usage : /produit <id>\nExemple : /produit 1"
        )
        return
    
    product_id = context.args[0]
    
    # 2️⃣ Appeler l'API pour ce produit précis
    try:
        response = requests.get(f"{API_URL}{product_id}/")
        
        # 3️⃣ Vérifier le status
        if response.status_code == 404:
            await update.message.reply_text(
                f"❌ Produit #{product_id} introuvable."
            )
            return
        
        if response.status_code != 200:
            await update.message.reply_text(
                f"❌ Erreur API : {response.status_code}"
            )
            return
        
        # 4️⃣ Formater la réponse
        p = response.json()
        message = (
            f"📦 *Produit #{p['id']}*\n\n"
            f"• Nom : {p['name']}\n"
            f"• Prix : {p['price']}€\n"
        )
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    except requests.exceptions.ConnectionError:
        await update.message.reply_text(
            "❌ Django ne répond pas. Est-il lancé ?"
        )

@restricted
async def ajouter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1️⃣ Vérifier les arguments
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage : /ajouter <nom> <prix>\n"
            "Exemple : /ajouter Pomme 2.5"
        )
        return
    
    # 2️⃣ Récupérer nom et prix
    nom = context.args[0]
    
    try:
        prix = float(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "❌ Le prix doit être un nombre. Exemple : 2.5"
        )
        return
    
    # 3️⃣ Préparer les données pour l'API
    data = {
        "name": nom,
        "price": prix
    }
    
    # 4️⃣ Envoyer POST à Django
    try:
        response = requests.post(API_URL, json=data)
        
        if response.status_code == 201:  # Created ✅
            p = response.json()
            await update.message.reply_text(
                f"✅ Produit créé !\n\n"
                f"• ID : {p['id']}\n"
                f"• Nom : {p['name']}\n"
                f"• Prix : {p['price']}€"
            )
        else:
            await update.message.reply_text(
                f"❌ Erreur {response.status_code} :\n{response.text}"
            )
    
    except requests.exceptions.ConnectionError:
        await update.message.reply_text(
            "❌ Django ne répond pas."
        )


@restricted
async def modifier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1️⃣ Vérifier : id + champ + valeur (3 args minimum)
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Usage : /modifier <id> <champ> <valeur>\n"
            "Exemple : /modifier 1 prix 3.5"
        )
        return
    
    product_id = context.args[0]
    champ = context.args[1]
    valeur = context.args[2]
    
    # 2️⃣ Mapper le champ français vers le champ Django
    mapping = {
        "nom": "name",
        "prix": "price"
    }
    
    if champ not in mapping:
        await update.message.reply_text(
            f"❌ Champ inconnu : {champ}\nChamps valides : nom, prix"
        )
        return
    
    champ_django = mapping[champ]
    
    # 3️⃣ Convertir le prix en float si besoin
    if champ_django == "price":
        try:
            valeur = float(valeur)
        except ValueError:
            await update.message.reply_text("❌ Prix invalide.")
            return
    
    # 4️⃣ Envoyer PATCH à l'API
    data = {champ_django: valeur}
    
    try:
        response = requests.patch(f"{API_URL}{product_id}/", json=data)
        
        if response.status_code == 200:
            p = response.json()
            await update.message.reply_text(
                f"✅ Produit #{p['id']} modifié !\n"
                f"• Nom : {p['name']}\n"
                f"• Prix : {p['price']}€"
            )
        elif response.status_code == 404:
            await update.message.reply_text(f"❌ Produit #{product_id} introuvable.")
        else:
            await update.message.reply_text(f"❌ Erreur {response.status_code}")
    
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("❌ Django ne répond pas.")

@restricted
async def supprimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Usage : /supprimer <id>\nExemple : /supprimer 1"
        )
        return
    
    product_id = context.args[0]
    
    try:
        response = requests.delete(f"{API_URL}{product_id}/")
        
        if response.status_code == 204:  # No Content = succès
            await update.message.reply_text(
                f"🗑️ Produit #{product_id} supprimé."
            )
        elif response.status_code == 404:
            await update.message.reply_text(
                f"❌ Produit #{product_id} introuvable."
            )
        else:
            await update.message.reply_text(f"❌ Erreur {response.status_code}")
    
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("❌ Django ne répond pas.")


# Lancement
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("produits", produits))
    app.add_handler(CommandHandler("produit", produit))
    app.add_handler(CommandHandler("ajouter", ajouter))
    app.add_handler(CommandHandler("modifier", modifier))
    app.add_handler(CommandHandler("supprimer", supprimer))
    print("🤖 Bot démarré...")
    app.run_polling()