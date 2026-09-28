# """Dataset summaries, visualizations, and PDF assembly for sales reports."""
# from __future__ import annotations

# from io import BytesIO
# from io import StringIO
# from typing import Any

# import numpy as np
# import pandas as pd
# from matplotlib.backends.backend_agg import FigureCanvasAgg
# from matplotlib.figure import Figure

# from tools.pdf_export import ReportPDF, _safe
# from tools import dataset_tools


# def load_report_dataframe(
#     dataset_path: str | None = None,
#     dataset_json: list[dict[str, Any]] | dict[str, Any] | None = None,
#     csv_data: str | None = None,
# ) -> tuple[pd.DataFrame, str]:
#     supplied = sum(value is not None for value in (dataset_path, dataset_json, csv_data))
#     if supplied != 1:
#         raise ValueError("Provide exactly one of dataset_path, dataset_json, or csv_data.")
#     if dataset_path is not None:
#         return dataset_tools.load(dataset_path), dataset_path
#     if csv_data is not None:
#         if not csv_data.strip():
#             raise ValueError("csv_data must not be empty.")
#         return pd.read_csv(StringIO(csv_data)), "uploaded.csv"
#     if isinstance(dataset_json, list):
#         if not dataset_json:
#             raise ValueError("dataset_json must contain at least one record.")
#         return pd.DataFrame.from_records(dataset_json), "uploaded.json"
#     if isinstance(dataset_json, dict):
#         if not dataset_json:
#             raise ValueError("dataset_json must not be empty.")
#         return pd.DataFrame(dataset_json), "uploaded.json"
#     raise ValueError("dataset_json must be an object or a list of records.")


# def summarize_sales_data(df: pd.DataFrame) -> dict[str, Any]:
#     """Return numeric descriptive statistics and available segment/cohort insights."""
#     numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
#     numeric_summary: dict[str, dict[str, float | int | None]] = {}
#     for column in numeric_columns:
#         values = df[column].dropna()
#         numeric_summary[column] = {
#             "count": int(values.count()),
#             "mean": float(values.mean()) if not values.empty else None,
#             "median": float(values.median()) if not values.empty else None,
#             "min": float(values.min()) if not values.empty else None,
#             "max": float(values.max()) if not values.empty else None,
#         }

#     preferred = ("customer_segment", "segment", "customer_type", "customer_tier", "region", "plan")
#     categorical = [
#         column for column in df.select_dtypes(exclude=[np.number]).columns
#         if not any(token in column.lower() for token in ("date", "time", "timestamp"))
#         and not column.lower().endswith("_id")
#         and 2 <= df[column].nunique(dropna=True) <= 12
#     ]
#     segment_columns = [
#         column for column in preferred if column in categorical
#     ]
#     segment_columns.extend(column for column in categorical if column not in segment_columns)
#     segment_columns = segment_columns[:3]

#     metric_columns = [
#         column for column in ("revenue", "marketing_spend", "avg_order_value", "churn_rate")
#         if column in numeric_columns
#     ]
#     segment_insights: dict[str, list[dict[str, Any]]] = {}
#     for column in segment_columns:
#         groups = []
#         for value, group in df.groupby(column, dropna=False, observed=True):
#             insight: dict[str, Any] = {"segment": "Missing" if pd.isna(value) else str(value), "rows": int(len(group))}
#             for metric in metric_columns:
#                 values = group[metric].dropna()
#                 insight[f"{metric}_mean"] = float(values.mean()) if not values.empty else None
#             groups.append(insight)
#         groups.sort(key=lambda item: item["rows"], reverse=True)
#         segment_insights[column] = groups

#     explicit_customer_segment = any(
#         "segment" in column.lower() or "customer_type" in column.lower() or "customer_tier" in column.lower()
#         for column in segment_columns
#     )
#     describe = df.describe().replace({np.nan: None}).to_dict()
#     return {
#         "rows": int(len(df)),
#         "columns": [str(column) for column in df.columns],
#         "numeric": numeric_summary,
#         "describe": describe,
#         "segment_insights": segment_insights,
#         "segment_note": (
#             "Customer segment fields are present in the dataset."
#             if explicit_customer_segment
#             else "No explicit customer-segment field was found; categorical cohorts such as region are proxies, not customer-level segments."
#         ),
#     }


# def build_report_prompt(summary: dict[str, Any], source_name: str) -> str:
#     return (
#         "Analyze this sales dataset for evidence-grounded findings. Return concise markdown "
#         "under these exact headings: Executive Summary, Hypotheses, Critique, "
#         "Recommendations, Proposed Actions, Competitor Analysis, Customer Segmentation. "
#         "Do not invent facts, "
#         "competitor information, causes, or numerical estimates. Distinguish correlation "
#         "from causation and state uncertainty. "
#         "For what-if recommendations such as lower prices or higher marketing spend, "
#         "state assumptions and recommend a controlled test instead of claiming an outcome.\n\n"
#         f"Dataset: {source_name}\nDataset summary and cohort data:\n{summary}"
#     )


# def _chart_bytes(title: str, draw) -> BytesIO:
#     figure = Figure(figsize=(8.2, 4.4), dpi=140)
#     figure.patch.set_facecolor("#ffffff")
#     FigureCanvasAgg(figure)
#     axis = figure.subplots()
#     axis.set_facecolor("#ffffff")
#     draw(axis)
#     axis.set_title(title)
#     axis.tick_params(colors="#52636a", labelsize=8)
#     for spine in axis.spines.values():
#         spine.set_color("#d8e1de")
#     if axis.get_ylabel():
#         axis.set_axisbelow(True)
#         axis.grid(axis="y", color="#e7eeeb", linewidth=0.7)
#     figure.tight_layout()
#     image = BytesIO()
#     figure.savefig(image, format="png", bbox_inches="tight")
#     image.seek(0)
#     figure.clear()
#     return image


