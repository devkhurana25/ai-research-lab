"""Dataset summaries, visualizations, and PDF assembly for sales reports."""
from __future__ import annotations

from io import BytesIO
from io import StringIO
from typing import Any

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from tools.pdf_export import ReportPDF, _safe
from tools import dataset_tools


def load_report_dataframe(
    dataset_path: str | None = None,
    dataset_json: list[dict[str, Any]] | dict[str, Any] | None = None,
    csv_data: str | None = None,
) -> tuple[pd.DataFrame, str]:
    supplied = sum(value is not None for value in (dataset_path, dataset_json, csv_data))
    if supplied != 1:
        raise ValueError("Provide exactly one of dataset_path, dataset_json, or csv_data.")
    if dataset_path is not None:
        return dataset_tools.load(dataset_path), dataset_path
    if csv_data is not None:
        if not csv_data.strip():
            raise ValueError("csv_data must not be empty.")
        return pd.read_csv(StringIO(csv_data)), "uploaded.csv"
    if isinstance(dataset_json, list):
        if not dataset_json:
            raise ValueError("dataset_json must contain at least one record.")
        return pd.DataFrame.from_records(dataset_json), "uploaded.json"
    if isinstance(dataset_json, dict):
        if not dataset_json:
            raise ValueError("dataset_json must not be empty.")
        return pd.DataFrame(dataset_json), "uploaded.json"
    raise ValueError("dataset_json must be an object or a list of records.")


def summarize_sales_data(df: pd.DataFrame) -> dict[str, Any]:
    """Return numeric descriptive statistics and available segment/cohort insights."""
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_summary: dict[str, dict[str, float | int | None]] = {}
    for column in numeric_columns:
        values = df[column].dropna()
        numeric_summary[column] = {
            "count": int(values.count()),
            "mean": float(values.mean()) if not values.empty else None,
            "median": float(values.median()) if not values.empty else None,
            "min": float(values.min()) if not values.empty else None,
            "max": float(values.max()) if not values.empty else None,
        }

    preferred = ("customer_segment", "segment", "customer_type", "customer_tier", "region", "plan")
    categorical = [
        column for column in df.select_dtypes(exclude=[np.number]).columns
        if not any(token in column.lower() for token in ("date", "time", "timestamp"))
        and not column.lower().endswith("_id")
        and 2 <= df[column].nunique(dropna=True) <= 12
    ]
    segment_columns = [
        column for column in preferred if column in categorical
    ]
    segment_columns.extend(column for column in categorical if column not in segment_columns)
    segment_columns = segment_columns[:3]

    metric_columns = [
        column for column in ("revenue", "marketing_spend", "avg_order_value", "churn_rate")
        if column in numeric_columns
    ]
    segment_insights: dict[str, list[dict[str, Any]]] = {}
    for column in segment_columns:
        groups = []
        for value, group in df.groupby(column, dropna=False, observed=True):
            insight: dict[str, Any] = {"segment": "Missing" if pd.isna(value) else str(value), "rows": int(len(group))}
            for metric in metric_columns:
                values = group[metric].dropna()
                insight[f"{metric}_mean"] = float(values.mean()) if not values.empty else None
            groups.append(insight)
        groups.sort(key=lambda item: item["rows"], reverse=True)
        segment_insights[column] = groups

    explicit_customer_segment = any(
        "segment" in column.lower() or "customer_type" in column.lower() or "customer_tier" in column.lower()
        for column in segment_columns
    )
    describe = df.describe().replace({np.nan: None}).to_dict()
    return {
        "rows": int(len(df)),
        "columns": [str(column) for column in df.columns],
        "numeric": numeric_summary,
        "describe": describe,
        "segment_insights": segment_insights,
        "segment_note": (
            "Customer segment fields are present in the dataset."
            if explicit_customer_segment
            else "No explicit customer-segment field was found; categorical cohorts such as region are proxies, not customer-level segments."
        ),
    }


def build_report_prompt(summary: dict[str, Any], source_name: str) -> str:
    return (
        "Analyze this sales dataset for evidence-grounded findings. Return concise markdown "
        "under these exact headings: Executive Summary, Hypotheses, Critique, "
        "Recommendations, Proposed Actions, Competitor Analysis, Customer Segmentation. "
        "Do not invent facts, "
        "competitor information, causes, or numerical estimates. Distinguish correlation "
        "from causation and state uncertainty. "
        "For what-if recommendations such as lower prices or higher marketing spend, "
        "state assumptions and recommend a controlled test instead of claiming an outcome.\n\n"
        f"Dataset: {source_name}\nDataset summary and cohort data:\n{summary}"
    )


