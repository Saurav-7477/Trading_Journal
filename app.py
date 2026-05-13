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
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 3rem;
        max-width: 1680px;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #171b22 0%, #101319 100%);
        border: 1px solid #2a303a;
        border-radius: 8px;
        padding: 16px 18px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.16);
    }
    div[data-testid="stMetricLabel"] {
        color: #aab2c0;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.7rem;
    }
    .section-note {
        color: #aab2c0;
        margin-top: -0.35rem;
        margin-bottom: 1rem;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #2a303a;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ===================== HEADERS =====================
COLUMNS = [
    "Date",
    "Instrument",
    "Strategy",
    "Position Size",
    "Entry",
    "Exit",
    "Exit Type",
    "SL Price",
    "P&L",
    "R-Multiple",
    "Setup Quality (1-5)",
    "Execution Score (1-5)",
    "Followed Plan?",
    "Mistake Type",
    "Psychology Note",
    "Key Learning",
]

GROUP_HEADER_ROW = [
    "SECTION 1 - Trade Setup",
    "",
    "",
    "",
    "",
    "",
    "",
    "SECTION 2 - Risk & Performance",
    "",
    "",
    "",
    "",
    "SECTION 3 - Discipline & Psychology",
    "",
    "",
    "",
]

LEGACY_COLUMN_ALIASES = {
    "Stratergy": "Strategy",
    "position Size": "Position Size",
    "Outcome": "P&L",
    "Did you follow your plan?": "Followed Plan?",
    "Any adjustment made": "Mistake Type",
    "Emotion before trade( confident, fearful, FOMO)": "Psychology Note",
    "What Worked / What Failed": "Key Learning",
}

NUMERIC_COLUMNS = [
    "Position Size",
    "Entry",
    "Exit",
    "SL Price",
    "P&L",
    "R-Multiple",
    "Setup Quality (1-5)",
    "Execution Score (1-5)",
]

PLAN_VALUES = ["Yes", "No", "Partially"]
EXIT_TYPES = ["Target Hit", "Stop Loss Hit", "Manual Exit", "Trailing Stop", "Time Exit", "Partial Exit"]
MISTAKE_TYPES = [
    "None",
    "Late Entry",
    "Early Entry",
    "Late Exit",
    "Early Exit",
    "Oversized",
    "No Stop",
    "Moved Stop",
    "Revenge Trade",
    "FOMO",
    "Other",
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
        worksheet.batch_clear(["Q1:Z2"])
        worksheet.freeze(rows=2)
        worksheet.format("A1:P1", {"textFormat": {"bold": True}})
        worksheet.format("A2:P2", {"textFormat": {"bold": True}})
        for range_name in ["A1:G1", "H1:L1", "M1:P1"]:
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
        worksheet.update(values=[GROUP_HEADER_ROW], range_name="A1")
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
            for old_column, new_column in LEGACY_COLUMN_ALIASES.items():
                if not record.get(new_column) and record.get(old_column):
                    record[new_column] = record[old_column]
            cleaned_record = {column: str(record.get(column, "")).strip() for column in COLUMNS}
            if any(value for value in cleaned_record.values()):
                records.append(cleaned_record)

        df = pd.DataFrame(records, columns=COLUMNS)
        text_columns = [column for column in COLUMNS if column not in NUMERIC_COLUMNS]
        for column in text_columns:
            df[column] = df[column].astype(str).str.strip()
        for column in NUMERIC_COLUMNS:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
        has_identity = (
            df["Date"].astype(str).str.strip().ne("")
            | df["Instrument"].astype(str).str.strip().ne("")
            | df["Strategy"].astype(str).str.strip().ne("")
        )
        has_trade_values = df[["Entry", "Exit", "SL Price", "P&L"]].abs().sum(axis=1) > 0
        return df[has_identity | has_trade_values].reset_index(drop=True)
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
            table_range="A2:P",
        )
        saved_rows = load_trades()
        if len(saved_rows) <= row_count_before:
            st.warning(
                "Google accepted the save request, but the new row was not found in "
                "the expected A:P table. Check whether another spreadsheet named "
                "`Trading Journal` is being opened."
            )
    except Exception as e:
        show_sheet_error("Failed to save trade to Google Sheets.", e)


def get_analytics_df(df):
    if df.empty:
        return df.copy()

    analytics_df = df.copy()
    analytics_df = analytics_df[analytics_df["Followed Plan?"].isin(PLAN_VALUES)]
    analytics_df = analytics_df[analytics_df["SL Price"] > 0]
    analytics_df = analytics_df[analytics_df["Strategy"].astype(str).str.strip() != ""]
    return analytics_df


def process_score(df):
    if df.empty:
        return 0
    plan_component = df["Followed Plan?"].map({"Yes": 5, "Partially": 3, "No": 1}).fillna(0)
    return ((plan_component + df["Setup Quality (1-5)"] + df["Execution Score (1-5)"]) / 3).mean()


# ===================== UI =====================
tab1, tab2, tab3 = st.tabs(["New Trade", "Trade History", "Discipline Analytics"])


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
        pos_size = st.number_input("Position Size", min_value=1, value=1)

    with col2:
        entry = st.number_input("Entry Price", format="%.2f", value=0.0)
        exit_price = st.number_input("Exit Price", format="%.2f", value=0.0)
        exit_type = st.selectbox(
            "Exit Type",
            EXIT_TYPES,
        )
        sl_price = st.number_input("SL Price", min_value=0.0, format="%.2f", value=0.0)

    setup_quality = st.slider("Setup Quality (1-5)", min_value=1, max_value=5, value=3)
    execution_score = st.slider("Execution Score (1-5)", min_value=1, max_value=5, value=3)
    followed = st.radio("Followed Plan?", PLAN_VALUES)
    mistake_type = st.selectbox(
        "Mistake Type",
        MISTAKE_TYPES,
    )
    psychology_note = st.text_area("Psychology Note")
    learning = st.text_area("Key Learning")

    with col3:
        multiplier = 50 if "NIFTY" in instrument else 1
        risk_amount = abs(entry - sl_price) * pos_size * multiplier
        pnl_preview = (exit_price - entry) * pos_size * multiplier
        r_multiple_preview = pnl_preview / risk_amount if risk_amount else 0
        plan_score = {"Yes": 5, "Partially": 3, "No": 1}[followed]
        current_process_score = (plan_score + setup_quality + execution_score) / 3
        st.metric("Risk From SL", f"{risk_amount:,.2f}")
        st.metric("R-Multiple", f"{r_multiple_preview:.2f}R")
        st.metric("Process Score", f"{current_process_score:.2f}/5")
        st.caption("Risk = |Entry - SL Price| x position size. R-Multiple = P&L / risk.")

    if st.button("Save Trade", type="primary", use_container_width=True):
        multiplier = 50 if "NIFTY" in instrument else 1
        risk_amount = abs(entry - sl_price) * pos_size * multiplier
        if risk_amount <= 0:
            st.error("SL Price must create a non-zero risk distance from Entry to calculate R-Multiple.")
            st.stop()

        pnl = (exit_price - entry) * pos_size * multiplier
        r_multiple = pnl / risk_amount if risk_amount else 0

        trade = {
            "Date": str(date),
            "Instrument": instrument,
            "Strategy": strategy,
            "Position Size": pos_size,
            "Entry": entry,
            "Exit": exit_price,
            "Exit Type": exit_type,
            "SL Price": round(sl_price, 2),
            "P&L": round(pnl, 2),
            "R-Multiple": round(r_multiple, 2),
            "Setup Quality (1-5)": setup_quality,
            "Execution Score (1-5)": execution_score,
            "Followed Plan?": followed,
            "Mistake Type": mistake_type,
            "Psychology Note": psychology_note,
            "Key Learning": learning,
        }

        save_trade(trade)
        st.success("Trade saved successfully!")
        st.rerun()


# ------------------- TAB 2: Trade History -------------------
with tab2:
    st.header("Trade History")
    if st.button("Refresh from Google Sheets", key="refresh_history"):
        st.rerun()
    df = load_trades()

    if not df.empty:
        history_df = df.copy()
        history_df["_DateSort"] = pd.to_datetime(history_df["Date"], errors="coerce")
        history_df = history_df.sort_values("_DateSort", ascending=False).drop(columns=["_DateSort"])
        st.caption(f"Showing {len(history_df)} trade row{'s' if len(history_df) != 1 else ''} from Google Sheets.")
        st.dataframe(
            history_df,
            use_container_width=True,
            height=min(760, 120 + len(history_df) * 44),
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("Date", width="medium"),
                "Instrument": st.column_config.TextColumn("Instrument", width="medium"),
                "Strategy": st.column_config.TextColumn("Strategy", width="large"),
                "Position Size": st.column_config.NumberColumn("Position Size", width="medium"),
                "Entry": st.column_config.NumberColumn("Entry", width="small", format="%.2f"),
                "Exit": st.column_config.NumberColumn("Exit", width="small", format="%.2f"),
                "Exit Type": st.column_config.TextColumn("Exit Type", width="large"),
                "SL Price": st.column_config.NumberColumn("SL Price", width="medium", format="%.2f"),
                "P&L": st.column_config.NumberColumn("P&L", width="medium", format="%.2f"),
                "R-Multiple": st.column_config.NumberColumn("R-Multiple", width="medium", format="%.2f"),
                "Setup Quality (1-5)": st.column_config.NumberColumn("Setup Quality", width="medium"),
                "Execution Score (1-5)": st.column_config.NumberColumn("Execution Score", width="medium"),
                "Followed Plan?": st.column_config.TextColumn("Followed Plan?", width="medium"),
                "Mistake Type": st.column_config.TextColumn("Mistake Type", width="large"),
                "Psychology Note": st.column_config.TextColumn("Psychology Note", width="large"),
                "Key Learning": st.column_config.TextColumn("Key Learning", width="large"),
            },
        )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download as CSV", csv, "trading_journal.csv", "text/csv")
    else:
        st.info("No trades yet. Log your first trade!")


