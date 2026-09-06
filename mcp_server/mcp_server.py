import json

from mcp.server.fastmcp import FastMCP
import sys
import os
from typing import Any
import mysql.connector
from mcp.types import ToolAnnotations
from pydantic import TypeAdapter
from dotenv import load_dotenv
from models import *

load_dotenv()
server = FastMCP('makaty-server-Demo')

WidgetListAdapter = TypeAdapter(list[WidgetData])
conn = None

class PageContent:
    title: str = "Untitled Report"
    results_page_contents: list[WidgetData] = []

    @classmethod
    def update_title(cls, title: str):
        cls.title = title

    @classmethod
    def add_to_content(cls, widget_data: WidgetData):
        cls.results_page_contents.append(widget_data)

    @classmethod
    def clear_content(cls):
        cls.results_page_contents.clear()
        cls.title = "Untitled Report"

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
@server.resource(
    uri="report://current",
    name="results_page_contents",
    description="this resource contains all the blocks in the results page",
    mime_type="application/json")
def get_current_report() -> str:
    blocks_json = WidgetListAdapter.dump_python(PageContent.results_page_contents, mode="json")
    payload = {
        "title": PageContent.title,
        "content": blocks_json,
    }
    return json.dumps(payload, indent=2)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@server.tool(
    name="set_page_title",
    title="Set Results Page Title",
    description=(
        "Sets the title shown at the top of the analytics results page."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,      # mutates server-side state (the page title)
        destructiveHint=False,   # overwrites the title, but doesn't delete any page blocks
        idempotentHint=True,      # calling it twice with the same title leaves the same end state
        openWorldHint=False,     # only touches local server state, no external systems
    ),
    structured_output=True,
)
def set_page_title(title: str) -> str:
    """
    Sets the results page's title. Call this once, typically at the
    start of building a results page, to give it a clear, descriptive
    title summarizing what the page covers (e.g., "Top Customers by
    Revenue — Q2 2026"). Calling it again later replaces the previous
    title.

    Args:
        title: The new title for the results page. Should be short and
            descriptive — a few words summarizing the analysis, not a
            full sentence.

    Returns:
        The title that was set.
    """
    PageContent.update_title(title)
    return title


@server.tool(
    name="execute_select_query",
    description=(
        "Execute a read-only SQL SELECT query against the MySQL database "
        "and return the resulting rows. Only SELECT queries are allowed. "
        "Use %s placeholders for query parameters and provide their values "
        "in params."
    )
)
def execute_db_query(
    query: str,
    params: tuple[Any, ...] = ()
) -> str:

    cursor = conn.cursor()

    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()

        result = ""
        for row in rows:
            result += f"\n{row}"

        return result

    finally:
        cursor.close()





@server.tool(
    name="clear_results_page",
    title="Clear Results Page",
    description="Clears the results page, removing all previously added blocks.",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,    # this one DOES destroy existing state (wipes the page)
        idempotentHint=True,     # calling it repeatedly has the same end effect (empty page)
        openWorldHint=False,
    ),
)
def clear_results_page() -> str:
    """
    Clears the results page, removing all previously added blocks.

    Use this at the very start of building a new results page, if the
    page may already contain blocks from a previous analysis in this
    session, so the new page starts empty rather than appending after
    old content.

    Returns:
        A confirmation that the page was cleared.
    """
    PageContent.clear_content()
    return json.dumps({"cleared": True})







@server.tool(name="add_paragraph_block")
def add_paragraph_block(text: str) -> ParagraphData:
    """
    Adds a paragraph of text to the analytics results page.

    Use this tool whenever you want to add a written explanation, summary,
    insight, or transition between visualizations on the results page —
    for example, introducing what a chart shows, summarizing a finding in
    words, or writing a short conclusion after presenting data.

    The results page is built as an ordered sequence of blocks. Each call
    to a block-adding tool (this one, or add_bar_chart_block) appends one
    new block to the END of that sequence, in the exact order the tool
    calls are made. For example, calling this tool, then add_bar_chart_block,
    then this tool again produces: paragraph -> bar chart -> paragraph,
    in that order, on the page.

    Call this tool once per paragraph. Do not combine multiple unrelated
    paragraphs into a single call — call the tool again for each new
    paragraph you want to add.

    Args:
        text: The paragraph's plain text content. Write it as you would
            normally write a clear, concise explanation for a business
            user reading a dashboard — no markdown formatting, no headers,
            just plain prose. Keep each paragraph focused on a single idea
            (e.g., one insight, one summary, one transition) rather than
            combining multiple unrelated points into one long paragraph.

    Returns:
        The structured paragraph block that was added to the results page.
    """
    data = ParagraphData(text=text)
    PageContent.add_to_content(data)
    return data


