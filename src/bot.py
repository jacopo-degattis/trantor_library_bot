import timeit
import random
import requests
from io import BytesIO
from config import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext

## ==> Backend SECTION (API INTERATCIONS)
## The whole bot is based on Imperial Library's API (JSON Parsing)
## Timing depends on original server, also consider that the bot need to pass through TOR Proxy to work (Longer times)

results = None # Variable to contain current book list
# Temp variable --> to remove TODO
page = 0
current_page = 0 # Temp variable TODO

# Configure the current session
def _configure(session):
    headers = {"User-agent": "HotJava/1.1.2 FCS"}
    session.proxies = {"http": config["proxy"], "https": config["proxy"]}
    return session, headers

# Return a list of books (Objects) TODO: Maybe better without object ? ! Response timing !
def get_books(books):
    res_books = []
    for book in books:
        b = Book(book["title"], book["description"], book["authors"][0], 
                book["cover"], book["download"], book["id"], book["lang"]
            )
        res_books.append(b)
    return res_books

# Return search results
def _search(session, query, headers):
    # p paramter mean page number, set to 0 for most relevant results -> change it -> TODO
    uri = config["base_url"].format("/search/?q={}&p=0&fmt=json".format(query))
    print("curr uri: " + uri)
    response = session.get(uri, headers=headers).json()
    start = timeit.default_timer()
    books = get_books(response["books"])
    stop = timeit.default_timer()
    print("Time: ", stop-start)
    return books

def __get_books_no_obj(books):
    res_books = []
    for book in books:
        b = {
            "title":book["title"],
            "description":book["description"],
            "authors":book["authors"][0], 
            "cover":book["cover"],
            "download":book["download"],
            "id":book["id"],
            "lang": book["lang"]
        }
        res_books.append(b)
    return res_books

def _search_no_obj(session, query, headers, page=0):
    # p paramter mean page number, set to 0 for most relevant results -> change it -> TODO
    uri = config["base_url"].format("/search/?q={}&p={}&fmt=json".format(query, page))
    print("curr uri: " + uri)
    response = session.get(uri, headers=headers).json()
    start = timeit.default_timer()
    books = __get_books_no_obj(response["books"])
    stop = timeit.default_timer()
    print("Time: ", stop-start)
    return books

# download_uri = download_uri
def _download(session, headers, download_uri):
    curr_url = config["base_url"].format(download_uri)
    content = session.get(curr_url, headers=headers).content
    try:
        with open(download_uri.split('/')[-1], 'wb') as output:
            output.write(content)
            output.close()
    except Exception as e:
        print("an error occurred")

# Search a book by his ID
def _search_by_id(session, headers, book_id):
    uri = config["base_url"].format(f"/book/{book_id}?fmt=json")
    content = session.get(uri, headers=headers).json()
    return content

# Given an url it returns raw image/document/music data
def get_raw_data_from_url(session, headers, url):
    data = session.get(url, headers=headers).content
    raw_bytes_stream = BytesIO(data)
    return raw_bytes_stream 

## ==> Frontend SECTION (TELEGRAM BOT)

# -> None: means void function
def start(update, context) -> None:
    welcome_message = '''Welcome to Trantor Library Bot\nHere you can find any kind of book !\n\nAvailable commands: \n- /search <bookname>\n- /help'''
    update.message.reply_text(welcome_message, parse_mode='Markdown')

def helper(update, context) -> None:
    help_message = '''Hi, type /search <book name> to search for a book!'''
    update.message.reply_text(help_message)

# Function to search for a book 
# NOTE: results are limited to the first page (0) max 5 books 
def search(update, context) -> None:
    global page
    global current_page
    page = 0
    counter = 0
    keyboard = [
        # example: [InlineKeyboardButton("Option3", callback_data='3')],
    ]
    # Random book emoticons to use in message
    books_types = ["📓", "📘", "📗", "📕", "📙"]
    message = "📚 Results"
    elements = update.message.text.split(' ')
    global user_query
    user_query = ""
    if len(elements) > 2:
        for el in elements[1:]:
            user_query += el + " "
    else:
        user_query = elements[1]
    mex = update.message.reply_text("Fetching books...")
    # Make the actual request with _search function
    # results = _search(session, query, headers)
    global results
    results = _search_no_obj(session, user_query, headers)
    for result in results[0:5]:
        # Create the list of books to send in chat
        # keyboard.append([InlineKeyboardButton(f"{books_types[random.randint(0, len(books_types)-1)]} {result.get_title()}", callback_data=result.get_book_id())])
        keyboard.append([InlineKeyboardButton(f"{books_types[random.randint(0, len(books_types)-1)]} {result['title']}", callback_data=result['id'])])
    keyboard.append([InlineKeyboardButton("<", callback_data="back"), InlineKeyboardButton(">", callback_data="forward")])
    bot.delete_message(chat_id=mex.chat.id, message_id=mex.message_id)
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(message, reply_markup=reply_markup)