def _chart_bytes(title: str, draw) -> BytesIO:
    figure = Figure(figsize=(8.2, 4.4), dpi=140)
    figure.patch.set_facecolor("#ffffff")
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    axis.set_facecolor("#ffffff")
    draw(axis)
    axis.set_title(title)
    axis.tick_params(colors="#52636a", labelsize=8)
    for spine in axis.spines.values():
        spine.set_color("#d8e1de")
    if axis.get_ylabel():
        axis.set_axisbelow(True)
        axis.grid(axis="y", color="#e7eeeb", linewidth=0.7)
    figure.tight_layout()
    image = BytesIO()
    figure.savefig(image, format="png", bbox_inches="tight")
    image.seek(0)
    figure.clear()
    return image


def _make_charts(df: pd.DataFrame) -> list[tuple[str, BytesIO]]:
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    categories = [
        column for column in df.select_dtypes(exclude=[np.number]).columns
        if not any(token in column.lower() for token in ("date", "time", "timestamp"))
        and 2 <= df[column].nunique(dropna=True) <= 12
    ]
    preferred_pairs = [
        ("marketing_spend", "revenue"),
        ("discount_pct", "revenue"),
        ("churn_rate", "revenue"),
    ]
    scatter_pair = next(
        (pair for pair in preferred_pairs if all(column in numeric_columns for column in pair)),
        None,
    )
    if scatter_pair is None and len(numeric_columns) >= 2:
        scatter_pair = (numeric_columns[0], numeric_columns[1])

    def draw_bar(axis) -> None:
        metric = "revenue" if "revenue" in numeric_columns else None
        if categories and metric:
            means = df.groupby(categories[0], observed=True)[metric].mean().dropna().sort_values().tail(10)
            axis.barh(means.index.astype(str), means.values, color="#2f8069")
            axis.set_xlabel("Mean revenue")
        elif categories:
            counts = df[categories[0]].fillna("Missing").astype(str).value_counts().head(10)
            axis.barh(counts.index[::-1], counts.values[::-1], color="#2f8069")
            axis.set_xlabel("Rows")
        elif numeric_columns:
            metric = "revenue" if "revenue" in numeric_columns else numeric_columns[0]
            values = df[metric].dropna()
            if values.empty:
                axis.text(0.5, 0.5, "No non-missing numeric values", ha="center", va="center")
            else:
                counts, edges = np.histogram(values, bins=min(12, max(2, values.nunique())))
                centers = (edges[:-1] + edges[1:]) / 2
                axis.bar(centers, counts, width=np.diff(edges) * 0.88, color="#2f8069")
                axis.set_xlabel(metric.replace("_", " ").title())
                axis.set_ylabel("Rows")
        else:
            axis.text(0.5, 0.5, "No plottable columns", ha="center", va="center")

    def draw_pie(axis) -> None:
        if categories:
            column = categories[0]
            counts = df[column].fillna("Missing").astype(str).value_counts()
            top = counts.head(6)
            if len(counts) > len(top):
                top.loc["Other"] = counts.iloc[len(top):].sum()
            axis.pie(top.values, labels=top.index, autopct="%1.1f%%", startangle=90)
            axis.set_ylabel("")
        elif numeric_columns:
            values = df[numeric_columns[0]].dropna()
            if values.empty:
                axis.text(0.5, 0.5, "No non-missing numeric values", ha="center", va="center")
            else:
                bins = pd.cut(values, bins=min(5, max(2, values.nunique()))).value_counts().sort_index()
                axis.pie(bins.values, labels=[str(item) for item in bins.index], autopct="%1.1f%%")
                axis.set_ylabel("")
        else:
            axis.text(0.5, 0.5, "No plottable columns", ha="center", va="center")

    def draw_line(axis) -> None:
        if numeric_columns:
            metric = "revenue" if "revenue" in numeric_columns else numeric_columns[0]
            date_column = next(
                (column for column in df.columns if any(token in str(column).lower() for token in ("date", "time", "timestamp"))),
                None,
            )
            values = df[metric]
            if date_column is not None:
                dates = pd.to_datetime(df[date_column], errors="coerce")
                valid = dates.notna() & values.notna()
                if valid.any():
                    axis.plot(dates[valid], values[valid], color="#356f9f", linewidth=1.5)
                    axis.set_xlabel(str(date_column))
                else:
                    axis.plot(values.to_numpy(), color="#356f9f", linewidth=1.5)
                    axis.set_xlabel("Row")
            else:
                axis.plot(values.to_numpy(), color="#356f9f", linewidth=1.5)
                axis.set_xlabel("Row")
            axis.set_ylabel(metric)
        elif categories:
            counts = df[categories[0]].fillna("Missing").astype(str).value_counts()
            axis.plot(range(len(counts)), counts.values, marker="o", color="#356f9f")
            axis.set_xticks(range(len(counts)), counts.index, rotation=30, ha="right")
            axis.set_ylabel("Rows")
        else:
            axis.text(0.5, 0.5, "No plottable columns", ha="center", va="center")

    def draw_scatter(axis) -> None:
        if scatter_pair is None:
            axis.text(0.5, 0.5, "At least two numeric columns are needed", ha="center", va="center")
            return
        x_column, y_column = scatter_pair
        points = df[[x_column, y_column]].dropna()
        axis.scatter(
            points[x_column], points[y_column], s=22, alpha=0.62,
            color="#2f8069", edgecolors="white", linewidths=0.35,
        )
        correlation = points[x_column].corr(points[y_column]) if len(points) > 1 else float("nan")
        if len(points) >= 2 and points[x_column].nunique() > 1:
            x_values = points[x_column].to_numpy(dtype=float)
            y_values = points[y_column].to_numpy(dtype=float)
            slope, intercept = np.polyfit(x_values, y_values, 1)
            line_x = np.linspace(x_values.min(), x_values.max(), 100)
            axis.plot(line_x, slope * line_x + intercept, color="#c35b44", linewidth=1.8)
        axis.set_xlabel(x_column.replace("_", " ").title())
        axis.set_ylabel(y_column.replace("_", " ").title())
        if pd.notna(correlation):
            axis.text(
                0.03, 0.97, f"Pearson r = {correlation:+.3f}\nAssociation only; not causal evidence",
                transform=axis.transAxes, va="top", fontsize=8,
                bbox={"boxstyle": "square,pad=0.4", "facecolor": "#f3f6f5", "edgecolor": "#d4dfda"},
            )

    return [
        ("Bar graph: numeric means or category counts", _chart_bytes("Dataset overview", draw_bar)),
        ("Pie chart: category distribution", _chart_bytes("Cohort distribution", draw_pie)),
        ("Line chart: metric over time or row order", _chart_bytes("Sales trend", draw_line)),
        ("Scatter plot: numeric relationship with fitted trend", _chart_bytes("Revenue relationship", draw_scatter)),
    ]