@server.tool(name="add_pie_chart_block")
def add_pie_chart_block(
        title: str,
        categories: list[str],
        values: list[float]
) -> PieChartData:
    """
    Adds a pie chart, appended to the end of the results page's block
    sequence. Use this specifically for "parts of a whole"
    breakdowns (e.g., revenue share by product line, headcount by
    department) — not for side-by-side comparisons across multiple
    groupings, which a bar chart is better suited for.

    Only call this immediately after obtaining the real underlying data
    from a data-fetching tool; use the EXACT values that tool returned.
    Do not estimate, round, recall from memory, or invent numbers.

    Call this tool once per chart. If you need to show two unrelated
    breakdowns, call this tool twice rather than combining them.

    Args:
        title: The chart's title, shown above/within the chart (e.g.,
            "Revenue by Product Line").
        categories: The list of category names, one per slice (e.g.,
            ["Product A", "Product B", "Product C"]). Must have at least
            2 entries.
        values: The raw magnitude for each category, in the same order
            as `categories` (e.g., [45000, 30000, 25000] for actual
            revenue amounts — not pre-computed percentages; the chart
            renderer calculates proportions automatically). Must be the
            same length as `categories`, and all values must be
            non-negative.

    Returns:
        The structured pie chart block that was added to the results
        page.
        """

    data = PieChartData(title=title, categories=categories, values=values)
    PageContent.add_to_content(data)
    return data


