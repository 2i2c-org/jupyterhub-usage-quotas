"""Tests for Jinja2 template rendering"""

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from jupyterhub_usage_quotas import get_template_path
from tests.services.fixtures.usage_data import (
    COMPUTE_USAGE_MULTIPLE,
    COMPUTE_USAGE_NO_DATA,
    COMPUTE_USAGE_SINGLE,
    STORAGE_USAGE_0_PCT,
    STORAGE_USAGE_50_PCT,
    STORAGE_USAGE_95_PCT,
    STORAGE_USAGE_100_PCT,
    STORAGE_USAGE_NO_DATA,
    STORAGE_USAGE_PROMETHEUS_ERROR,
    STORAGE_USAGE_TERABYTES,
)


@pytest.fixture
def jinja_env():
    """Create Jinja2 environment for template rendering"""
    return Environment(loader=FileSystemLoader(get_template_path()), autoescape=True)


def render_template(
    jinja_env: Environment,
    storage_data: dict = None,
    compute_data: list = None,
    enable_storage: bool = True,
    enable_compute: bool = True,
):
    """Helper to render template and return BeautifulSoup object"""
    template = jinja_env.get_template("usage.html")
    html_content = template.render(
        {
            "storage_data": storage_data,
            "compute_data": compute_data,
            "enable_storage": enable_storage,
            "enable_compute": enable_compute,
        }
    )
    return BeautifulSoup(html_content, "html.parser")


