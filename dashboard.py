"""Anima Trustpilot Sentiment Monitor — Dashboard

A live dashboard tracking Anima Health's Trustpilot reviews, auto-categorising
negative reviews, and comparing against competitors.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import os
from datetime import datetime

# --- Config ---
st.set_page_config(
    page_title="Anima Trustpilot Sentiment Monitor",
    page_icon="📊",
    layout="wide",
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reviews.db")

# --- Anima Brand Styling ---
st.markdown("""
<style>
    /* Clean Anima brand typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Tighten default Streamlit block spacing */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1100px !important;
    }

    /* Section headers — clean, no underline */
    h2 {
        color: #7C3AED !important;
        font-weight: 600 !important;
        font-size: 1.6rem !important;
        letter-spacing: -0.01em !important;
        margin-top: 2.5rem !important;
        margin-bottom: 1.2rem !important;
        border: none !important;
        padding-bottom: 0 !important;
    }

    h3 {
        color: #1A1A2E !important;
        font-weight: 600 !important;
        font-size: 1.05rem !important;
        margin-bottom: 0.8rem !important;
    }

    /* Metric cards — lighter, cleaner */
    [data-testid="stMetric"] {
        background: #FAFAFF;
        border: 1px solid #EDE9FE;
        border-radius: 10px;
        padding: 1.1rem 1.3rem;
    }

    [data-testid="stMetricLabel"] {
        color: #7C3AED !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
    }

    [data-testid="stMetricValue"] {
        color: #1A1A2E !important;
        font-weight: 700 !important;
        font-size: 1.8rem !important;
    }

    /* Dataframe styling */
    [data-testid="stDataFrame"] {
        border: 1px solid #EDE9FE;
        border-radius: 10px;
        overflow: hidden;
    }

    /* Plotly chart containers */
    [data-testid="stPlotlyChart"] {
        border-radius: 10px;
    }

    /* Remove Streamlit branding footer */
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}

    /* Tidy up input widgets */
    .stSelectbox > div, .stMultiSelect > div, .stTextInput > div {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- Password Protection ---
def check_password():
    """Simple password gate. Set the password in .streamlit/secrets.toml"""
    correct_password = st.secrets.get("password", "anima2026")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("""
    <div style="text-align: center; margin-top: 8vh;">
        <p style="font-size: 2rem; font-weight: 700; color: #1A1A2E; letter-spacing: -0.03em; margin-bottom: 0.3rem;">Trustpilot Sentiment Monitor</p>
        <p style="color: #6B6B8D; font-size: 1rem;">Enter the password to continue</p>
    </div>
    """, unsafe_allow_html=True)
    password = st.text_input("Password", type="password")
    if password:
        if password == correct_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False

if not check_password():
    st.stop()

CATEGORY_COLORS = {
    "Interface and technical problems": "#7C3AED",
    "Questionnaire burden": "#A855F7",
    "System unavailability": "#3B82F6",
    "Digital exclusion": "#EC4899",
    "Triage misdirection": "#6366F1",
    "Practice capacity": "#94A3B8",
    "Other": "#CBD5E1",
}

CATEGORY_ORDER = [
    "Interface and technical problems",
    "Questionnaire burden",
    "System unavailability",
    "Digital exclusion",
    "Triage misdirection",
    "Other",
    "Practice capacity",
]


CHART_LAYOUT = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Inter, sans-serif", color="#4A4A6A", size=12),
    margin=dict(l=40, r=20, t=30, b=40),
    xaxis=dict(gridcolor="#F0ECF9", linecolor="#EDE9FE", zeroline=False),
    yaxis=dict(gridcolor="#F0ECF9", linecolor="#EDE9FE", zeroline=False),
)


@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM reviews", conn)
    scrape_log = pd.read_sql_query(
        "SELECT * FROM scrape_log ORDER BY scraped_at DESC", conn
    )
    conn.close()

    df["date_published"] = pd.to_datetime(df["date_published"])
    df["month"] = df["date_published"].dt.to_period("M").astype(str)
    df["year_month"] = df["date_published"].dt.strftime("%Y-%m")
    return df, scrape_log


def get_latest_stats(scrape_log, company):
    row = scrape_log[scrape_log["company"] == company]
    if row.empty:
        return {}
    row = row.iloc[0]
    return {
        "rating": row["rating"],
        "total": row["total_reviews"],
        "five": row["five_star"],
        "four": row["four_star"],
        "three": row["three_star"],
        "two": row["two_star"],
        "one": row["one_star"],
    }


# --- Load data ---
df, scrape_log = load_data()
anima = df[df["company"] == "anima"]
anima_neg = anima[anima["rating"] <= 2]

