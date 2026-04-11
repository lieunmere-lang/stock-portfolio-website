import os
import jwt
import uuid
import requests
import secrets
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# --- Load Environment Variables ---
load_dotenv()
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
APP_USERNAME = os.getenv("APP_USERNAME", "portfolio")
APP_PASSWORD = os.getenv("APP_PASSWORD", "portfolio")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    is_valid = secrets.compare_digest(credentials.username, APP_USERNAME) and secrets.compare_digest(credentials.password, APP_PASSWORD)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- Pydantic Models for Data Structure ---
class Asset(BaseModel):
    name: str
    ticker: str
    quantity: float
    avg_price: float
    current_price: float
    total_value: float
    profit_loss: float
    profit_loss_rate: float
    asset_type: str = 'crypto'

class Portfolio(BaseModel):
    last_synced: str
    total_value: float
    total_profit_loss: float
    total_profit_loss_rate: float
    assets: List[Asset]

# --- In-Memory Store ---
portfolio_data: Dict[str, Any] = {}

# --- Real-Time Data Fetching from Upbit ---
def get_real_upbit_data() -> List[Dict[str, Any]]:
    if not UPBIT_ACCESS_KEY or not UPBIT_SECRET_KEY:
        print("API keys not found. Skipping Upbit data fetch.")
        return []

    # 1. Get account balances
    payload = {
        'access_key': UPBIT_ACCESS_KEY,
        'nonce': str(uuid.uuid4()),
    }
    jwt_token = jwt.encode(payload, UPBIT_SECRET_KEY)
    authorize_token = f'Bearer {jwt_token}'
    headers = {'Authorization': authorize_token}

    res = requests.get("https://api.upbit.com/v1/accounts", headers=headers)
    res.raise_for_status()  # Raise error for bad responses
    my_assets = res.json()

    # 2. Get ticker information (current prices)
    # We need to format the tickers to query the ticker API
    tickers = [asset['currency'] for asset in my_assets if asset['currency'] != 'KRW']
    upbit_tickers = [f"KRW-{ticker}" for ticker in tickers]
    
    if not upbit_tickers:
        return []

    ticker_res = requests.get(f"https://api.upbit.com/v1/ticker?markets={','.join(upbit_tickers)}")
    ticker_res.raise_for_status()
    ticker_data = {t['market']: t for t in ticker_res.json()}

    # 3. Combine data
    processed_assets = []
    for asset in my_assets:
        currency = asset['currency']
        if currency == 'KRW':
            continue

        market_ticker = f"KRW-{currency}"
        current_price_info = ticker_data.get(market_ticker)
        
        if current_price_info:
            quantity = float(asset['balance'])
            avg_price = float(asset['avg_buy_price'])
            current_price = current_price_info['trade_price']
            
            processed_assets.append({
                "name": currency, # Using currency symbol as name for now
                "ticker": market_ticker,
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": current_price
            })
            
    return processed_assets

# --- Data Synchronization Logic ---
def sync_data():
    global portfolio_data
    print("Syncing data...")

    all_assets: List[Asset] = []
    total_value = 0.0
    total_purchase_value = 0.0

    # Crypto from Upbit
    upbit_cryptos = get_real_upbit_data()
    for crypto in upbit_cryptos:
        total_value += crypto["quantity"] * crypto["current_price"]
        total_purchase_value += crypto["quantity"] * crypto["avg_price"]
        asset = Asset(
            name=crypto["name"],
            ticker=crypto["ticker"],
            quantity=crypto["quantity"],
            avg_price=crypto["avg_price"],
            current_price=crypto["current_price"],
            total_value=crypto["quantity"] * crypto["current_price"],
            profit_loss=(crypto["current_price"] - crypto["avg_price"]) * crypto["quantity"],
            profit_loss_rate=((crypto["current_price"] / crypto["avg_price"]) - 1) if crypto["avg_price"] > 0 else 0,
            asset_type='crypto'
        )
        all_assets.append(asset)
    
    total_profit_loss = total_value - total_purchase_value
    total_profit_loss_rate = (total_value / total_purchase_value) - 1 if total_purchase_value > 0 else 0

    portfolio_data = Portfolio(
        last_synced=datetime.datetime.now().isoformat(),
        total_value=total_value,
        total_profit_loss=total_profit_loss,
        total_profit_loss_rate=total_profit_loss_rate,
        assets=all_assets
    ).dict()
    print("Data sync complete.")


# --- FastAPI Application Setup ---
app = FastAPI(dependencies=[Depends(authenticate)])
scheduler = BackgroundScheduler()
scheduler.add_job(sync_data, 'interval', hours=1)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    sync_data()
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

@app.get("/health")
def health_check():
    return {"message": "Portfolio API is running"}

@app.get("/api/portfolio", response_model=Portfolio)
def get_portfolio():
    if not portfolio_data:
        sync_data()
    return portfolio_data
    
@app.post("/api/sync", dependencies=[Depends(authenticate)])
def force_sync():
    sync_data()
    return {"status": "success", "message": "Data synchronization triggered."}

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