# def _make_charts(df: pd.DataFrame) -> list[tuple[str, BytesIO]]:
#     numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
#     categories = [
#         column for column in df.select_dtypes(exclude=[np.number]).columns
#         if not any(token in column.lower() for token in ("date", "time", "timestamp"))
#         and 2 <= df[column].nunique(dropna=True) <= 12
#     ]
#     preferred_pairs = [
#         ("marketing_spend", "revenue"),
#         ("discount_pct", "revenue"),
#         ("churn_rate", "revenue"),
#     ]
#     scatter_pair = next(
#         (pair for pair in preferred_pairs if all(column in numeric_columns for column in pair)),
#         None,
#     )
#     if scatter_pair is None and len(numeric_columns) >= 2:
#         scatter_pair = (numeric_columns[0], numeric_columns[1])

#     def draw_bar(axis) -> None:
#         metric = "revenue" if "revenue" in numeric_columns else None
#         if categories and metric:
#             means = df.groupby(categories[0], observed=True)[metric].mean().dropna().sort_values().tail(10)
#             axis.barh(means.index.astype(str), means.values, color="#2f8069")
#             axis.set_xlabel("Mean revenue")
#         elif categories:
#             counts = df[categories[0]].fillna("Missing").astype(str).value_counts().head(10)
#             axis.barh(counts.index[::-1], counts.values[::-1], color="#2f8069")
#             axis.set_xlabel("Rows")
#         elif numeric_columns:
#             metric = "revenue" if "revenue" in numeric_columns else numeric_columns[0]
#             values = df[metric].dropna()
#             if values.empty:
#                 axis.text(0.5, 0.5, "No non-missing numeric values", ha="center", va="center")
#             else:
#                 counts, edges = np.histogram(values, bins=min(12, max(2, values.nunique())))
#                 centers = (edges[:-1] + edges[1:]) / 2
#                 axis.bar(centers, counts, width=np.diff(edges) * 0.88, color="#2f8069")
#                 axis.set_xlabel(metric.replace("_", " ").title())
#                 axis.set_ylabel("Rows")
#         else:
#             axis.text(0.5, 0.5, "No plottable columns", ha="center", va="center")

#     def draw_pie(axis) -> None:
#         if categories:
#             column = categories[0]
#             counts = df[column].fillna("Missing").astype(str).value_counts()
#             top = counts.head(6)
#             if len(counts) > len(top):
#                 top.loc["Other"] = counts.iloc[len(top):].sum()
#             axis.pie(top.values, labels=top.index, autopct="%1.1f%%", startangle=90)
#             axis.set_ylabel("")
#         elif numeric_columns:
#             values = df[numeric_columns[0]].dropna()
#             if values.empty:
#                 axis.text(0.5, 0.5, "No non-missing numeric values", ha="center", va="center")
#             else:
#                 bins = pd.cut(values, bins=min(5, max(2, values.nunique()))).value_counts().sort_index()
#                 axis.pie(bins.values, labels=[str(item) for item in bins.index], autopct="%1.1f%%")
#                 axis.set_ylabel("")
#         else:
#             axis.text(0.5, 0.5, "No plottable columns", ha="center", va="center")

#     def draw_line(axis) -> None:
#         if numeric_columns:
#             metric = "revenue" if "revenue" in numeric_columns else numeric_columns[0]
#             date_column = next(
#                 (column for column in df.columns if any(token in str(column).lower() for token in ("date", "time", "timestamp"))),
#                 None,
#             )
#             values = df[metric]
#             if date_column is not None:
#                 dates = pd.to_datetime(df[date_column], errors="coerce")
#                 valid = dates.notna() & values.notna()
#                 if valid.any():
#                     axis.plot(dates[valid], values[valid], color="#356f9f", linewidth=1.5)
#                     axis.set_xlabel(str(date_column))
#                 else:
#                     axis.plot(values.to_numpy(), color="#356f9f", linewidth=1.5)
#                     axis.set_xlabel("Row")
#             else:
#                 axis.plot(values.to_numpy(), color="#356f9f", linewidth=1.5)
#                 axis.set_xlabel("Row")
#             axis.set_ylabel(metric)
#         elif categories:
#             counts = df[categories[0]].fillna("Missing").astype(str).value_counts()
#             axis.plot(range(len(counts)), counts.values, marker="o", color="#356f9f")
#             axis.set_xticks(range(len(counts)), counts.index, rotation=30, ha="right")
#             axis.set_ylabel("Rows")
#         else:
#             axis.text(0.5, 0.5, "No plottable columns", ha="center", va="center")

#     def draw_scatter(axis) -> None:
#         if scatter_pair is None:
#             axis.text(0.5, 0.5, "At least two numeric columns are needed", ha="center", va="center")
#             return
#         x_column, y_column = scatter_pair
#         points = df[[x_column, y_column]].dropna()
#         axis.scatter(
#             points[x_column], points[y_column], s=22, alpha=0.62,
#             color="#2f8069", edgecolors="white", linewidths=0.35,
#         )
#         correlation = points[x_column].corr(points[y_column]) if len(points) > 1 else float("nan")
#         if len(points) >= 2 and points[x_column].nunique() > 1:
#             x_values = points[x_column].to_numpy(dtype=float)
#             y_values = points[y_column].to_numpy(dtype=float)
#             slope, intercept = np.polyfit(x_values, y_values, 1)
#             line_x = np.linspace(x_values.min(), x_values.max(), 100)
#             axis.plot(line_x, slope * line_x + intercept, color="#c35b44", linewidth=1.8)
#         axis.set_xlabel(x_column.replace("_", " ").title())
#         axis.set_ylabel(y_column.replace("_", " ").title())
#         if pd.notna(correlation):
#             axis.text(
#                 0.03, 0.97, f"Pearson r = {correlation:+.3f}\nAssociation only; not causal evidence",
#                 transform=axis.transAxes, va="top", fontsize=8,
#                 bbox={"boxstyle": "square,pad=0.4", "facecolor": "#f3f6f5", "edgecolor": "#d4dfda"},
#             )

