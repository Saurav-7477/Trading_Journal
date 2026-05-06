import gspread
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime
from google.oauth2.service_account import Credentials
from pathlib import Path


# ===================== CONFIG =====================
st.set_page_config(page_title="Velocity Trading Journal", layout="wide")
st.title("Velocity Trading Journal")
st.markdown("**Professional Options & Stock Trading Journal**")


# ===================== HEADERS =====================
COLUMNS = [
    "Date",
    "Instrument",
    "Stratergy",
    "position Size",
    "Entry",
    "Exit",
    "Expected move",
    "Stop Loss",
    "Target",
    "Did you follow your plan?",
    "Slippage / late entry / early exit",
    "Any adjustment made",
    "Outcome",
    "Emotion before trade( confident, fearful, FOMO)",
    "During trade: (panic, patience, overconfidence)",
    "After trade: (regret, satisfaction)",
    "What Worked / What Failed",
    "Improvement",
]

GROUP_HEADER_ROW = [
    "Meta Data",
    "",
    "",
    "",
    "",
    "",
    "",
    "Risk Management",
    "",
    "Execution Quality",
    "",
    "",
    "Outcome",
    "Psychlogical State",
    "",
    "",
    "key Learning",
    "",
]

NUMERIC_COLUMNS = [
    "position Size", "Entry", "Exit", "Expected move", "Stop Loss", "Target", "Outcome",
]

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

DEFAULT_SPREADSHEET_NAME = "Trading Journal"
DEFAULT_WORKSHEET_NAME = "Sheet1"
LOCAL_CREDENTIALS_PATH = Path(__file__).with_name("credentials.json")


def show_sheet_error(message, error):
    st.error(message)
    with st.expander("Technical details"):
        st.exception(error)
    st.stop()


def normalize_row(row, expected_length):
    return [str(cell).strip() for cell in (row + [""] * expected_length)[:expected_length]]


def get_secret_section(section_name):
    try:
        return st.secrets.get(section_name, {})
    except Exception:
        return {}


def get_google_sheet_settings():
    gspread_secrets = get_secret_section("gspread")
    gcp_service_account = get_secret_section("gcp_service_account")

    credentials_dict = gspread_secrets.get("credentials") or gcp_service_account
    if credentials_dict is None and LOCAL_CREDENTIALS_PATH.exists():
        credentials_dict = str(LOCAL_CREDENTIALS_PATH)

    spreadsheet_id = (
        gspread_secrets.get("spreadsheet_id")
        or os.environ.get("GOOGLE_SPREADSHEET_ID")
    )
    spreadsheet_name = (
        gspread_secrets.get("spreadsheet_name")
        or os.environ.get("GOOGLE_SPREADSHEET_NAME")
        or DEFAULT_SPREADSHEET_NAME
    )
    worksheet_name = (
        gspread_secrets.get("worksheet_name")
        or os.environ.get("GOOGLE_WORKSHEET_NAME")
        or DEFAULT_WORKSHEET_NAME
    )

    return credentials_dict, spreadsheet_id, spreadsheet_name, worksheet_name


def apply_reference_sheet_layout(worksheet):
    try:
        worksheet.freeze(rows=2)
        worksheet.format("A1:R1", {"textFormat": {"bold": True}})
        worksheet.format("A2:R2", {"textFormat": {"bold": True}})
        for range_name in ["A1:G1", "H1:I1", "J1:L1", "N1:P1"]:
            worksheet.merge_cells(range_name)
    except Exception:
        pass


@st.cache_resource
def get_google_worksheet():
    try:
        credentials_dict, spreadsheet_id, spreadsheet_name, worksheet_name = get_google_sheet_settings()

        if credentials_dict is None:
            st.error(
                "Google credentials are not configured. Add `.streamlit/secrets.toml` "
                "or keep a local `credentials.json` beside `app.py`."
            )
            st.stop()

        if isinstance(credentials_dict, str):
            credentials = Credentials.from_service_account_file(credentials_dict, scopes=SCOPES)
        else:
            credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
        client = gspread.authorize(credentials)

        if spreadsheet_id:
            spreadsheet = client.open_by_key(spreadsheet_id)
        else:
            spreadsheet = client.open(spreadsheet_name)

        return spreadsheet.worksheet(worksheet_name)
    except Exception as e:
        show_sheet_error(
            "Google Sheets connection failed. Check Streamlit secrets, spreadsheet ID, "
            "spreadsheet name, worksheet name, and whether the service account has "
            "access to the sheet.",
            e,
        )


