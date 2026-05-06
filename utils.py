import pandas as pd
from datetime import datetime
import os

EXCEL_PATH = "data/May2026.xlsx"  # Change as needed

def load_trades():
    if os.path.exists(EXCEL_PATH):
        return pd.read_excel(EXCEL_PATH, sheet_name="Sheet1")
    else:
        # Create with your headers
        columns = ["Date", "Instrument", "Strategy", "position Size", "Entry", "Exit", 
                  "Expected move", "Stop Loss", "Target", "Did you follow your plan?", 
                  "Slippage / late entry / early exit", "Any adjustment made", 
                  "Emotion before trade", "During trade", "After trade", 
                  "What Worked / What Failed", "Improvement"]
        df = pd.DataFrame(columns=columns)
        os.makedirs("data", exist_ok=True)
        df.to_excel(EXCEL_PATH, index=False)
        return df

def save_trade(trade_data: dict):
    df = load_trades()
    new_row = pd.DataFrame([trade_data])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(EXCEL_PATH, index=False)
    return df