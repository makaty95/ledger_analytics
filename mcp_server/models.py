from pydantic import model_validator
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

# widgets structures
class ParagraphData(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str

class BarChartSeries(BaseModel):
    name: str
    values: list[float]

class BarChartData(BaseModel):
    type: Literal["bar_chart"] = "bar_chart"
    title: str
    x_label: str
    y_label: str
    categories: list[str]
    series: list[BarChartSeries]

    @model_validator(mode="after")
    def check_series_lengths(self):
        for s in self.series:
            if len(s.values) != len(self.categories):
                raise ValueError(
                    f"Series '{s.name}' has {len(s.values)} values, "
                    f"but there are {len(self.categories)} categories "
                    f"({len(self.categories)} values are required per series)."
                )
        return self

class PieChartData(BaseModel):
    type: Literal["pie_chart"] = "pie_chart"
    title: str
    categories: list[str]
    values: list[float]

    @model_validator(mode="after")
    def check_lengths_and_values(self):
        if len(self.categories) != len(self.values):
            raise ValueError(
                f"categories has {len(self.categories)} entries but "
                f"values has {len(self.values)} — they must match, one "
                f"value per category."
            )
        if any(v < 0 for v in self.values):
            raise ValueError("Pie chart values cannot be negative.")
        if len(self.categories) < 2:
            raise ValueError("A pie chart needs at least 2 categories.")
        return self

class LineChartSeries(BaseModel):
    name: str
    values: list[float]


class LineChartData(BaseModel):
    type: Literal["line_chart"] = "line_chart"
    title: str
    x_label: str
    y_label: str
    categories: list[str]
    series: list[LineChartSeries]

    @model_validator(mode="after")
    def check_validator(self):
        for s in self.series:
            if len(s.values) != len(self.categories):
                raise ValueError (
                    f"Series '{s.name}' has {len(s.values)} values, "
                    f"but there are {len(self.categories)} categories "
                    f"({len(self.categories)} values are required per series)."
                )
        return self

class ScatterPoint(BaseModel):
    x: float
    y: float


class ScatterChartSeries(BaseModel):
    name: str
    points: list[ScatterPoint]


class ScatterChartData(BaseModel):
    type: Literal["scatter_chart"] = "scatter_chart"
    title: str
    x_label: str
    y_label: str
    series: list[ScatterChartSeries]

    @model_validator(mode="after")
    def check_series_have_points(self):
        for s in self.series:
            if not s.points:
                raise ValueError(f"Series '{s.name}' has no points.")
        return self

WidgetData = Annotated[
    Union[ParagraphData, BarChartData, PieChartData, LineChartData, ScatterChartData],
    Field(discriminator="type")
]