#     return [
#         ("Bar graph: numeric means or category counts", _chart_bytes("Dataset overview", draw_bar)),
#         ("Pie chart: category distribution", _chart_bytes("Cohort distribution", draw_pie)),
#         ("Line chart: metric over time or row order", _chart_bytes("Sales trend", draw_line)),
#         ("Scatter plot: numeric relationship with fitted trend", _chart_bytes("Revenue relationship", draw_scatter)),
#     ]


# def _write_text(pdf: ReportPDF, text: str, line_height: float = 5) -> None:
#     pdf.set_x(pdf.l_margin)
#     pdf.multi_cell(0, line_height, _safe(text))


# def _write_ai_sections(pdf: ReportPDF, findings: str) -> None:
#     aliases = {
#         "executive summary": "Executive Summary",
#         "hypothesis": "Hypotheses",
#         "hypotheses": "Hypotheses",
#         "critique": "Critique",
#         "critiques": "Critique",
#         "recommendation": "Recommendations",
#         "recommendations": "Recommendations",
#         "proposed action": "Proposed Actions",
#         "proposed actions": "Proposed Actions",
#         "competitor analysis": "Competitor Analysis",
#         "customer segmentation": "Customer Segmentation",
#     }
#     sections: dict[str, list[str]] = {title: [] for title in (
#         "Executive Summary", "Hypotheses", "Critique", "Recommendations",
#         "Proposed Actions", "Competitor Analysis", "Customer Segmentation",
#     )}
#     current: str | None = None
#     for raw_line in findings.splitlines():
#         line = raw_line.strip()
#         if not line:
#             continue
#         heading = line.lstrip("# ").rstrip(":* ").strip().lower()
#         if heading in aliases:
#             current = aliases[heading]
#             continue
#         if current is None:
#             current = "Recommendations"
#         sections[current].append(line)

#     for title, lines in sections.items():
#         pdf.set_font("Helvetica", "B", 12)
#         pdf.set_text_color(34, 75, 66)
#         pdf.ln(2)
#         _write_text(pdf, title, 7)
#         pdf.set_font("Helvetica", "", 9)
#         pdf.set_text_color(45, 55, 60)
#         _write_text(pdf, "\n".join(lines) if lines else "No specific finding was provided in this section.", 5)


# def generate_sales_report_pdf(
#     df: pd.DataFrame,
#     source_name: str,
#     summary: dict[str, Any],
#     ai_findings: str,
# ) -> bytes:
#     pdf = ReportPDF(format="A4")
#     pdf.set_margins(18, 18, 18)
#     pdf.set_auto_page_break(auto=True, margin=18)

#     # Cover page
#     pdf.add_page()
#     pdf.set_fill_color(28, 57, 62)
#     pdf.rect(0, 0, pdf.w, 92, style="F")
#     pdf.set_text_color(240, 246, 242)
#     pdf.set_font("Helvetica", "B", 26)
#     pdf.set_xy(20, 34)
#     pdf.cell(0, 14, "SALES INTELLIGENCE", new_x="LMARGIN", new_y="NEXT")
#     pdf.set_font("Helvetica", "", 13)
#     pdf.set_x(20)
#     pdf.cell(0, 9, "Evidence, patterns, and practical next steps", new_x="LMARGIN", new_y="NEXT")
#     pdf.set_draw_color(191, 150, 74)
#     pdf.set_line_width(1.2)
#     pdf.line(20, 103, 68, 103)
#     pdf.set_y(119)
#     pdf.set_text_color(32, 49, 53)
#     pdf.set_font("Helvetica", "B", 21)
#     _write_text(pdf, "Sales Analysis Report", 12)
#     pdf.set_font("Helvetica", "", 11)
#     pdf.set_text_color(76, 90, 94)
#     _write_text(pdf, f"Dataset: {source_name}", 7)
#     _write_text(pdf, f"{summary['rows']} records · {len(summary['columns'])} columns", 7)
#     pdf.ln(4)
#     _write_text(pdf, "Prepared with deterministic dataset analysis and local Ollama Mistral findings.", 6)

#     # Executive summary
#     pdf.add_page()
#     pdf.set_font("Helvetica", "B", 18)
#     pdf.set_text_color(25, 44, 53)
#     _write_text(pdf, "Executive Summary", 10)
#     pdf.set_font("Helvetica", "", 10)
#     pdf.set_text_color(45, 55, 60)
#     _write_text(
#         pdf,
#         f"This report analyzes {summary['rows']} records across {len(summary['columns'])} columns. "
#         "Descriptive statistics and charts summarize observed patterns; they do not establish causation.",
#         6,
#     )
#     primary_metric = "revenue" if "revenue" in summary["numeric"] else next(iter(summary["numeric"]), None)
#     if primary_metric:
#         metric_stats = summary["numeric"][primary_metric]
#         if metric_stats["mean"] is not None:
#             _write_text(
#                 pdf,
#                 f"{primary_metric.replace('_', ' ').title()} has a mean of {metric_stats['mean']:.3f} "
#                 f"and median of {metric_stats['median']:.3f} across {metric_stats['count']} observed values.",
#                 6,
#             )
#     _write_text(pdf, summary["segment_note"], 6)
#     _write_text(pdf, "Detailed hypotheses, limitations, recommendations, and actions follow in the AI findings section.", 6)