# ------------------- TAB 3: Analytics -------------------
with tab3:
    st.header("Discipline Analytics")
    st.markdown(
        '<p class="section-note">Freshly fetched from Google Sheets on every rerun. '
        'The dashboard prioritizes process quality, discipline, and R-based thinking over rupee totals.</p>',
        unsafe_allow_html=True,
    )
    if st.button("Refresh analytics", key="refresh_analytics"):
        st.rerun()
    df = load_trades()
    analytics_df = get_analytics_df(df)

    if not analytics_df.empty:
        total_trades = len(analytics_df)
        wins = analytics_df[analytics_df["P&L"] > 0]
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        avg_r_multiple = analytics_df["R-Multiple"].mean()
        adherence_rate = (analytics_df["Followed Plan?"] == "Yes").mean() * 100
        mistake_free_rate = (analytics_df["Mistake Type"] == "None").mean() * 100
        avg_setup = analytics_df["Setup Quality (1-5)"].mean()
        avg_execution = analytics_df["Execution Score (1-5)"].mean()
        avg_process = process_score(analytics_df)
        best_r = analytics_df["R-Multiple"].max()
        worst_r = analytics_df["R-Multiple"].min()

        metric_row_1 = st.columns(4)
        metric_row_1[0].metric("Total Trades", total_trades)
        metric_row_1[1].metric("Plan Adherence", f"{adherence_rate:.1f}%")
        metric_row_1[2].metric("Process Score", f"{avg_process:.2f}/5")
        metric_row_1[3].metric("Avg R-Multiple", f"{avg_r_multiple:.2f}R")

        metric_row_2 = st.columns(4)
        metric_row_2[0].metric("Mistake-Free Rate", f"{mistake_free_rate:.1f}%")
        metric_row_2[1].metric("Avg Setup Quality", f"{avg_setup:.2f}/5")
        metric_row_2[2].metric("Avg Execution", f"{avg_execution:.2f}/5")
        metric_row_2[3].metric("Best / Worst R", f"{best_r:.2f}R / {worst_r:.2f}R")

        analytics_df = analytics_df.copy()
        analytics_df["Trade Date"] = pd.to_datetime(analytics_df["Date"], errors="coerce")
        analytics_df = analytics_df.sort_values(["Trade Date", "Date"], na_position="last")
        analytics_df["Trade #"] = range(1, len(analytics_df) + 1)
        analytics_df["Cumulative R"] = analytics_df["R-Multiple"].cumsum()
        analytics_df["Process Score"] = (
            analytics_df["Followed Plan?"].map({"Yes": 5, "Partially": 3, "No": 1}).fillna(0)
            + analytics_df["Setup Quality (1-5)"]
            + analytics_df["Execution Score (1-5)"]
        ) / 3
        analytics_df["Abs R"] = analytics_df["R-Multiple"].abs().clip(lower=0.2)

        left, right = st.columns([1.35, 1])
        with left:
            equity_fig = go.Figure()
            equity_fig.add_trace(
                go.Scatter(
                    x=analytics_df["Trade #"],
                    y=analytics_df["Cumulative R"],
                    mode="lines+markers",
                    fill="tozeroy",
                    name="Cumulative R",
                    line=dict(color="#22c55e", width=3),
                    marker=dict(size=7),
                )
            )
            equity_fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#64748b")
            equity_fig.update_layout(
                title="Cumulative R Curve",
                height=430,
                template="plotly_dark",
                margin=dict(l=20, r=20, t=55, b=30),
                xaxis_title="Trade #",
                yaxis_title="Cumulative R",
            )
            st.plotly_chart(equity_fig, use_container_width=True)

        with right:
            r_fig = px.histogram(
                analytics_df,
                x="R-Multiple",
                nbins=18,
                title="R-Multiple Distribution",
                color_discrete_sequence=["#38bdf8"],
                template="plotly_dark",
            )
            r_fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="#f87171")
            r_fig.update_layout(height=430, margin=dict(l=20, r=20, t=55, b=30))
            st.plotly_chart(r_fig, use_container_width=True)

        strategy_perf = analytics_df.groupby("Strategy", as_index=False).agg(
            Trades=("P&L", "count"),
            WinRate=("P&L", lambda x: (x > 0).mean() * 100),
            AvgR=("R-Multiple", "mean"),
            ProcessScore=("Process Score", "mean"),
        )
        strategy_perf = strategy_perf.sort_values("ProcessScore", ascending=False)

        discipline_perf = analytics_df.groupby("Followed Plan?", as_index=False).agg(
            Trades=("R-Multiple", "count"),
            AvgR=("R-Multiple", "mean"),
            ProcessScore=("Process Score", "mean"),
        )
        discipline_perf["Followed Plan?"] = pd.Categorical(
            discipline_perf["Followed Plan?"],
            categories=PLAN_VALUES,
            ordered=True,
        )
        discipline_perf = discipline_perf.sort_values("Followed Plan?")

        chart_col_1, chart_col_2 = st.columns(2)
        with chart_col_1:
            strategy_fig = px.bar(
                strategy_perf,
                x="Strategy",
                y="ProcessScore",
                color="AvgR",
                hover_data=["Trades", "WinRate", "AvgR"],
                title="Strategy Process Quality",
                color_continuous_scale="RdYlGn",
                template="plotly_dark",
            )
            strategy_fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=70))
            st.plotly_chart(strategy_fig, use_container_width=True)

        with chart_col_2:
            discipline_fig = px.bar(
                discipline_perf,
                x="Followed Plan?",
                y="AvgR",
                color="ProcessScore",
                hover_data=["Trades", "ProcessScore"],
                title="Discipline Impact",
                color_continuous_scale="RdYlGn",
                template="plotly_dark",
            )
            discipline_fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#64748b")
            discipline_fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=50))
            st.plotly_chart(discipline_fig, use_container_width=True)

        quality_col, mistakes_col = st.columns(2)
        with quality_col:
            quality_fig = px.scatter(
                analytics_df,
                x="Setup Quality (1-5)",
                y="Execution Score (1-5)",
                size="Abs R",
                color="R-Multiple",
                hover_data=["Strategy", "Mistake Type", "Followed Plan?"],
                title="Setup Quality vs Execution",
                color_continuous_scale="RdYlGn",
                template="plotly_dark",
            )
            quality_fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=40))
            st.plotly_chart(quality_fig, use_container_width=True)

        with mistakes_col:
            mistake_perf = analytics_df.groupby("Mistake Type", as_index=False).agg(
                Trades=("R-Multiple", "count"),
                AvgR=("R-Multiple", "mean"),
            )
            mistake_perf = mistake_perf[mistake_perf["Mistake Type"].astype(str).str.strip() != ""]
            mistake_perf = mistake_perf.sort_values("AvgR")
            mistake_fig = px.bar(
                mistake_perf,
                x="AvgR",
                y="Mistake Type",
                orientation="h",
                color="AvgR",
                hover_data=["Trades"],
                title="Mistake Cost in R",
                color_continuous_scale="RdYlGn",
                template="plotly_dark",
            )
            mistake_fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="#64748b")
            mistake_fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=40))
            st.plotly_chart(mistake_fig, use_container_width=True)

        st.subheader("Clean Discipline Summary")
        st.dataframe(
            discipline_perf.rename(
                columns={"AvgR": "Avg R-Multiple", "ProcessScore": "Process Score"}
            ),
            use_container_width=True,
            hide_index=True,
        )
    elif not df.empty:
        st.warning(
            "No current-structure trades are available for analytics yet. Add a new trade "
            "with SL Price and Followed Plan filled in, or clean old rows in Google Sheets."
        )
    else:
        st.warning("Add some trades to see analytics!")


with st.sidebar:
    st.header("About")
    st.info("Your trading edge compounds through disciplined journaling.")
    st.caption("Built for Saurav - Velocity Trading")