@server.tool(
    name="add_scatter_chart_block",
    title="Add Scatter Chart to Results Page",
    description=(
        "Adds a scatter chart to the analytics results page, showing "
        "the relationship between two numeric variables as individual "
        "(x, y) points."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
    structured_output=True,
)
def add_scatter_chart_block(
        title: str,
        x_label: str,
        y_label: str,
        series: list[ScatterChartSeries]
) -> ScatterChartData:
    """
    Adds a scatter chart, appended to the end of the results page's
    block sequence — in the same ordered queue as the other add_*_block
    tools. Use this specifically to show the relationship or correlation
    between two numeric variables (e.g., order size vs. delivery time,
    age vs. spending) — not for comparing discrete categories (use a bar
    chart) or trends over an ordered sequence like time (use a line
    chart).

    Only call this immediately after obtaining the real underlying data
    from a data-fetching tool; use the EXACT values that tool returned.
    Do not estimate, invent, or approximate coordinates.

    Call this tool once per chart. If you need to show two unrelated
    relationships, call this tool twice rather than combining them.

    Args:
        title: The chart's title (e.g., "Order Size vs. Delivery Time").
        x_label: What the x-coordinate represents, including units if
            relevant (e.g., "Order Size (items)").
        y_label: What the y-coordinate represents, including units if
            relevant (e.g., "Delivery Time (days)").
        series: One or more named groups of (x, y) points. Use multiple
            series to distinguish different groups of points on the same
            chart (e.g., one series per region), each shown in a
            different color with a legend. Each series must have at
            least one point.

    Returns:
        The structured scatter chart block that was added to the
        results page.
    """

    data = ScatterChartData(title=title, x_label=x_label, y_label=y_label, series=series)
    PageContent.add_to_content(data)
    return data


@server.tool(
    name="add_line_chart_block",
    title="Add Line Chart to Results Page",
    description=(
        "Adds a line chart to the analytics results page, showing how "
        "one or more numeric series change across an ordered sequence "
        "of categories (typically time)."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,      # mutates server-side state (appends to the page)
        destructiveHint=False,   # only appends — never deletes or overwrites existing blocks
        idempotentHint=False,    # calling it twice with the same args adds two separate blocks
        openWorldHint=False,     # only touches local server state, no external systems
    ),
    structured_output=True,
)
def add_line_chart_block(
        x_label: str,
        y_label: str,
        title: str,
        categories: list[str],
        series: list[LineChartSeries]
) -> LineChartData:
    """
    Adds a line chart, appended to the end of the results page's block
    sequence — in the same ordered queue as the other add_*_block
    tools. Use this specifically for
    trends over an ordered sequence (most commonly time, e.g. revenue by
    month) — not for comparing unordered discrete categories, which a
    bar chart is better suited for, and not for parts-of-a-whole
    breakdowns, which a pie chart is better suited for.

    Only call this immediately after obtaining the real underlying data
    from a data-fetching tool; use the EXACT values that tool returned.
    Do not estimate, round, recall from memory, or invent numbers.

    Call this tool once per chart. If you need to show two unrelated
    trends, call this tool twice rather than combining them into a
    single chart with unrelated series.

    Args:
        title: The chart's title, shown above the chart (e.g.,
            "Monthly Revenue Trend").
        x_label: Label describing what the categories represent, shown
            below the x-axis (e.g., "Month").
        y_label: Label describing what the values represent, shown
            beside the y-axis, including units if relevant (e.g.,
            "Revenue ($)").
        categories: The ordered list of points along the x-axis (e.g.,
            ["Jan", "Feb", "Mar", "Apr"]). Every series' `values` list
            must contain exactly one number per category, in the same
            order.
        series: One or more named lines to plot. Each series' `values`
            list must have the SAME length as `categories`, with each
            value at the same index corresponding to the category at
            that index. Example: if categories is
            ["Jan", "Feb", "Mar", "Apr"], a series named "Revenue" with
            values [1200, 1400, 1300, 1600] means Jan=1200, Feb=1400,
            Mar=1300, Apr=1600.

    Returns:
        The structured line chart block that was added to the results page.
        """

    data = LineChartData(
        title=title,
        x_label=x_label,
        y_label=y_label,
        categories=categories,
        series=series)
    PageContent.add_to_content(data)
    return data


@server.tool(name="add_bar_chart_block")
def add_bar_chart_block(
        title: str,
        x_label: str,
        y_label: str,
        categories: list[str],
        series: list[BarChartSeries],
) -> BarChartData:
    """
    Adds a bar chart to the analytics results page.

    Use this tool whenever you want to visually display categorical or
    comparative numeric data on the results page — for example, comparing
    totals across regions, time periods, product categories, or any other
    set of discrete groups. Only call this tool immediately after
    obtaining the real underlying data from a data-fetching tool; use the
    EXACT values that tool returned. Do not estimate, round, recall from
    memory, or invent numbers when calling this tool.

    The results page is built as an ordered sequence of blocks. Each call
    to a block-adding tool (this one, or add_paragraph_block) appends one
    new block to the END of that sequence, in the exact order the tool
    calls are made. For example, calling add_paragraph_block, then this
    tool, then add_paragraph_block again produces: paragraph -> bar chart
    -> paragraph, in that order, on the page.

    Call this tool once per chart. If you need to show two unrelated
    comparisons, call this tool twice (once per chart) rather than trying
    to combine them into a single chart with more series.

    Args:
        title: The chart's title, shown above the chart (e.g.,
            "Sales by Region").
        x_label: Label describing what the categories represent, shown
            below the x-axis (e.g., "Region").
        y_label: Label describing what the values represent, shown beside
            the y-axis, including units if relevant (e.g., "Revenue ($)").
        categories: The list of category names shown along the x-axis
            (e.g., ["North", "South", "East", "West"]). Every series'
            `values` list below must contain exactly one number per
            category, in the same order as this list.
        series: One or more named sets of values to plot. Each series
            becomes one bar per category (if there are multiple series,
            each category shows one grouped cluster of bars — one bar per
            series, with a legend distinguishing them). Each series'
            `values` list must have the SAME length as `categories`, with
            each value at the same index corresponding to the category at
            that index. Example: if categories is
            ["North", "South", "East", "West"], a series named "Q1" with
            values [1200, 900, 1500, 700] means North=1200, South=900,
            East=1500, West=700 for Q1.

    Returns:
        The structured bar chart block that was added to the results page.
    """
    data = BarChartData(
        title=title,
        x_label=x_label,
        y_label=y_label,
        categories=categories,
        series=series,
    )
    PageContent.add_to_content(data)
    return data

def init_connection():
    db_name = os.getenv("DB_NAME")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    global conn
    conn = mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        port=db_port
    )

    print("\nDB connection initialized successfully", file=sys.stderr)
    print(f"DB: {db_name}", file=sys.stderr)
    print(f"HOST: {db_host}", file=sys.stderr)
    print(f"PORT: {db_port}", file=sys.stderr)


if __name__ == '__main__':

    init_connection()
    print("\nMCP Server created successfully :)", file=sys.stderr)
    server.run(transport='stdio')