def ensure_header_row(worksheet, rows=None):
    rows = rows if rows is not None else worksheet.get_all_values()
    first_row = rows[0] if rows else []
    second_row = rows[1] if len(rows) > 1 else []

    if not rows or not any(cell.strip() for cell in first_row):
        worksheet.update(values=[GROUP_HEADER_ROW, COLUMNS], range_name="A1")
        apply_reference_sheet_layout(worksheet)
        return COLUMNS, []

    normalized_group_row = normalize_row(first_row, len(GROUP_HEADER_ROW))
    normalized_header = normalize_row(second_row, len(COLUMNS))

    if normalized_group_row != GROUP_HEADER_ROW:
        worksheet.insert_row(GROUP_HEADER_ROW, index=1)
        apply_reference_sheet_layout(worksheet)
        rows = worksheet.get_all_values()
        normalized_header = normalize_row(rows[1], len(COLUMNS)) if len(rows) > 1 else []

    if normalized_header != COLUMNS:
        worksheet.update(values=[COLUMNS], range_name="A2")
        apply_reference_sheet_layout(worksheet)
        normalized_header = COLUMNS

    duplicates = sorted(
        {
            name
            for name in normalized_header
            if name and normalized_header.count(name) > 1
        }
    )
    has_blank_headers = len(normalized_header) != len([name for name in normalized_header if name])
    use_expected_columns = bool(duplicates or has_blank_headers)

    if duplicates:
        st.warning(
            "Your Google Sheet has duplicate header names: "
            f"{', '.join(duplicates)}. Repairing the header row and loading by "
            "the expected journal columns."
        )
    if has_blank_headers:
        st.warning(
            "Your Google Sheet has blank header cells. Repairing the header row and "
            "loading by the expected journal columns."
        )
    if use_expected_columns:
        worksheet.update(values=[COLUMNS], range_name="A2")
        apply_reference_sheet_layout(worksheet)

    if normalized_header != COLUMNS:
        missing = [column for column in COLUMNS if column not in normalized_header]
        extra = [column for column in normalized_header if column and column not in COLUMNS]
        if missing:
            st.info(
                "Your Google Sheet header row is missing expected journal columns: "
                f"{', '.join(missing)}. New saves will use the app's expected column order."
            )
        if extra:
            st.info(
                "Your Google Sheet has extra columns not used by the app: "
                f"{', '.join(extra)}."
            )

    return COLUMNS if use_expected_columns else normalized_header, rows[2:]


@st.cache_data(ttl=300)
def load_trades():
    try:
        worksheet = get_google_worksheet()
        rows = worksheet.get_all_values()
        header, data_rows = ensure_header_row(worksheet, rows)

        if not data_rows:
            return pd.DataFrame(columns=COLUMNS)

        records = []
        for row in data_rows:
            padded_row = row + [""] * max(len(header) - len(row), 0)
            record = dict(zip(header, padded_row))
            records.append({column: record.get(column, "") for column in COLUMNS})

        df = pd.DataFrame(records, columns=COLUMNS)
        for column in NUMERIC_COLUMNS:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
        return df
    except Exception as e:
        show_sheet_error(
            "Failed to load trades from Google Sheets. The app now avoids "
            "gspread.get_all_records(), so this is likely a permissions, worksheet "
            "name, or sheet format issue.",
            e,
        )


def save_trade(trade_dict):
    try:
        worksheet = get_google_worksheet()
        _, data_rows = ensure_header_row(worksheet)
        row_count_before = len(data_rows)
        worksheet.append_row(
            [trade_dict.get(column, "") for column in COLUMNS],
            value_input_option="RAW",
            table_range="A2:R",
        )
        load_trades.clear()
        saved_rows = load_trades()
        if len(saved_rows) <= row_count_before:
            st.warning(
                "Google accepted the save request, but the new row was not found in "
                "the expected A:R table. Check whether another spreadsheet named "
                "`Trading Journal` is being opened."
            )
    except Exception as e:
        show_sheet_error("Failed to save trade to Google Sheets.", e)


# ===================== UI =====================
tab1, tab2, tab3 = st.tabs(["New Trade", "Trade History", "Analytics"])