# --- Header ---
st.markdown("""
<div style="margin-bottom: 2rem;">
    <p style="font-size: 1.8rem; font-weight: 700; color: #1A1A2E; letter-spacing: -0.03em; margin-bottom: 0.2rem; line-height: 1.2;">Trustpilot Sentiment Monitor</p>
    <p style="color: #6B6B8D; font-size: 0.95rem; margin: 0 0 0.15rem 0;">
        Automated analysis of patient feedback for <a href="https://animahealth.com" style="color: #7C3AED; text-decoration: none; font-weight: 500;">Anima Health</a>
    </p>
    <p style="color: #A0A0B8; font-size: 0.8rem; margin: 0;">
        Reviews scraped daily &middot; Negative feedback auto-categorised into seven complaint frameworks
    </p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SECTION 1: Overview Panel
# ============================================================
st.header("Overview")

# Get stats from scrape log (these are accurate totals from Trustpilot)
anima_stats = get_latest_stats(scrape_log, "anima")

# Metrics row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Anima Rating", f"{anima_stats.get('rating', 'N/A')}/5")
with col2:
    st.metric("Total Reviews", f"{anima_stats.get('total', 'N/A'):,}")
with col3:
    one_star_pct = (
        anima_stats.get("one", 0) / anima_stats.get("total", 1) * 100
        if anima_stats.get("total")
        else 0
    )
    st.metric("1-Star Reviews", f"{one_star_pct:.0f}%")
with col4:
    five_star_pct = (
        anima_stats.get("five", 0) / anima_stats.get("total", 1) * 100
        if anima_stats.get("total")
        else 0
    )
    st.metric("5-Star Reviews", f"{five_star_pct:.0f}%")

# Star distribution
st.subheader("Star Distribution")
if anima_stats:
    star_data = pd.DataFrame({
        "Stars": ["5 star", "4 star", "3 star", "2 star", "1 star"],
        "Count": [
            anima_stats.get("five", 0),
            anima_stats.get("four", 0),
            anima_stats.get("three", 0),
            anima_stats.get("two", 0),
            anima_stats.get("one", 0),
        ],
    })
    star_data["Percentage"] = (
        star_data["Count"] / star_data["Count"].sum() * 100
    ).round(1)
    fig = px.bar(
        star_data,
        x="Stars",
        y="Count",
        text="Percentage",
        color="Stars",
        color_discrete_map={
            "5 star": "#00B67A",
            "4 star": "#73CF11",
            "3 star": "#FFCE00",
            "2 star": "#FF8622",
            "1 star": "#FF3722",
        },
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(**CHART_LAYOUT, showlegend=False, yaxis_title="Number of Reviews", xaxis_title="", height=320)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

# ============================================================
# SECTION 2: Trends Over Time
# ============================================================
st.header("Trends Over Time")

# Monthly average rating
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.subheader("Monthly Average Rating")
    monthly_rating = (
        anima.groupby("year_month")
        .agg(avg_rating=("rating", "mean"), count=("rating", "count"))
        .reset_index()
    )
    monthly_rating = monthly_rating[monthly_rating["count"] >= 3]
    if not monthly_rating.empty:
        fig = px.line(
            monthly_rating,
            x="year_month",
            y="avg_rating",
            markers=True,
        )
        fig.update_layout(**CHART_LAYOUT, yaxis_title="Average Rating", yaxis_range=[1, 5], xaxis_title="", height=320)
        fig.update_traces(line_color="#7C3AED")
        st.plotly_chart(fig, use_container_width=True)

with col_t2:
    st.subheader("Monthly Review Volume")
    monthly_vol = (
        anima.groupby("year_month")
        .agg(total=("rating", "count"))
        .reset_index()
    )
    if not monthly_vol.empty:
        fig = px.bar(monthly_vol, x="year_month", y="total")
        fig.update_layout(**CHART_LAYOUT, yaxis_title="Number of Reviews", xaxis_title="", height=320)
        fig.update_traces(marker_color="#7C3AED")
        st.plotly_chart(fig, use_container_width=True)

# Star distribution over time
st.subheader("Star Distribution Over Time")
monthly_stars = (
    anima.groupby(["year_month", "rating"])
    .size()
    .reset_index(name="count")
)
if not monthly_stars.empty:
    monthly_totals = monthly_stars.groupby("year_month")["count"].sum().reset_index(name="total")
    monthly_stars = monthly_stars.merge(monthly_totals, on="year_month")
    monthly_stars["percentage"] = (monthly_stars["count"] / monthly_stars["total"] * 100).round(1)
    monthly_stars["rating_label"] = monthly_stars["rating"].astype(str) + " star"

    fig = px.area(
        monthly_stars,
        x="year_month",
        y="percentage",
        color="rating_label",
        color_discrete_map={
            "5 star": "#00B67A",
            "4 star": "#73CF11",
            "3 star": "#FFCE00",
            "2 star": "#FF8622",
            "1 star": "#FF3722",
        },
        groupnorm="percent",
    )
    fig.update_layout(**CHART_LAYOUT, yaxis_title="% of Reviews", xaxis_title="", legend_title="Rating", height=320)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

# ============================================================
# SECTION 3: Negative Review Analysis
# ============================================================
st.header("Negative Review Analysis")
st.markdown(f"*Based on {len(anima_neg)} reviews with 1-2 stars in our database*")

col_n1, col_n2 = st.columns(2)

with col_n1:
    st.subheader("Category Breakdown")
    cat_counts = (
        anima_neg[anima_neg["category"].notna()]
        .groupby("category")
        .size()
        .reset_index(name="count")
    )
    if not cat_counts.empty:
        cat_counts["percentage"] = (
            cat_counts["count"] / cat_counts["count"].sum() * 100
        ).round(1)
        cat_counts = cat_counts.sort_values("count", ascending=True)
        fig = px.bar(
            cat_counts,
            x="count",
            y="category",
            orientation="h",
            text="percentage",
            color="category",
            color_discrete_map=CATEGORY_COLORS,
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(**CHART_LAYOUT, showlegend=False, xaxis_title="Number of Reviews", yaxis_title="", height=380)
        st.plotly_chart(fig, use_container_width=True)

with col_n2:
    st.subheader("Software vs Practice Complaints")
    sw = anima_neg[anima_neg["software_complaint"] == 1].shape[0]
    pr = anima_neg[anima_neg["software_complaint"] == 0].shape[0]
    if sw + pr > 0:
        fig = px.pie(
            values=[sw, pr],
            names=["Software complaint", "Practice complaint"],
            color_discrete_sequence=["#7C3AED", "#E2E0EA"],
            hole=0.4,
        )
        fig.update_layout(**CHART_LAYOUT, height=380)
        st.plotly_chart(fig, use_container_width=True)

# THE KEY CHART: Category trends over time
st.subheader("Category Trends Over Time")
st.markdown("""
*How each complaint category's share of negative reviews changes over time.*
""")

cat_monthly = (
    anima_neg[anima_neg["category"].notna()]
    .groupby(["year_month", "category"])
    .size()
    .reset_index(name="count")
)
if not cat_monthly.empty:
    monthly_neg_total = cat_monthly.groupby("year_month")["count"].sum().reset_index(name="total")
    cat_monthly = cat_monthly.merge(monthly_neg_total, on="year_month")
    cat_monthly["percentage"] = (cat_monthly["count"] / cat_monthly["total"] * 100).round(1)

    # Filter to months with enough data
    cat_monthly = cat_monthly[cat_monthly["total"] >= 3]

    if not cat_monthly.empty:
        fig = px.line(
            cat_monthly,
            x="year_month",
            y="percentage",
            color="category",
            markers=True,
            color_discrete_map=CATEGORY_COLORS,
        )
        fig.update_layout(**CHART_LAYOUT, yaxis_title="% of Negative Reviews", xaxis_title="", legend_title="Category", height=400)
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

# ============================================================
# SECTION 4: Recent Negative Reviews
# ============================================================
st.header("Recent Negative Reviews")

recent_neg = (
    anima_neg[["date_published", "rating", "consumer_name", "title", "text", "category", "software_complaint"]]
    .sort_values("date_published", ascending=False)
    .head(50)
    .copy()
)
recent_neg["date"] = recent_neg["date_published"].dt.strftime("%Y-%m-%d")
recent_neg["type"] = recent_neg["software_complaint"].map(
    {1: "Software", 0: "Practice"}
)
recent_neg = recent_neg[["date", "rating", "consumer_name", "title", "category", "type"]]
recent_neg.columns = ["Date", "Stars", "Reviewer", "Title", "Category", "Type"]

st.dataframe(
    recent_neg,
    use_container_width=True,
    hide_index=True,
    height=500,
)

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

# ============================================================
# SECTION 5: Review Explorer
# ============================================================
st.header("Review Explorer")

col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    company_filter = st.selectbox("Company", ["anima"])
with col_f2:
    rating_filter = st.multiselect("Star Rating", [1, 2, 3, 4, 5], default=[1, 2, 3, 4, 5])
with col_f3:
    category_filter = st.multiselect("Category", CATEGORY_ORDER, default=[])
with col_f4:
    search_term = st.text_input("Search reviews", "")

filtered = df[df["company"] == company_filter]
if rating_filter:
    filtered = filtered[filtered["rating"].isin(rating_filter)]
if category_filter:
    filtered = filtered[filtered["category"].isin(category_filter)]
if search_term:
    mask = (
        filtered["title"].str.contains(search_term, case=False, na=False)
        | filtered["text"].str.contains(search_term, case=False, na=False)
    )
    filtered = filtered[mask]

filtered = filtered.sort_values("date_published", ascending=False)

st.markdown(f"**{len(filtered)} reviews found**")

display_df = filtered[["date_published", "rating", "consumer_name", "title", "text", "category"]].copy()
display_df["date"] = display_df["date_published"].dt.strftime("%Y-%m-%d")
display_df = display_df[["date", "rating", "consumer_name", "title", "text", "category"]]
display_df.columns = ["Date", "Stars", "Reviewer", "Title", "Review Text", "Category"]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=500,
)