#     # Dataset summary table built directly from pandas.DataFrame.describe().
#     pdf.add_page()
#     pdf.set_font("Helvetica", "B", 16)
#     pdf.set_text_color(25, 44, 53)
#     _write_text(pdf, "Dataset Summary", 9)
#     pdf.set_font("Helvetica", "", 9)
#     pdf.set_text_color(60, 70, 74)
#     _write_text(pdf, f"Rows: {summary['rows']}   Columns: {len(summary['columns'])}", 6)
#     describe_rows = ("count", "mean", "std", "min", "25%", "50%", "75%", "max")
#     describe = summary["describe"]
#     if describe:
#         headers = ["Metric"] + list(describe.keys())
#         usable_columns = max(1, min(len(headers) - 1, 7))
#         if len(headers) > usable_columns + 1:
#             headers = headers[:usable_columns + 1]
#         widths = [31] + [(pdf.w - pdf.l_margin - pdf.r_margin - 31) / (len(headers) - 1)] * (len(headers) - 1)
#         pdf.set_font("Helvetica", "B", 7)
#         pdf.set_text_color(255, 255, 255)
#         pdf.set_fill_color(35, 77, 71)
#         for header, width in zip(headers, widths):
#             pdf.cell(width, 7, _safe(str(header)[:18]), border=1, align="C", fill=True)
#         pdf.ln()
#         pdf.set_font("Helvetica", "", 7)
#         for index, statistic in enumerate(describe_rows):
#             pdf.set_x(pdf.l_margin)
#             pdf.set_text_color(35, 48, 52)
#             pdf.set_fill_color(235, 241, 238) if index % 2 == 0 else pdf.set_fill_color(255, 255, 255)
#             pdf.cell(widths[0], 7, statistic, border=1, fill=True)
#             for column, width in zip(headers[1:], widths[1:]):
#                 value = describe.get(column, {}).get(statistic)
#                 text = "-" if value is None else f"{value:.3g}"
#                 pdf.cell(width, 7, text, border=1, align="R", fill=True)
#             pdf.ln()
#     else:
#         _write_text(pdf, "No numeric columns were available for pandas describe().", 6)

#     pdf.ln(7)
#     pdf.set_font("Helvetica", "B", 13)
#     pdf.set_text_color(25, 44, 53)
#     _write_text(pdf, "Customer Segmentation and Cohorts", 8)
#     pdf.set_font("Helvetica", "", 9)
#     pdf.set_text_color(45, 55, 60)
#     _write_text(pdf, summary["segment_note"])
#     for column, groups in summary["segment_insights"].items():
#         pdf.set_font("Helvetica", "B", 10)
#         pdf.set_x(pdf.l_margin)
#         pdf.cell(0, 6, _safe(f"Cohort: {column}"), new_x="LMARGIN", new_y="NEXT")
#         pdf.set_font("Helvetica", "", 9)
#         for group in groups:
#             values = [f"{key.removesuffix('_mean')} mean={value:.3f}" for key, value in group.items()
#                       if key.endswith("_mean") and value is not None]
#             detail = f"{group['segment']}: {group['rows']} rows"
#             if values:
#                 detail += "; " + ", ".join(values)
#             _write_text(pdf, detail)
#     if not summary["segment_insights"]:
#         _write_text(pdf, "No low-cardinality categorical cohort was available for segmentation.")

#     for caption, image in _make_charts(df):
#         pdf.add_page()
#         pdf.set_font("Helvetica", "B", 13)
#         pdf.set_text_color(25, 44, 53)
#         _write_text(pdf, caption, 8)
#         pdf.image(image, x=20, w=170)

#     pdf.add_page()
#     pdf.set_font("Helvetica", "B", 17)
#     pdf.set_text_color(25, 44, 53)
#     _write_text(pdf, "AI Findings and Recommendations", 10)
#     _write_ai_sections(pdf, ai_findings)

#     return bytes(pdf.output())



from io import BytesIO
from io import StringIO
from typing import Any

import numpy as np
import pandas as pd
import re 
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


# Professional report palette
NAVY = "#17324D"
TEAL = "#138A8A"
BLUE = "#3B82F6"
GOLD = "#E0A458"
CORAL = "#E76F51"
GREEN = "#2A9D8F"
PURPLE = "#7C5CFC"
LIGHT = "#F4F7FA"
MID = "#D9E2EC"
TEXT = "#263746"
MUTED = "#657786"

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
        "You are a senior data scientist writing a professional executive report. "
        "Analyze this sales dataset for evidence-grounded findings. Return concise markdown "
        "under these exact headings: Executive Summary, Key Numbers, Dataset Summary, "
        "Hypotheses, Critique, Recommendations, Proposed Actions, Customer Segmentation, "
        "Competitor Analysis, Limitations. "
        "Do not invent facts, "
        "competitor information, causes, or numerical estimates. Distinguish correlation "
        "from causation and state uncertainty. "
        "For what-if recommendations such as lower prices or higher marketing spend, "
        "state assumptions and recommend a controlled test instead of claiming an outcome.\n\n"
        f"Dataset: {source_name}\nDataset summary and cohort data:\n{summary}"
    )


