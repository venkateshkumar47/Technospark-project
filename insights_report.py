"""
insights_report.py
------------------
Merchant MDR Copilot - Reporting & Insights Module

Responsibility:
    Accepts audited transaction data from audit_engine.py, identifies fee
    discrepancies (where Audit_Status == 'Discrepancy Detected'), displays clear
    plain-language business insights distinguishing overcharges and undercharges,
    and provides a download button for discrepancy_report.csv.

Design Principles:
    - Pure reporting: Accurately reflects audit_engine.py output without altering audit decisions.
    - Schema alignment: Seamlessly matches audit_engine.py and data_pipeline.py columns
      ('Actual_Fee_Deducted', 'Expected_Fee', 'Discrepancy_Amount', 'Audit_Status').
    - Safe & robust: Gracefully handles empty DataFrames, missing columns, zero discrepancies,
      and invalid numeric values.
"""

from typing import Optional
import pandas as pd
import streamlit as st

# ==============================================================================
# COLUMN MAPPINGS (Aligned with audit_engine.py and data_pipeline.py)
# ==============================================================================
COL_AUDIT_STATUS = "Audit_Status"
COL_DISCREPANCY_AMOUNT = "Discrepancy_Amount"
COL_EXPECTED_FEE = "Expected_Fee"
COL_ACTUAL_FEE_DEDUCTED = "Actual_Fee_Deducted"
COL_ACTUAL_FEE_FALLBACK = "Actual_Fee"
COL_TRANSACTION_ID = "Transaction_ID"
COL_MERCHANT_CATEGORY = "Merchant_Category"
COL_AMOUNT = "Amount"

# Expected status values from audit_engine.py
STATUS_CLEAN = "Clean"
STATUS_DISCREPANCY = "Discrepancy Detected"


def _resolve_actual_fee_col(df: pd.DataFrame) -> Optional[str]:
    """Identifies the actual fee column present in the DataFrame."""
    if COL_ACTUAL_FEE_DEDUCTED in df.columns:
        return COL_ACTUAL_FEE_DEDUCTED
    if COL_ACTUAL_FEE_FALLBACK in df.columns:
        return COL_ACTUAL_FEE_FALLBACK
    return None


def _get_discrepancy_series(df: pd.DataFrame) -> Optional[pd.Series]:
    """
    Safely retrieves or computes the discrepancy amount series.
    If 'Discrepancy_Amount' exists, it is converted to numeric.
    Otherwise, if actual fee and expected fee are present, computes:
    Actual_Fee - Expected_Fee.
    """
    if COL_DISCREPANCY_AMOUNT in df.columns:
        return pd.to_numeric(df[COL_DISCREPANCY_AMOUNT], errors="coerce").fillna(0.0)

    actual_col = _resolve_actual_fee_col(df)
    if actual_col and COL_EXPECTED_FEE in df.columns:
        actual = pd.to_numeric(df[actual_col], errors="coerce").fillna(0.0)
        expected = pd.to_numeric(df[COL_EXPECTED_FEE], errors="coerce").fillna(0.0)
        return (actual - expected).round(2)

    return None