class TestUsageTemplateWithNormalUsage:
    """Test template rendering with normal usage (< 90%)"""

    def test_displays_correct_usage_percentage(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        progress_label = soup.find(class_="progress-label")
        assert progress_label is not None
        assert "50.0%" in progress_label.text

    def test_displays_usage_and_quota_in_gib(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        metric_usage = soup.find(class_="metric-usage")
        assert metric_usage is not None
        assert "5.0 GiB used" in metric_usage.text
        assert "10.0 GiB quota" in metric_usage.text

    def test_displays_remaining_storage(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        metric_remaining = soup.find(class_="metric-remaining")
        assert metric_remaining is not None
        assert "5.0 GiB remaining" in metric_remaining.text

    def test_progress_bar_width_matches_percentage(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        progress_fill = soup.find(class_="progress-fill")
        assert progress_fill is not None
        assert "width: 50.0%" in progress_fill.get("style", "")

    def test_uses_normal_styling_below_90_percent(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        progress_fill = soup.find(class_="progress-fill")
        style = progress_fill.get("style", "")
        assert "#ef4444" not in style

    def test_displays_last_updated_timestamp(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        time_element = soup.find("time")
        assert time_element is not None
        assert time_element.has_attr("datetime")
        assert STORAGE_USAGE_50_PCT["last_updated"] in time_element["datetime"]

    def test_shows_normal_folder_icon(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        svgs = soup.find_all("svg", class_="icon")
        assert len(svgs) > 0
        circles = soup.find_all("circle")
        assert len(circles) == 0


class TestUsageTemplateWithHighUsage:
    """Test template rendering with high usage (>= 90%)"""

    def test_displays_sad_folder_icon_at_95_percent(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_95_PCT, COMPUTE_USAGE_SINGLE)
        circles = soup.find_all("circle")
        assert len(circles) == 2

    @pytest.mark.parametrize(
        "css_class,expected_style",
        [
            ("progress-fill", "background: #ef4444"),
            ("metric-remaining", "color: #ef4444"),
            ("progress-label", "color: #ef4444"),
        ],
    )
    def test_high_usage_elements_are_red(self, jinja_env, css_class, expected_style):
        soup = render_template(jinja_env, STORAGE_USAGE_95_PCT, COMPUTE_USAGE_SINGLE)
        element = soup.find(class_=css_class)
        assert expected_style in element.get("style", "")

    def test_percentage_threshold_at_exactly_90(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_95_PCT, COMPUTE_USAGE_SINGLE)
        progress_fill = soup.find(class_="progress-fill")
        assert "#ef4444" in progress_fill.get("style", "")


class TestUsageTemplateWithErrors:
    """Test template rendering with error states"""

    def test_displays_error_message_when_prometheus_down(self, jinja_env):
        soup = render_template(
            jinja_env, STORAGE_USAGE_PROMETHEUS_ERROR, COMPUTE_USAGE_NO_DATA
        )
        error_message = soup.find(class_="error-message")
        assert error_message is not None
        assert "Unable to reach Prometheus" in error_message.text

    def test_displays_error_icon_not_folder(self, jinja_env):
        soup = render_template(
            jinja_env, STORAGE_USAGE_PROMETHEUS_ERROR, COMPUTE_USAGE_NO_DATA
        )
        svgs = soup.find_all("svg", class_="icon")
        assert len(svgs) > 0
        svg = svgs[0]
        assert 'stroke="#ef4444"' in str(svg) or svg.get("stroke") == "#ef4444"

    def test_error_state_has_no_progress_bar(self, jinja_env):
        soup = render_template(
            jinja_env, STORAGE_USAGE_PROMETHEUS_ERROR, COMPUTE_USAGE_NO_DATA
        )
        progress_track = soup.find(class_="progress-track")
        assert progress_track is None

    def test_displays_no_data_error(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_NO_DATA, COMPUTE_USAGE_NO_DATA)
        error_message = soup.find(class_="error-message")
        assert error_message is not None
        assert "No storage data found" in error_message.text

    def test_error_message_has_red_styling(self, jinja_env):
        template = jinja_env.get_template("usage.html")
        html_content = template.render(
            storage_data=STORAGE_USAGE_PROMETHEUS_ERROR,
            compute_data=COMPUTE_USAGE_SINGLE,
        )
        assert ".error-message" in html_content
        assert "color: #ef4444" in html_content or "color:#ef4444" in html_content


class TestUsageTemplateMultipleCompute:
    """Test template rendering with multiple compute usage quotas."""

    def test_displays_collapsed_content(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_MULTIPLE)
        collapsed_content = soup.find_all("div", attrs={"data-bs-toggle": "collapse"})
        assert collapsed_content is not None

    def test_displays_multiple_quotas(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_MULTIPLE)
        compute_div = soup.find(id="compute")
        metric_item_div = compute_div.find_all(class_="metric-item")
        assert len(metric_item_div) == len(COMPUTE_USAGE_MULTIPLE)


class TestUsageTemplateEdgeCases:
    """Test edge cases in template rendering"""

    def test_handles_0_percent_usage(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_0_PCT, COMPUTE_USAGE_SINGLE)
        progress_label = soup.find(class_="progress-label")
        assert "0.0%" in progress_label.text
        progress_fill = soup.find(class_="progress-fill")
        assert "width: 0.0%" in progress_fill.get("style", "")
        metric_remaining = soup.find(class_="metric-remaining")
        assert "10.0 GiB remaining" in metric_remaining.text

    def test_handles_100_percent_usage(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_100_PCT, COMPUTE_USAGE_SINGLE)
        progress_label = soup.find(class_="progress-label")
        assert "100.0%" in progress_label.text
        progress_fill = soup.find(class_="progress-fill")
        assert "#ef4444" in progress_fill.get("style", "")
        metric_remaining = soup.find(class_="metric-remaining")
        assert "0.0 GiB remaining" in metric_remaining.text

    def test_handles_very_large_quota_terabytes(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_TERABYTES, COMPUTE_USAGE_SINGLE)
        metric_usage = soup.find(class_="metric-usage")
        assert "512.0 GiB used" in metric_usage.text
        assert "1024.0 GiB quota" in metric_usage.text


class TestUsageTemplateFooter:
    """Test footer and informational text"""

    def test_displays_footer_note(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        footer_note = soup.find(class_="footer-note")
        assert footer_note is not None
        assert "JupyterHub Admin" in footer_note.text
        assert "quota" in footer_note.text.lower()

    def test_displays_page_title(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        h1 = soup.find("h1")
        assert h1 is not None
        assert "Usage" in h1.text

    def test_displays_subtitle(self, jinja_env):
        soup = render_template(jinja_env, STORAGE_USAGE_50_PCT, COMPUTE_USAGE_SINGLE)
        subtitle = soup.find(class_="subtitle")
        assert subtitle is not None
        assert "view your current resource usage and quota" in subtitle.text.lower()