def _chart_bytes(title: str, draw, figsize=(8.2, 4.6)) -> BytesIO:
    """Render a polished matplotlib chart directly to an in-memory PNG."""
    figure = Figure(figsize=figsize, dpi=160, facecolor="white")
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    axis.set_facecolor("white")
    draw(axis)

    axis.set_title(
        title,
        loc="left",
        fontsize=14,
        fontweight="bold",
        color=NAVY,
        pad=14,
    )
    axis.tick_params(colors=MUTED, labelsize=8)
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.grid(axis="y", color="#E8EEF3", linewidth=0.8)
    axis.set_axisbelow(True)

    figure.tight_layout(pad=1.5)
    image = BytesIO()
    figure.savefig(
        image,
        format="png",
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
    )
    image.seek(0)
    figure.clear()
    return image


def _pretty_name(value: Any) -> str:
    return str(value).replace("_", " ").strip().title()


def _make_charts(df: pd.DataFrame) -> list[tuple[str, BytesIO]]:
    """Create meaningful, dataset-adaptive visualizations."""
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    categories = [
        column
        for column in df.select_dtypes(exclude=[np.number]).columns
        if not any(token in str(column).lower() for token in ("date", "time", "timestamp"))
        and not str(column).lower().endswith("_id")
        and 2 <= df[column].nunique(dropna=True) <= 12
    ]

    preferred_pairs = [
        ("marketing_spend", "revenue"),
        ("discount_pct", "revenue"),
        ("churn_rate", "revenue"),
        ("avg_order_value", "revenue"),
    ]
    scatter_pair = next(
        (pair for pair in preferred_pairs if all(column in numeric_columns for column in pair)),
        None,
    )
    if scatter_pair is None and len(numeric_columns) >= 2:
        # Prefer a likely business metric as Y where possible.
        y = "revenue" if "revenue" in numeric_columns else numeric_columns[1]
        x = next((c for c in numeric_columns if c != y), numeric_columns[0])
        scatter_pair = (x, y)

    charts: list[tuple[str, BytesIO]] = []

    def draw_bar(axis) -> None:
        metric = "revenue" if "revenue" in numeric_columns else (
            numeric_columns[0] if numeric_columns else None
        )
        if categories and metric:
            means = (
                df.groupby(categories[0], observed=True)[metric]
                .mean()
                .dropna()
                .sort_values()
                .tail(10)
            )
            labels = [_pretty_name(v) for v in means.index]
            bars = axis.barh(labels, means.values, color=TEAL, height=0.62)
            axis.set_xlabel(f"Mean {_pretty_name(metric)}", color=MUTED)
            for bar, value in zip(bars, means.values):
                axis.text(
                    bar.get_width(),
                    bar.get_y() + bar.get_height() / 2,
                    f" {value:,.0f}",
                    va="center",
                    fontsize=8,
                    color=TEXT,
                )
        elif categories:
            counts = df[categories[0]].fillna("Missing").astype(str).value_counts().head(10)
            labels = [_pretty_name(v) for v in counts.index[::-1]]
            axis.barh(labels, counts.values[::-1], color=BLUE, height=0.62)
            axis.set_xlabel("Records", color=MUTED)
        elif numeric_columns:
            metric = "revenue" if "revenue" in numeric_columns else numeric_columns[0]
            values = df[metric].dropna()
            if values.empty:
                axis.text(0.5, 0.5, "No non-missing numeric values", ha="center", va="center")
                return
            counts, edges = np.histogram(values, bins=min(12, max(2, values.nunique())))
            centers = (edges[:-1] + edges[1:]) / 2
            axis.bar(centers, counts, width=np.diff(edges) * 0.88, color=TEAL)
            axis.set_xlabel(_pretty_name(metric), color=MUTED)
            axis.set_ylabel("Records", color=MUTED)
        else:
            axis.text(0.5, 0.5, "No plottable columns", ha="center", va="center")

    def draw_pie(axis) -> None:
        if categories:
            column = categories[0]
            counts = df[column].fillna("Missing").astype(str).value_counts()
            top = counts.head(6).copy()
            if len(counts) > len(top):
                top.loc["Other"] = counts.iloc[len(top):].sum()

            wedges, _, autotexts = axis.pie(
                top.values,
                labels=None,
                autopct="%1.1f%%",
                startangle=90,
                pctdistance=0.74,
                wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2},
                colors=[TEAL, BLUE, GOLD, CORAL, PURPLE, GREEN, "#94A3B8"],
            )
            for text in autotexts:
                text.set_color(NAVY)
                text.set_fontsize(8)
                text.set_fontweight("bold")
            axis.legend(
                wedges,
                [_pretty_name(v) for v in top.index],
                loc="center left",
                bbox_to_anchor=(0.98, 0.5),
                frameon=False,
                fontsize=8,
            )
        elif numeric_columns:
            values = df[numeric_columns[0]].dropna()
            if values.empty:
                axis.text(0.5, 0.5, "No non-missing numeric values", ha="center", va="center")
                return
            bins = pd.cut(values, bins=min(5, max(2, values.nunique()))).value_counts().sort_index()
            axis.pie(
                bins.values,
                labels=[str(item) for item in bins.index],
                autopct="%1.1f%%",
                startangle=90,
                wedgeprops={"edgecolor": "white", "linewidth": 2},
            )
        else:
            axis.text(0.5, 0.5, "No plottable columns", ha="center", va="center")

    def draw_trend(axis) -> None:
        metric = "revenue" if "revenue" in numeric_columns else (
            numeric_columns[0] if numeric_columns else None
        )
        if metric is None:
            axis.text(0.5, 0.5, "No numeric metric available", ha="center", va="center")
            return

        date_column = next(
            (
                column for column in df.columns
                if any(token in str(column).lower() for token in ("date", "time", "timestamp"))
            ),
            None,
        )

        values = df[metric]
        if date_column is not None:
            dates = pd.to_datetime(df[date_column], errors="coerce")
            temp = pd.DataFrame({"date": dates, "value": values}).dropna()
            if not temp.empty:
                temp = temp.sort_values("date")
                # Aggregate to daily/monthly observations where appropriate.
                if temp["date"].dt.normalize().nunique() > 40:
                    temp["period"] = temp["date"].dt.to_period("M").dt.to_timestamp()
                    grouped = temp.groupby("period")["value"].mean()
                    axis.plot(
                        grouped.index, grouped.values,
                        color=BLUE, linewidth=2.4, marker="o", markersize=3
                    )
                    axis.fill_between(
                        grouped.index, grouped.values,
                        np.nanmin(grouped.values),
                        alpha=0.08,
                        color=BLUE,
                    )
                    axis.set_xlabel("Period", color=MUTED)
                else:
                    axis.plot(
                        temp["date"], temp["value"],
                        color=BLUE, linewidth=2.0
                    )
                    axis.set_xlabel(_pretty_name(date_column), color=MUTED)
            else:
                axis.plot(values.dropna().to_numpy(), color=BLUE, linewidth=2.0)
                axis.set_xlabel("Record order", color=MUTED)
        else:
            rolling = values.dropna().reset_index(drop=True)
            axis.plot(rolling.to_numpy(), color=BLUE, linewidth=1.8, alpha=0.65)
            if len(rolling) >= 5:
                window = max(3, min(15, len(rolling) // 10))
                smooth = rolling.rolling(window, min_periods=1).mean()
                axis.plot(smooth, color=CORAL, linewidth=2.4, label=f"{window}-point moving average")
                axis.legend(frameon=False, fontsize=8)
            axis.set_xlabel("Record order", color=MUTED)

        axis.set_ylabel(_pretty_name(metric), color=MUTED)

    def draw_scatter(axis) -> None:
        if scatter_pair is None:
            axis.text(0.5, 0.5, "At least two numeric columns are needed", ha="center", va="center")
            return

        x_column, y_column = scatter_pair
        points = df[[x_column, y_column]].dropna()

        if points.empty:
            axis.text(0.5, 0.5, "No complete observations available", ha="center", va="center")
            return

        # Limit rendered points for very large datasets without changing the analysis.
        plot_points = points.sample(min(len(points), 3000), random_state=42)

        axis.scatter(
            plot_points[x_column],
            plot_points[y_column],
            s=24,
            alpha=0.48,
            color=TEAL,
            edgecolors="white",
            linewidths=0.35,
        )

        correlation = points[x_column].corr(points[y_column])

        if len(points) >= 2 and points[x_column].nunique() > 1:
            x_values = points[x_column].to_numpy(dtype=float)
            y_values = points[y_column].to_numpy(dtype=float)
            slope, intercept = np.polyfit(x_values, y_values, 1)
            line_x = np.linspace(x_values.min(), x_values.max(), 100)
            axis.plot(
                line_x,
                slope * line_x + intercept,
                color=CORAL,
                linewidth=2.2,
                label="Linear trend",
            )
            axis.legend(frameon=False, fontsize=8)

        axis.set_xlabel(_pretty_name(x_column), color=MUTED)
        axis.set_ylabel(_pretty_name(y_column), color=MUTED)

        if pd.notna(correlation):
            strength = abs(float(correlation))
            direction = "positive" if correlation > 0 else "negative"
            axis.text(
                0.03,
                0.97,
                f"Pearson r = {correlation:+.3f}\n"
                f"{direction} association · not causal evidence",
                transform=axis.transAxes,
                va="top",
                fontsize=8,
                color=TEXT,
                bbox={
                    "boxstyle": "round,pad=0.45",
                    "facecolor": "#F4F7FA",
                    "edgecolor": MID,
                },
            )

    charts.append(("Performance by Segment", _chart_bytes("Average performance by cohort", draw_bar)))
    charts.append(("Category Composition", _chart_bytes("Dataset composition", draw_pie)))
    charts.append(("Trend Analysis", _chart_bytes("Metric trend", draw_trend)))
    charts.append(("Relationship Analysis", _chart_bytes("Relationship between key metrics", draw_scatter)))

    return charts

def _write_text(pdf: ReportPDF, text: str, line_height: float = 5) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, line_height, _safe(text))


def _write_ai_sections(pdf: ReportPDF, findings: str) -> None:
    """Render Ollama findings as structured, readable report sections."""
    aliases = {
        "executive summary": "Executive Summary",
        "key numbers": "Key Numbers",
        "dataset summary": "Dataset Summary",
        "hypothesis": "Hypotheses",
        "hypotheses": "Hypotheses",
        "critique": "Critique",
        "recommendation": "Recommendations",
        "recommendations": "Recommendations",
        "proposed action": "Proposed Actions",
        "proposed actions": "Proposed Actions",
        "competitor analysis": "Competitor Analysis",
        "customer segmentation": "Customer Segmentation",
        "limitations": "Limitations",
    }

    section_order = (
        "Executive Summary",
        "Key Numbers",
        "Dataset Summary",
        "Hypotheses",
        "Critique",
        "Recommendations",
        "Proposed Actions",
        "Customer Segmentation",
        "Competitor Analysis",
        "Limitations",
    )
    sections: dict[str, list[str]] = {title: [] for title in section_order}
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
            current = "Executive Summary"

        sections[current].append(line)

    section_colors = {
        "Executive Summary": TEAL,
        "Key Numbers": BLUE,
        "Dataset Summary": PURPLE,
        "Hypotheses": GOLD,
        "Critique": CORAL,
        "Recommendations": GREEN,
        "Proposed Actions": TEAL,
        "Customer Segmentation": BLUE,
        "Competitor Analysis": PURPLE,
        "Limitations": MUTED,
    }

    for title in section_order:
        lines = sections[title]
        if not lines:
            continue

        pdf.ln(4)
        color = section_colors.get(title, TEAL)
        pdf.set_fill_color(*_hex_rgb(color))
        pdf.rect(pdf.l_margin, pdf.get_y(), 3, 8, style="F")
        pdf.set_x(pdf.l_margin + 6)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*_hex_rgb(NAVY))
        pdf.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_hex_rgb(TEXT))

        for line in lines:
            clean = re.sub(r"^[-*•]\s*", "", line)
            is_bullet = clean != line or re.match(r"^\d+[.)]\s+", line) is not None
            if is_bullet:
                clean = re.sub(r"^\d+[.)]\s+", "", clean)
                pdf.set_x(pdf.l_margin + 4)
                pdf.set_text_color(*_hex_rgb(color))
                pdf.cell(4, 5, "-")
                pdf.set_x(pdf.l_margin + 9)
                pdf.set_text_color(*_hex_rgb(TEXT))
                _write_text(pdf, clean, 5)
            else:
                _write_text(pdf, clean, 5)

