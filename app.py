import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import asyncio
from google.antigravity import Agent, LocalAgentConfig
from dotenv import load_dotenv  # .env ഫയൽ വായിക്കാൻ ഇത് ആവശ്യമാണ്

# പ്രൊജക്റ്റ് ഫോൾഡറിലെ .env ഫയൽ ലോഡ് ചെയ്യുന്നു
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 3 റൂംമേറ്റ്സിന്റെ പേരുകൾ
ROOMMATES = ["രാഹുൽ", "അഖിൽ", "ജിതിൻ"]

# Database Table
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    shop = db.Column(db.String(100), nullable=False)
    paid_by = db.Column(db.String(50), nullable=False)  # പണം നൽകിയ ആൾ
    amount = db.Column(db.Float, nullable=False)

# AI function to categorize the expense purpose
async def process_purpose_with_ai(title, api_key):
    instruction = (
        "You are an expense categorizer. Look at the item name and give a 1-word category/purpose. "
        "Example: If item is 'Petrol' or 'Diesel', reply: Transport. "
        "If item is 'Biriyani' or 'Milk', reply: Food. "
        "Respond ONLY with the category word."
    )
    config = LocalAgentConfig(
        api_key=api_key,
        system_instructions=instruction
    )
    try:
        async with Agent(config) as agent:
            response = await agent.chat(title)
            res_text = await response.text()
            return res_text.strip()
    except Exception:
        return "General"

@app.route('/', methods=['GET', 'POST'])
def index():
    # നിങ്ങളുടെ രഹസ്യ API Key ഇവിടെ നേരിട്ട് കൊടുക്കുന്നില്ല.
    # ഇത് കമ്പ്യൂട്ടറിലെ .env ഫയലിൽ നിന്നോ Render ഡാഷ്‌ബോർഡിൽ നിന്നോ ഓട്ടോമാറ്റിക്കായി എടുത്തോളും.
    MY_API_KEY = os.environ.get("GEMINI_API_KEY")

    if request.method == 'POST':
        date_str = request.form['date']
        item_title = request.form['title']
        shop = request.form['shop']
        paid_by = request.form['paid_by']
        amount = request.form['amount']

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        # AI വഴി കാറ്റഗറി കണ്ടെത്തുന്നു
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            purpose = loop.run_until_complete(process_purpose_with_ai(item_title, MY_API_KEY))
        except Exception:
            purpose = "General"

        full_title = f"{item_title} ({purpose})"

        new_expense = Expense(
            date=date_obj,
            title=full_title,
            shop=shop,
            paid_by=paid_by,
            amount=float(amount)
        )
        db.session.add(new_expense)
        db.session.commit()
        return redirect(url_for('index'))

    expenses = Expense.query.order_by(Expense.date.desc()).all()

    # ഈ മാസത്തെ കണക്കുകൾ മാത്രം ഫിൽട്ടർ ചെയ്യുന്നു
    current_month = datetime.now().month
    current_year = datetime.now().year
    monthly_expenses = [exp for exp in expenses if exp.date.month == current_month and exp.date.year == current_year]

    # ആകെ തുകകൾ
    monthly_total = sum(exp.amount for exp in monthly_expenses)
    total_all_time = sum(exp.amount for exp in expenses)

    # 1. ഓരോരുത്തരും ഈ മാസം ആകെ ചിലവാക്കിയ തുക (Individual Spent)
    shares = {name: 0.0 for name in ROOMMATES}
    for exp in monthly_expenses:
        if exp.paid_by in shares:
            shares[exp.paid_by] += exp.