def generate_plain_text_insights(audited_df: pd.DataFrame) -> None:
    """
    Analyzes audited transactions and displays clear plain-language insights.

    Key behaviors:
    - Safely handles None, empty DataFrames, and missing columns.
    - Focuses on transactions where Audit_Status is 'Discrepancy Detected'.
    - Displays total discrepancy count and total discrepancy amount.
    - Clearly distinguishes between overcharges (fee deducted > expected)
      and undercharges (fee deducted < expected) when fee data allows.
    - Highlights category concentration and actionable next steps.
    """
    # 1. Safely handle None or empty DataFrame
    if audited_df is None or not isinstance(audited_df, pd.DataFrame) or audited_df.empty:
        st.info("ℹ️ No audited transaction data available to analyze.")
        return

    # 2. Check for required Audit_Status column safely
    if COL_AUDIT_STATUS not in audited_df.columns:
        st.error(
            f"❌ Data Format Error: Missing required column '{COL_AUDIT_STATUS}'. "
            "Please ensure the transaction data has been processed by the audit engine."
        )
        return

    # 3. Identify transactions whose Audit_Status is 'Discrepancy Detected'
    discrepancy_mask = (
        audited_df[COL_AUDIT_STATUS].astype(str).str.strip().str.lower()
        == STATUS_DISCREPANCY.lower()
    )
    discrepancy_df = audited_df[discrepancy_mask].copy()
    discrepancy_count = len(discrepancy_df)

    # 4. Handle the zero discrepancies case cleanly
    if discrepancy_count == 0:
        st.success("✅ **Audit Clean**: All transactions match expected MDR rules.")
        st.caption("No fee discrepancies were detected across the audited transactions.")
        return

    # 5. Extract or compute discrepancy amounts
    discrepancy_series = _get_discrepancy_series(discrepancy_df)

    plural_text = "discrepancy" if discrepancy_count == 1 else "discrepancies"
    st.warning(f"⚠️ **{discrepancy_count} Fee {plural_text.title()} Detected**")

    # If data does not permit calculating discrepancy amounts
    if discrepancy_series is None:
        st.metric("Flagged Transactions", f"{discrepancy_count}")
        st.info(
            "ℹ️ Detailed fee columns are unavailable in this dataset. "
            "Flagged transaction counts are displayed, but specific overcharge/undercharge amounts cannot be determined."
        )
        return

    # Attach computed values for safe segmentation
    discrepancy_df["_diff"] = discrepancy_series
    total_discrepancy = round(float(discrepancy_series.sum()), 2)

    # Distinguish overcharges and undercharges:
    # Discrepancy = Actual_Fee - Expected_Fee
    # > 0.005 : Merchant was overcharged (deducted more than expected)
    # < -0.005 : Merchant was undercharged (deducted less than expected)
    overcharge_mask = discrepancy_series > 0.005
    undercharge_mask = discrepancy_series < -0.005

    overcharge_df = discrepancy_df[overcharge_mask]
    undercharge_df = discrepancy_df[undercharge_mask]

    overcharge_count = len(overcharge_df)
    undercharge_count = len(undercharge_df)

    overcharge_total = round(float(overcharge_df["_diff"].sum()), 2) if overcharge_count > 0 else 0.0
    undercharge_total = round(float(abs(undercharge_df["_diff"].sum())), 2) if undercharge_count > 0 else 0.0

    # 6. Render summary metrics
    if overcharge_count > 0 and undercharge_count > 0:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Flagged Transactions", f"{discrepancy_count}")
        col2.metric("Total Net Discrepancy", f"₹{total_discrepancy:,.2f}")
        col3.metric("Overcharges", f"{overcharge_count} (₹{overcharge_total:,.2f})")
        col4.metric("Undercharges", f"{undercharge_count} (₹{undercharge_total:,.2f})")
    elif overcharge_count > 0:
        col1, col2 = st.columns(2)
        col1.metric("Flagged Transactions", f"{discrepancy_count}")
        col2.metric("Total Overcharge Amount", f"₹{overcharge_total:,.2f}")
    elif undercharge_count > 0:
        col1, col2 = st.columns(2)
        col1.metric("Flagged Transactions", f"{discrepancy_count}")
        col2.metric("Total Undercharge Amount", f"₹{undercharge_total:,.2f}")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Flagged Transactions", f"{discrepancy_count}")
        col2.metric("Total Discrepancy Amount", f"₹{total_discrepancy:,.2f}")

    # 7. Render plain-language insights
    st.markdown("#### 📋 Discrepancy Analysis & Insights")

    # Clear breakdown in plain business language
    if overcharge_count > 0 and undercharge_count > 0:
        plural_over = "transaction" if overcharge_count == 1 else "transactions"
        plural_under = "transaction" if undercharge_count == 1 else "transactions"
        st.markdown(
            f"- **Overcharges ({overcharge_count} {plural_over})**: The payment processor deducted "
            f"fees higher than the contracted MDR rate, resulting in an excess fee deduction of "
            f"**₹{overcharge_total:,.2f}**.\n"
            f"- **Undercharges ({undercharge_count} {plural_under})**: Fees deducted were lower than "
            f"the contracted MDR rate, totaling **₹{undercharge_total:,.2f}** in under-deductions.\n"
            f"- **Net Financial Impact**: The net difference across all flagged transactions is "
            f"**₹{total_discrepancy:,.2f}** {'excess fee paid by the merchant' if total_discrepancy > 0 else 'net under-deduction'}."
        )
    elif overcharge_count > 0:
        plural_flagged = "transaction" if discrepancy_count == 1 else "transactions"
        st.markdown(
            f"- **Overcharges Detected**: All **{discrepancy_count} flagged {plural_flagged}** are overcharges. "
            f"The payment processor deducted fees exceeding the contracted MDR rate, causing an excess charge "
            f"of **₹{overcharge_total:,.2f}** to your account."
        )
    elif undercharge_count > 0:
        plural_flagged = "transaction" if discrepancy_count == 1 else "transactions"
        st.markdown(
            f"- **Undercharges Detected**: All **{discrepancy_count} flagged {plural_flagged}** are undercharges. "
            f"The payment processor deducted fees lower than expected by a total of **₹{undercharge_total:,.2f}**."
        )
    else:
        plural_flagged = "transaction" if discrepancy_count == 1 else "transactions"
        st.markdown(
            f"- **Discrepancy Summary**: **{discrepancy_count} {plural_flagged}** showed a fee variance "
            f"totaling **₹{total_discrepancy:,.2f}**."
        )

    # Optional category concentration insight if column is available
    if COL_MERCHANT_CATEGORY in discrepancy_df.columns:
        cat_counts = discrepancy_df[COL_MERCHANT_CATEGORY].value_counts()
        if not cat_counts.empty:
            top_category = cat_counts.index[0]
            top_cat_count = cat_counts.iloc[0]
            st.markdown(
                f"- **Category Concentration**: The **{top_category}** category had the highest number "
                f"of discrepancies (**{top_cat_count}** of {discrepancy_count} flagged transactions)."
            )

    # Actionable guidance for the merchant
    st.caption(
        "💡 **Recommended Action**: Export the discrepancy evidence report below and share it with your "
        "payment aggregator or acquiring bank to initiate a fee reconciliation claim."
    )