def button(update, context) -> None:
    global page
    global user_query
    global current_page
    global results

    print("Books: ", len(results))

    query = update.callback_query
    query.answer()
    books_types = ["📓", "📘", "📗", "📕", "📙"]
    if query.data != 'forward' and query.data != 'back':
        book_id = query.data

        # Get book infos by ID
        response = _search_by_id(session, headers, book_id)
        # Add more loading messages TODO
        # update.callback_query.message.reply_text("*Loading... Please wait !*", parse_mode="Markdown")

        # Get image raw data before sending
        image = get_raw_data_from_url(session, headers, config["base_url"].format(response['cover']))
        description = response['description']
        desc = description[0:75] if len(description) > 75 else description
        print(desc)
        curr_caption = f"""\n📚 *Book Infos*\n\n*Title*: {response["title"]}\n\n*Author*: {response["authors"][0]}\n\n*Release date*: {response['date'].split('T')[0]}\n\n*Description*: {desc}...\n\n*Publisher*: {response['publisher']}\n\n*Size*: {round(float(response['size'] / 1e+6), 2)}mb"""
        update.callback_query.message.reply_photo(photo=image, caption=curr_caption, parse_mode='Markdown')
        
        # Get document raw data before sending
        status = update.callback_query.message.reply_text("*Loading... Please wait !*", parse_mode="Markdown")
        document = get_raw_data_from_url(session, headers, config["base_url"].format(response["download"]))
        
        # Delete the loading message and send the document
        bot.delete_message(chat_id=status.chat.id, message_id=status.message_id)
        update.callback_query.message.reply_document(document, filename=f"{response['title']}.epub")
    elif query.data == 'back':
        # Load next 5 books
        # print(results[4]['title'])
        # Default is from 0 to 5 [0:5]
        new_keyboard = []
        if page > 0:
            page -= 5
            books_on_page_back = results[page:page+5]
            for result in books_on_page_back:
                new_keyboard.append([InlineKeyboardButton(f"{books_types[random.randint(0, len(books_types)-1)]} {result['title']}", callback_data=result['id'])])
            new_keyboard.append([InlineKeyboardButton("<", callback_data="back"), InlineKeyboardButton(">", callback_data="forward")])
            print(new_keyboard)
            query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
        else:
            # Check total page number TODO
            if current_page > 0:
                page = 0
                new_keyboard = []
                current_page -= 1
                print("Query: ", user_query)
                print("current page: ", current_page)
                loading_msg_prev = update.callback_query.message.reply_text("Loading previous page...")
                results = _search_no_obj(session, user_query, headers, page=current_page)
                for result in results[page:page+5]:
                    new_keyboard.append([InlineKeyboardButton(f"{books_types[random.randint(0, len(books_types)-1)]} {result['title']}", callback_data=result['id'])])
                new_keyboard.append([InlineKeyboardButton("<", callback_data="back"), InlineKeyboardButton(">", callback_data="forward")])
                bot.delete_message(chat_id=loading_msg_prev.chat.id, message_id=loading_msg_prev.message_id)
                query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
                #update.callback_query.message.reply_text("You already are on the first page ! ")
            else:
                update.callback_query.message.reply_text("You already are on the first page ! ")
        # Edit current keyboard message
    elif query.data == 'forward':
        new_keyboard = []
        print(f"{page} < {len(results)-5}")
        if page < len(results)-5:
            print("IN")
            page += 5
            books_on_page_next = results[page:page+5]
            for result in books_on_page_next:
                new_keyboard.append([InlineKeyboardButton(f"{books_types[random.randint(0, len(books_types)-1)]} {result['title']}", callback_data=result['id'])])
            new_keyboard.append([InlineKeyboardButton("<", callback_data="back"), InlineKeyboardButton(">", callback_data="forward")])
            query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
        else:
            page = 0
            new_keyboard = []
            current_page += 1 # Go next page
            print("Query: ", user_query)
            print("Current page : ", current_page)
            loading_msg_next = update.callback_query.message.reply_text("Loading next page...")
            results = _search_no_obj(session, user_query, headers, page=current_page)
            for result in results[page:page+5]:
                new_keyboard.append([InlineKeyboardButton(f"{books_types[random.randint(0, len(books_types)-1)]} {result['title']}", callback_data=result['id'])])
            new_keyboard.append([InlineKeyboardButton("<", callback_data="back"), InlineKeyboardButton(">", callback_data="forward")])
            bot.delete_message(chat_id=loading_msg_next.chat.id, message_id=loading_msg_next.message_id)
            query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
            # update.callback_query.message.reply_text("You alread are on the last page ! ")

def main():
    updater = Updater(config["TOKEN"], use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("search", search))
    dispatcher.add_handler(CommandHandler("help", helper))
    dispatcher.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    # This "bot" variable is needed to delete the message
    bot = Bot(config["TOKEN"])
    session = requests.session()
    session, headers = _configure(session)
    main()

# Find a way to handle sessions with DICT # TODO