def _write_text(pdf: ReportPDF, text: str, line_height: float = 5) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, line_height, _safe(text))


def _write_ai_sections(pdf: ReportPDF, findings: str) -> None:
    aliases = {
        "executive summary": "Executive Summary",
        "hypothesis": "Hypotheses",
        "hypotheses": "Hypotheses",
        "critique": "Critique",
        "critiques": "Critique",
        "recommendation": "Recommendations",
        "recommendations": "Recommendations",
        "proposed action": "Proposed Actions",
        "proposed actions": "Proposed Actions",
        "competitor analysis": "Competitor Analysis",
        "customer segmentation": "Customer Segmentation",
    }
    sections: dict[str, list[str]] = {title: [] for title in (
        "Executive Summary", "Hypotheses", "Critique", "Recommendations",
        "Proposed Actions", "Competitor Analysis", "Customer Segmentation",
    )}
    current: str | None = None
    for raw_line in findings.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = line.lstrip("# ").rstrip(":* ").strip().lower()
        if heading in aliases:
            current = aliases[heading]
            continue
        if current is None:
            current = "Recommendations"
        sections[current].append(line)

    for title, lines in sections.items():
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(34, 75, 66)
        pdf.ln(2)
        _write_text(pdf, title, 7)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(45, 55, 60)
        _write_text(pdf, "\n".join(lines) if lines else "No specific finding was provided in this section.", 5)