def render_export_button(audited_df: pd.DataFrame) -> None:
    """
    Filters transactions where Audit_Status is 'Discrepancy Detected' and renders
    a Streamlit download button to export them as 'discrepancy_report.csv'.

    Safely handles empty DataFrames, missing columns, and zero discrepancies.
    """
    # 1. Handle None or empty DataFrame safely
    if audited_df is None or not isinstance(audited_df, pd.DataFrame) or audited_df.empty:
        st.button(
            "⬇️ Download Discrepancy Report",
            disabled=True,
            help="No transaction data available to export.",
        )
        return

    # 2. Check for required Audit_Status column safely
    if COL_AUDIT_STATUS not in audited_df.columns:
        st.button(
            "⬇️ Download Discrepancy Report",
            disabled=True,
            help="Cannot export: Missing 'Audit_Status' column.",
        )
        st.error(
            f"❌ Cannot export report: Missing required column '{COL_AUDIT_STATUS}'. "
            "Please ensure transactions have been audited."
        )
        return

    # 3. Filter transactions where Audit_Status indicates a discrepancy
    discrepancy_mask = (
        audited_df[COL_AUDIT_STATUS].astype(str).str.strip().str.lower()
        == STATUS_DISCREPANCY.lower()
    )
    discrepancy_df = audited_df[discrepancy_mask]

    # 4. Handle zero discrepancies gracefully
    if discrepancy_df.empty:
        st.button(
            "⬇️ Download Discrepancy Report",
            disabled=True,
            help="No discrepancies to export.",
        )
        st.caption("No flagged transactions found to export.")
        return

    # 5. Convert flagged transactions to UTF-8 CSV
    csv_bytes = discrepancy_df.to_csv(index=False).encode("utf-8")

    # 6. Render Streamlit download button
    st.download_button(
        label="⬇️ Download Discrepancy Report",
        data=csv_bytes,
        file_name="discrepancy_report.csv",
        mime="text/csv",
        help="Download flagged transactions as discrepancy_report.csv for reconciliation.",
    )
