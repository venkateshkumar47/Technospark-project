# ==============================================================================
# MODULE 3: STREAMLIT UI & DASHBOARD VIEW
# ==============================================================================
# This module is ONLY responsible for presentation and accessibility.
# It receives an already-audited DataFrame from audit_engine.py and renders
# an explainable settlement audit dashboard for merchants.
# ==============================================================================

import streamlit as st
import pandas as pd
import plotly.express as px


def render_ui(audited_df: pd.DataFrame):
    """
    Renders the Streamlit dashboard using the audited DataFrame.
    
    Dashboard Layout Order:
      A. Page Header
      B. KPI Cards
      C. Filters (Sidebar)
      D. Audited Transactions Table (with Discrepancy Row Highlighting & Status)
      E. Transaction Details & Explainability Section
      F. Visual Analytics / Charts (Moved to the bottom)
    """
    # -------------------------------------------------------------------------
    # A. Page Header & Configuration
    # -------------------------------------------------------------------------
    try:
        st.set_page_config(page_title="Merchant MDR Copilot", page_icon="💳", layout="wide")
    except Exception:
        pass
    st.title("💳 Merchant MDR Settlement Copilot")
    st.caption("Explainable settlement audit & fee discrepancy dashboard")

    # Graceful handling if DataFrame is None or empty
    if audited_df is None or audited_df.empty:
        st.info("ℹ️ No audited transaction data available to display.")
        return

    # -------------------------------------------------------------------------
    # C. Filters (Sidebar Controls)
    # -------------------------------------------------------------------------
    filtered_df = audited_df.copy()

    st.sidebar.header("🔍 Filter Transactions")

    # Filter 1: Status Filter ('All', 'Clean', 'Discrepancy Detected')
    if "Audit_Status" in filtered_df.columns:
        unique_statuses = sorted(filtered_df["Audit_Status"].dropna().unique().tolist())
        status_options = ["All"] + unique_statuses
        selected_status = st.sidebar.selectbox("Audit Status", status_options)

        if selected_status != "All":
            filtered_df = filtered_df[filtered_df["Audit_Status"] == selected_status]

    # Filter 2: Date Range Filter
    if "Date" in audited_df.columns:
        all_dates = pd.to_datetime(audited_df["Date"]).dt.date
        min_date, max_date = all_dates.min(), all_dates.max()

        selected_dates = st.sidebar.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2:
            start_date, end_date = selected_dates
            row_dates = pd.to_datetime(filtered_df["Date"]).dt.date
            filtered_df = filtered_df[
                (row_dates >= start_date) & (row_dates <= end_date)
            ]

    # Filter 3: Transaction Amount Slider Filter
    if "Amount" in audited_df.columns:
        min_amt = float(audited_df["Amount"].min())
        max_amt = float(audited_df["Amount"].max())

        if min_amt < max_amt:
            step_val = max(1.0, min(100.0, round((max_amt - min_amt) / 50, 2)))
            selected_amt_range = st.sidebar.slider(
                "Transaction Amount (₹)",
                min_value=min_amt,
                max_value=max_amt,
                value=(min_amt, max_amt),
                step=step_val,
            )
            filtered_df = filtered_df[
                (filtered_df["Amount"] >= selected_amt_range[0])
                & (filtered_df["Amount"] <= selected_amt_range[1])
            ]

    st.sidebar.caption(f"Showing {len(filtered_df)} of {len(audited_df)} transactions")

    # -------------------------------------------------------------------------
    # B. KPI Cards
    # -------------------------------------------------------------------------
    total_transactions = len(filtered_df)
    total_amount = (
        filtered_df["Amount"].sum()
        if "Amount" in filtered_df.columns and total_transactions > 0
        else 0.0
    )
    total_overcharge = (
        filtered_df["Discrepancy_Amount"].sum()
        if "Discrepancy_Amount" in filtered_df.columns and total_transactions > 0
        else 0.0
    )

    if "Audit_Status" in filtered_df.columns and total_transactions > 0:
        flagged_count = (filtered_df["Audit_Status"] != "Clean").sum()
    else:
        flagged_count = 0

    discrepancy_rate = (
        (flagged_count / total_transactions * 100)
        if total_transactions > 0
        else 0.0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Total Transactions", value=f"{total_transactions:,}")
    col2.metric(label="Total Transaction Amount", value=f"₹{total_amount:,.2f}")
    col3.metric(label="Potential Overcharge", value=f"₹{total_overcharge:,.2f}")
    col4.metric(label="Discrepancy Rate", value=f"{discrepancy_rate:.1f}%")

    st.divider()

    # Graceful Zero-Row Check
    if filtered_df.empty:
        st.warning(
            "⚠️ No transactions match your selected filter criteria. "
            "Try broadening the filters in the sidebar."
        )
        return

    # -------------------------------------------------------------------------
    # D. Audited Transactions Table (with Highlighted Discrepancies)
    # -------------------------------------------------------------------------
    st.subheader("📋 Audited Transactions")
    st.caption("Rows with fee discrepancies are highlighted in light red. Audit_Status includes icons for accessibility.")

    # Table columns to display (keeping underlying column names intact)
    display_columns = [
        "Transaction_ID",
        "Date",
        "Amount",
        "Payment_Mode",
        "Merchant_Category",
        "Settled_Amount",
        "Actual_Fee_Deducted",
        "Expected_Fee",
        "Discrepancy_Amount",
        "Audit_Status",
    ]
    available_cols = [c for c in display_columns if c in filtered_df.columns]
    table_df = filtered_df[available_cols].copy()

    # Make status accessible: Add clear icon prefix to text (does not rely on color alone)
    if "Audit_Status" in table_df.columns:
        table_df["Audit_Status"] = table_df["Audit_Status"].map(
            {
                "Clean": "✅ Clean",
                "Discrepancy Detected": "⚠️ Discrepancy Detected",
            }
        ).fillna(table_df["Audit_Status"])

    # Highlighting function: Discrepancy Detected rows get a soft warning-red background
    def highlight_discrepant_rows(row):
        if "Discrepancy Detected" in str(row.get("Audit_Status", "")):
            return ["background-color: #FCE8E6; color: #8A1C14; font-weight: 500"] * len(row)
        return [""] * len(row)

    # Format currency fields to ₹%.2f
    currency_formats = {}
    for col in ["Amount", "Settled_Amount", "Actual_Fee_Deducted", "Expected_Fee", "Discrepancy_Amount"]:
        if col in table_df.columns:
            currency_formats[col] = "₹{:.2f}"

    styled_table = table_df.style.apply(highlight_discrepant_rows, axis=1).format(currency_formats)

    st.dataframe(styled_table, use_container_width=True, hide_index=True)

    st.divider()

    # -------------------------------------------------------------------------
    # E. Transaction Details / Explanation
    # -------------------------------------------------------------------------
    st.subheader("🔍 Transaction Details & Explanation")
    st.caption("Select any transaction to inspect its detailed breakdown and explainability report.")

    if "Transaction_ID" in filtered_df.columns and len(filtered_df) > 0:
        txn_list = filtered_df["Transaction_ID"].tolist()
        selected_txn_id = st.selectbox("Select a Transaction ID to inspect:", txn_list)

        # Get the record for the selected transaction
        selected_row = filtered_df[filtered_df["Transaction_ID"] == selected_txn_id].iloc[0]

        # Display itemized values in clean columns
        detail_col1, detail_col2, detail_col3 = st.columns(3)

        with detail_col1:
            st.markdown(f"**Transaction ID:** `{selected_row['Transaction_ID']}`")
            st.markdown(f"**Date:** {selected_row.get('Date', 'N/A')}")
            st.markdown(f"**Payment Mode:** {selected_row.get('Payment_Mode', 'N/A')}")

        with detail_col2:
            st.markdown(f"**Amount:** ₹{selected_row.get('Amount', 0.0):,.2f}")
            st.markdown(f"**Settled Amount:** ₹{selected_row.get('Settled_Amount', 0.0):,.2f}")
            st.markdown(f"**Category:** {selected_row.get('Merchant_Category', 'N/A')}")

        with detail_col3:
            st.markdown(f"**Expected Fee:** ₹{selected_row.get('Expected_Fee', 0.0):,.2f}")
            st.markdown(f"**Actual Fee Deducted:** ₹{selected_row.get('Actual_Fee_Deducted', 0.0):,.2f}")
            st.markdown(f"**Discrepancy Amount:** ₹{selected_row.get('Discrepancy_Amount', 0.0):,.2f}")

        # Plain-English, accessible explanation based on Audit_Status
        if selected_row.get("Audit_Status") == "Discrepancy Detected":
            st.error(
                f"⚠️ **Audit Finding: Discrepancy Detected**\n\n"
                f"- **Processor Deduction:** ₹{selected_row['Actual_Fee_Deducted']:,.2f}\n"
                f"- **Expected Regulatory Fee:** ₹{selected_row['Expected_Fee']:,.2f}\n"
                f"- **Overcharge Amount:** ₹{selected_row['Discrepancy_Amount']:,.2f}\n\n"
                f"**Explanation:** The processor deducted more than the regulatory fee cap for this transaction. "
                f"A claim of **₹{selected_row['Discrepancy_Amount']:,.2f}** can be initiated."
            )
        else:
            st.success(
                f"✅ **Audit Finding: Clean Settlement**\n\n"
                f"- **Processor Deduction:** ₹{selected_row['Actual_Fee_Deducted']:,.2f}\n"
                f"- **Expected Regulatory Fee:** ₹{selected_row['Expected_Fee']:,.2f}\n"
                f"- **Discrepancy:** ₹0.00\n\n"
                f"**Explanation:** The fee charged accurately matches the regulatory MDR rate. No overcharge was detected."
            )

    st.divider()

    # -------------------------------------------------------------------------
    # F. Visual Analytics / Charts (Positioned at the Bottom)
    # -------------------------------------------------------------------------
    st.subheader("📊 Audit Analytics & Visual Insights")

    chart_col1, chart_col2 = st.columns(2)

    # Chart 1: Expected Fee vs Actual Fee Deducted Comparison
    with chart_col1:
        if (
            "Transaction_ID" in filtered_df.columns
            and "Expected_Fee" in filtered_df.columns
            and "Actual_Fee_Deducted" in filtered_df.columns
        ):
            fee_df = filtered_df[
                ["Transaction_ID", "Expected_Fee", "Actual_Fee_Deducted"]
            ].melt(
                id_vars=["Transaction_ID"],
                value_vars=["Expected_Fee", "Actual_Fee_Deducted"],
                var_name="Fee Type",
                value_name="Fee",
            )
            fee_df["Fee Type"] = fee_df["Fee Type"].map(
                {
                    "Expected_Fee": "Expected Fee",
                    "Actual_Fee_Deducted": "Actual Fee Deducted",
                }
            )

            fig_fee = px.bar(
                fee_df,
                x="Transaction_ID",
                y="Fee",
                color="Fee Type",
                barmode="group",
                title="Expected vs Actual Fee per Transaction",
                labels={"Transaction_ID": "Transaction ID", "Fee": "Fee (₹)"},
                color_discrete_map={
                    "Expected Fee": "#2ECC71",         # Green: Fair rate
                    "Actual Fee Deducted": "#E74C3C",  # Red: Deducted rate
                },
                template="plotly_white",
            )
            fig_fee.update_layout(
                legend_title_text="",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(tickangle=-45),
            )
            st.plotly_chart(fig_fee, use_container_width=True)

    # Chart 2: Number of Transactions by Audit Status
    with chart_col2:
        if "Audit_Status" in filtered_df.columns:
            status_counts = filtered_df["Audit_Status"].value_counts().reset_index()
            status_counts.columns = ["Audit Status", "Count"]

            fig_status = px.pie(
                status_counts,
                names="Audit Status",
                values="Count",
                hole=0.45,
                title="Audit Status Breakdown",
                color="Audit Status",
                color_discrete_map={
                    "Clean": "#2ECC71",                 # Green
                    "Discrepancy Detected": "#E74C3C",  # Red
                },
                template="plotly_white",
            )
            fig_status.update_traces(
                textposition="inside",
                textinfo="percent+label",
            )
            st.plotly_chart(fig_status, use_container_width=True)

    # Chart 3: Overcharge Trend by Date (Full Width)
    if "Date" in filtered_df.columns and "Discrepancy_Amount" in filtered_df.columns:
        trend_df = (
            filtered_df.groupby("Date", as_index=False)["Discrepancy_Amount"]
            .sum()
            .sort_values("Date")
        )

        fig_trend = px.line(
            trend_df,
            x="Date",
            y="Discrepancy_Amount",
            markers=True,
            title="📈 Daily Overcharge Trend (₹)",
            labels={"Date": "Settlement Date", "Discrepancy_Amount": "Total Overcharge (₹)"},
            template="plotly_white",
        )
        fig_trend.update_traces(
            line=dict(color="#E74C3C", width=3),
            marker=dict(size=9, color="#C0392B"),
        )
        fig_trend.update_layout(yaxis=dict(rangemode="tozero"))
        st.plotly_chart(fig_trend, use_container_width=True)


# ==============================================================================
# INTEGRATION TEST HARNESS (Connected to real pipeline & audit engine)
# ==============================================================================
if __name__ == "__main__":
    try:
        from src.data_pipeline import generate_mock_data
        from src.audit_engine import run_audit
    except ImportError:
        from data_pipeline import generate_mock_data
        from audit_engine import run_audit

    # 1. Pipeline loads/generates transactions
    raw_df = generate_mock_data()

    # 2. Audit engine processes MDR rules and computes discrepancies
    audited_df = run_audit(raw_df)

    # 3. Module 3 presents the final audited results
    render_ui(audited_df)