def generate_sales_report_pdf(
    df: pd.DataFrame,
    source_name: str,
    summary: dict[str, Any],
    ai_findings: str,
) -> bytes:
    pdf = ReportPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)

    # Cover page
    pdf.add_page()
    pdf.set_fill_color(28, 57, 62)
    pdf.rect(0, 0, pdf.w, 92, style="F")
    pdf.set_text_color(240, 246, 242)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_xy(20, 34)
    pdf.cell(0, 14, "SALES INTELLIGENCE", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.set_x(20)
    pdf.cell(0, 9, "Evidence, patterns, and practical next steps", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(191, 150, 74)
    pdf.set_line_width(1.2)
    pdf.line(20, 103, 68, 103)
    pdf.set_y(119)
    pdf.set_text_color(32, 49, 53)
    pdf.set_font("Helvetica", "B", 21)
    _write_text(pdf, "Sales Analysis Report", 12)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(76, 90, 94)
    _write_text(pdf, f"Dataset: {source_name}", 7)
    _write_text(pdf, f"{summary['rows']} records · {len(summary['columns'])} columns", 7)
    pdf.ln(4)
    _write_text(pdf, "Prepared with deterministic dataset analysis and local Ollama Mistral findings.", 6)

    # Executive summary
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(25, 44, 53)
    _write_text(pdf, "Executive Summary", 10)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(45, 55, 60)
    _write_text(
        pdf,
        f"This report analyzes {summary['rows']} records across {len(summary['columns'])} columns. "
        "Descriptive statistics and charts summarize observed patterns; they do not establish causation.",
        6,
    )
    primary_metric = "revenue" if "revenue" in summary["numeric"] else next(iter(summary["numeric"]), None)
    if primary_metric:
        metric_stats = summary["numeric"][primary_metric]
        if metric_stats["mean"] is not None:
            _write_text(
                pdf,
                f"{primary_metric.replace('_', ' ').title()} has a mean of {metric_stats['mean']:.3f} "
                f"and median of {metric_stats['median']:.3f} across {metric_stats['count']} observed values.",
                6,
            )
    _write_text(pdf, summary["segment_note"], 6)
    _write_text(pdf, "Detailed hypotheses, limitations, recommendations, and actions follow in the AI findings section.", 6)

    # Dataset summary table built directly from pandas.DataFrame.describe().
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(25, 44, 53)
    _write_text(pdf, "Dataset Summary", 9)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 70, 74)
    _write_text(pdf, f"Rows: {summary['rows']}   Columns: {len(summary['columns'])}", 6)
    describe_rows = ("count", "mean", "std", "min", "25%", "50%", "75%", "max")
    describe = summary["describe"]
    if describe:
        headers = ["Metric"] + list(describe.keys())
        usable_columns = max(1, min(len(headers) - 1, 7))
        if len(headers) > usable_columns + 1:
            headers = headers[:usable_columns + 1]
        widths = [31] + [(pdf.w - pdf.l_margin - pdf.r_margin - 31) / (len(headers) - 1)] * (len(headers) - 1)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(35, 77, 71)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, _safe(str(header)[:18]), border=1, align="C", fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 7)
        for index, statistic in enumerate(describe_rows):
            pdf.set_x(pdf.l_margin)
            pdf.set_text_color(35, 48, 52)
            pdf.set_fill_color(235, 241, 238) if index % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(widths[0], 7, statistic, border=1, fill=True)
            for column, width in zip(headers[1:], widths[1:]):
                value = describe.get(column, {}).get(statistic)
                text = "-" if value is None else f"{value:.3g}"
                pdf.cell(width, 7, text, border=1, align="R", fill=True)
            pdf.ln()
    else:
        _write_text(pdf, "No numeric columns were available for pandas describe().", 6)

    pdf.ln(7)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(25, 44, 53)
    _write_text(pdf, "Customer Segmentation and Cohorts", 8)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(45, 55, 60)
    _write_text(pdf, summary["segment_note"])
    for column, groups in summary["segment_insights"].items():
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 6, _safe(f"Cohort: {column}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for group in groups:
            values = [f"{key.removesuffix('_mean')} mean={value:.3f}" for key, value in group.items()
                      if key.endswith("_mean") and value is not None]
            detail = f"{group['segment']}: {group['rows']} rows"
            if values:
                detail += "; " + ", ".join(values)
            _write_text(pdf, detail)
    if not summary["segment_insights"]:
        _write_text(pdf, "No low-cardinality categorical cohort was available for segmentation.")

    for caption, image in _make_charts(df):
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(25, 44, 53)
        _write_text(pdf, caption, 8)
        pdf.image(image, x=20, w=170)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(25, 44, 53)
    _write_text(pdf, "AI Findings and Recommendations", 10)
    _write_ai_sections(pdf, ai_findings)

    return bytes(pdf.output())