# ------------------- TAB 1: New Trade -------------------
with tab1:
    st.header("Log New Trade")

    col1, col2, col3 = st.columns(3)

    with col1:
        date = st.date_input("Date", datetime.now().date())
        instrument = st.selectbox(
            "Instrument",
            ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "STOCK", "Other"],
        )
        strategy = st.text_input("Strategy (e.g., Bull Call Spread)")
        expected_move = st.number_input("Expected move", format="%.2f", value=0.0)

    with col2:
        pos_size = st.number_input("position Size", min_value=1, value=1)
        entry = st.number_input("Entry Price", format="%.2f", value=0.0)
        exit_price = st.number_input("Exit Price", format="%.2f", value=0.0)
        stop_loss = st.number_input("Stop Loss", format="%.2f")
        target = st.number_input("Target", format="%.2f")

    with col3:
        outcome_preview = (exit_price - entry) * pos_size * (50 if "NIFTY" in instrument else 1)
        st.metric("Outcome", f"INR {outcome_preview:,.2f}")

    followed = st.radio("Did you follow your plan?", ["Yes", "No", "Partially"])
    slippage = st.text_area("Slippage / late entry / early exit")
    adjustment = st.text_area("Any adjustment made")

    emo_before = st.multiselect(
        "Emotion before trade",
        ["Confident", "Fearful", "FOMO", "Neutral", "Excited"],
    )
    emo_during = st.multiselect(
        "During trade",
        ["Patience", "Panic", "Overconfidence", "Calm"],
    )
    emo_after = st.multiselect(
        "After trade",
        ["Satisfaction", "Regret", "Neutral", "Frustrated"],
    )

    learning = st.text_area("What Worked / What Failed")
    improvement = st.text_area("Improvement")

    if st.button("Save Trade", type="primary", use_container_width=True):
        multiplier = 50 if "NIFTY" in instrument else 1
        outcome = (exit_price - entry) * pos_size * multiplier

        trade = {
            "Date": str(date),
            "Instrument": instrument,
            "Stratergy": strategy,
            "position Size": pos_size,
            "Entry": entry,
            "Exit": exit_price,
            "Expected move": expected_move,
            "Stop Loss": stop_loss,
            "Target": target,
            "Did you follow your plan?": followed,
            "Slippage / late entry / early exit": slippage,
            "Any adjustment made": adjustment,
            "Outcome": round(outcome, 2),
            "Emotion before trade( confident, fearful, FOMO)": ", ".join(emo_before),
            "During trade: (panic, patience, overconfidence)": ", ".join(emo_during),
            "After trade: (regret, satisfaction)": ", ".join(emo_after),
            "What Worked / What Failed": learning,
            "Improvement": improvement,
        }

        save_trade(trade)
        st.success("Trade saved successfully!")
        st.rerun()


# ------------------- TAB 2: Trade History -------------------
with tab2:
    st.header("Trade History")
    df = load_trades()

    if not df.empty:
        st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True, height=600)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download as CSV", csv, "trading_journal.csv", "text/csv")
    else:
        st.info("No trades yet. Log your first trade!")


# ------------------- TAB 3: Analytics -------------------
with tab3:
    st.header("Performance Analytics")
    df = load_trades()

    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        total_trades = len(df)
        win_rate = len(df[df["Outcome"] > 0]) / total_trades * 100 if total_trades > 0 else 0
        total_outcome = df["Outcome"].sum()
        avg_outcome = df["Outcome"].mean()

        col1.metric("Total Trades", total_trades)
        col2.metric("Win Rate", f"{win_rate:.1f}%")
        col3.metric("Total Outcome", f"INR {total_outcome:,.0f}", delta=None)
        col4.metric("Avg Outcome", f"INR {avg_outcome:,.0f}")

        df_sorted = df.sort_values("Date")
        df_sorted["Cumulative Outcome"] = df_sorted["Outcome"].cumsum()

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df_sorted["Date"],
                y=df_sorted["Cumulative Outcome"],
                mode="lines+markers",
                name="Equity Curve",
            )
        )
        fig.update_layout(title="Equity Curve", height=400)
        st.plotly_chart(fig, use_container_width=True)

        strategy_perf = df.groupby("Stratergy").agg(
            Trades=("Outcome", "count"),
            WinRate=("Outcome", lambda x: (x > 0).mean() * 100),
            AvgOutcome=("Outcome", "mean"),
        ).round(2)
        st.plotly_chart(
            px.bar(strategy_perf, y="WinRate", title="Win Rate by Strategy"),
            use_container_width=True,
        )

        st.subheader("Psychology Impact")
        emo_df = df.copy()
        emotion_column = "Emotion before trade( confident, fearful, FOMO)"
        emo_df[emotion_column] = emo_df[emotion_column].str.split(", ")
        emo_exploded = emo_df.explode(emotion_column)
        emo_perf = emo_exploded.groupby(emotion_column)["Outcome"].agg(["count", "mean"]).round(2)
        st.dataframe(emo_perf)
    else:
        st.warning("Add some trades to see analytics!")


with st.sidebar:
    st.header("About")
    st.info("Your trading edge compounds through disciplined journaling.")
    st.caption("Built for Saurav - Velocity Trading")