def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

def generate_sales_report_pdf(
    df: pd.DataFrame,
    source_name: str,
    summary: dict[str, Any],
    ai_findings: str,
) -> bytes:
    """Generate a professional, colorful, evidence-grounded A4 PDF report."""
    pdf = ReportPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)

    # -----------------------------
    # Cover
    # -----------------------------
    pdf.add_page()
    pdf.set_fill_color(*_hex_rgb(NAVY))
    pdf.rect(0, 0, pdf.w, 92, style="F")

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 27)
    pdf.set_xy(20, 28)
    pdf.cell(0, 13, "SALES INTELLIGENCE", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 12)
    pdf.set_x(20)
    pdf.cell(
        0, 8,
        "Evidence-grounded analysis, business patterns, and practical next steps",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_fill_color(*_hex_rgb(GOLD))
    pdf.rect(20, 82, 58, 3, style="F")

    pdf.set_y(116)
    pdf.set_text_color(*_hex_rgb(NAVY))
    pdf.set_font("Helvetica", "B", 22)
    _write_text(pdf, "Professional Data Analysis Report", 12)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_hex_rgb(MUTED))
    _write_text(pdf, f"Source dataset: {source_name}", 6)
    _write_text(
        pdf,
        f"{summary['rows']:,} records  ·  {len(summary['columns'])} columns  ·  "
        f"Generated from deterministic analysis + local AI findings",
        6,
    )

    pdf.ln(14)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_hex_rgb(TEXT))
    _write_text(
        pdf,
        "Purpose",
        6,
    )
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_hex_rgb(MUTED))
    _write_text(
        pdf,
        "Provide a concise view of dataset health, key business metrics, "
        "observed relationships, evidence-backed hypotheses, and recommended actions.",
        5,
    )

    # -----------------------------
    # Executive Summary + KPI cards
    # -----------------------------
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 19)
    pdf.set_text_color(*_hex_rgb(NAVY))
    _write_text(pdf, "Executive Summary", 10)

    primary_metric = (
        "revenue" if "revenue" in summary["numeric"]
        else next(iter(summary["numeric"]), None)
    )

    missing_cells = int(df.isna().sum().sum())
    missing_pct = (missing_cells / max(1, df.size)) * 100
    duplicate_rows = int(df.duplicated().sum())
    numeric_count = len(summary["numeric"])
    categorical_count = len(df.select_dtypes(exclude=[np.number]).columns)

    cards = [
        ("RECORDS", f"{len(df):,}", TEAL),
        ("COLUMNS", f"{len(df.columns):,}", BLUE),
        ("MISSING", f"{missing_pct:.1f}%", CORAL),
        ("DUPLICATES", f"{duplicate_rows:,}", GOLD),
    ]

    card_gap = 4
    card_width = (pdf.w - pdf.l_margin - pdf.r_margin - card_gap * 3) / 4
    card_y = pdf.get_y() + 3

    for index, (label, value, color) in enumerate(cards):
        x = pdf.l_margin + index * (card_width + card_gap)
        pdf.set_fill_color(*_hex_rgb(LIGHT))
        pdf.set_draw_color(*_hex_rgb(MID))
        pdf.rect(x, card_y, card_width, 25, style="DF")
        pdf.set_fill_color(*_hex_rgb(color))
        pdf.rect(x, card_y, 3, 25, style="F")

        pdf.set_xy(x + 7, card_y + 5)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*_hex_rgb(MUTED))
        pdf.cell(card_width - 10, 5, label)

        pdf.set_xy(x + 7, card_y + 12)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*_hex_rgb(NAVY))
        pdf.cell(card_width - 10, 8, value)

    pdf.set_y(card_y + 34)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_hex_rgb(TEXT))

    if primary_metric:
        metric_stats = summary["numeric"][primary_metric]
        if metric_stats["mean"] is not None:
            mean = metric_stats["mean"]
            median = metric_stats["median"]
            minimum = metric_stats["min"]
            maximum = metric_stats["max"]
            _write_text(
                pdf,
                f"Primary metric — {_pretty_name(primary_metric)}: "
                f"mean {mean:,.2f}, median {median:,.2f}, "
                f"range {minimum:,.2f} to {maximum:,.2f}.",
                6,
            )

    _write_text(
        pdf,
        f"The dataset contains {numeric_count} numeric and {categorical_count} "
        "categorical columns. Findings in this report describe observed patterns; "
        "correlation should not be interpreted as causation without further testing.",
        6,
    )

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_hex_rgb(NAVY))
    _write_text(pdf, "Data Quality Snapshot", 7)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_hex_rgb(TEXT))
    _write_text(
        pdf,
        f"Missing cells: {missing_cells:,} ({missing_pct:.2f}% of all cells). "
        f"Duplicate rows: {duplicate_rows:,}. "
        f"Customer segmentation note: {summary['segment_note']}",
        6,
    )

    # -----------------------------
    # Dataset summary
    # -----------------------------
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*_hex_rgb(NAVY))
    _write_text(pdf, "Dataset Summary", 10)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_hex_rgb(MUTED))
    _write_text(
        pdf,
        "Descriptive statistics below are calculated directly from the supplied DataFrame.",
        6,
    )

    describe_rows = ("count", "mean", "std", "min", "25%", "50%", "75%", "max")
    describe = summary["describe"]

    if describe:
        headers = ["Statistic"] + list(describe.keys())
        max_metric_columns = min(len(headers) - 1, 6)
        headers = headers[:max_metric_columns + 1]

        available_width = pdf.w - pdf.l_margin - pdf.r_margin
        first_width = 29
        other_width = (available_width - first_width) / max(1, len(headers) - 1)
        widths = [first_width] + [other_width] * (len(headers) - 1)

        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(*_hex_rgb(NAVY))

        for header, width in zip(headers, widths):
            pdf.cell(width, 7, _safe(str(header)[:17]), border=1, align="C", fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 7)
        for index, statistic in enumerate(describe_rows):
            pdf.set_x(pdf.l_margin)
            row_color = "#F4F7FA" if index % 2 == 0 else "#FFFFFF"
            pdf.set_fill_color(*_hex_rgb(row_color))
            pdf.set_text_color(*_hex_rgb(TEXT))
            pdf.cell(widths[0], 7, statistic, border=1, fill=True)

            for column, width in zip(headers[1:], widths[1:]):
                value = describe.get(column, {}).get(statistic)
                text = "-" if value is None else f"{value:.3g}"
                pdf.cell(width, 7, text, border=1, align="R", fill=True)
            pdf.ln()

    pdf.ln(7)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*_hex_rgb(NAVY))
    _write_text(pdf, "Cohort & Customer Segmentation", 8)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_hex_rgb(TEXT))
    _write_text(pdf, summary["segment_note"], 6)

    for column, groups in summary["segment_insights"].items():
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_hex_rgb(TEAL))
        pdf.set_x(pdf.l_margin)
        pdf.cell(
            0, 6,
            _safe(f"Cohort: {_pretty_name(column)}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_hex_rgb(TEXT))

        for group in groups[:10]:
            values = [
                f"{key.removesuffix('_mean').replace('_', ' ')}={value:.2f}"
                for key, value in group.items()
                if key.endswith("_mean") and value is not None
            ]
            detail = f"{group['segment']}: {group['rows']:,} rows"
            if values:
                detail += " · " + " · ".join(values)
            _write_text(pdf, detail, 5)

    if not summary["segment_insights"]:
        _write_text(pdf, "No low-cardinality categorical cohort was available for segmentation.", 6)

    # -----------------------------
    # Visualizations
    # -----------------------------
    for caption, image in _make_charts(df):
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*_hex_rgb(NAVY))
        _write_text(pdf, caption, 9)

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_hex_rgb(MUTED))

        chart_descriptions = {
            "Performance by Segment": "Compares average performance across the most useful low-cardinality cohort available.",
            "Category Composition": "Shows how observations are distributed across the primary categorical cohort.",
            "Trend Analysis": "Shows the primary metric over time where a date field exists, otherwise across record order.",
            "Relationship Analysis": "Shows the strongest available business-metric pairing and its linear association.",
        }
        _write_text(pdf, chart_descriptions.get(caption, ""), 5)
        pdf.ln(3)
        pdf.image(image, x=pdf.l_margin, w=pdf.w - pdf.l_margin - pdf.r_margin)

    # -----------------------------
    # AI findings
    # -----------------------------
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 19)
    pdf.set_text_color(*_hex_rgb(NAVY))
    _write_text(pdf, "Hypotheses, Critique & Recommendations", 10)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_hex_rgb(MUTED))
    _write_text(
        pdf,
        "The following sections are generated by the configured Ollama model from "
        "the supplied dataset summary. Numerical claims should remain traceable to the dataset.",
        6,
    )

    _write_ai_sections(pdf, ai_findings)

    # -----------------------------
    # Final methodology note
    # -----------------------------
    pdf.ln(8)
    pdf.set_fill_color(*_hex_rgb(LIGHT))
    pdf.set_draw_color(*_hex_rgb(MID))
    pdf.rect(
        pdf.l_margin,
        pdf.get_y(),
        pdf.w - pdf.l_margin - pdf.r_margin,
        28,
        style="DF",
    )
    pdf.set_xy(pdf.l_margin + 6, pdf.get_y() + 5)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_hex_rgb(NAVY))
    pdf.cell(0, 5, "Methodology & Interpretation", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin + 6)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*_hex_rgb(MUTED))
    _write_text(
        pdf,
        "Charts use deterministic pandas/matplotlib calculations. AI findings are intended "
        "to interpret observed evidence, not replace statistical validation or controlled experiments.",
        4.5,
    )

    return bytes(pdf.output())

