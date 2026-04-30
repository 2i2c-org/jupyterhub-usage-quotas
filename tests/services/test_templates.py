"""Tests for Jinja2 template rendering"""

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from jupyterhub_usage_quotas import get_template_path
from tests.services.fixtures.usage_data import (
    COMPUTE_DATA_PLACEHOLDER,
    USAGE_0_PCT,
    USAGE_50_PCT,
    USAGE_95_PCT,
    USAGE_100_PCT,
    USAGE_NO_DATA,
    USAGE_PROMETHEUS_ERROR,
    USAGE_TERABYTES,
)


@pytest.fixture
def jinja_env():
    """Create Jinja2 environment for template rendering"""
    return Environment(loader=FileSystemLoader(get_template_path()), autoescape=True)


def render_template(
    jinja_env: Environment,
    storage_data: dict = None,
    compute_data: dict = None,
    compute_data_placeholder=dict,
):
    """Helper to render template and return BeautifulSoup object"""
    template = jinja_env.get_template("usage.html")
    compute_data = compute_data_placeholder
    html_content = template.render(
        {"storage_data": storage_data, "compute_data": compute_data}
    )
    return BeautifulSoup(html_content, "html.parser")


class TestUsageTemplateWithNormalUsage:
    """Test template rendering with normal usage (< 90%)"""

    def test_displays_correct_usage_percentage(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        progress_label = soup.find(class_="progress-label")
        assert progress_label is not None
        assert "50.0%" in progress_label.text

    def test_displays_usage_and_quota_in_gib(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        metric_usage = soup.find(class_="metric-usage")
        assert metric_usage is not None
        assert "5.0 GiB used" in metric_usage.text
        assert "10.0 GiB quota" in metric_usage.text

    def test_displays_remaining_storage(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        metric_remaining = soup.find(class_="metric-remaining")
        assert metric_remaining is not None
        assert "5.0 GiB remaining" in metric_remaining.text

    def test_progress_bar_width_matches_percentage(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        progress_fill = soup.find(class_="progress-fill")
        assert progress_fill is not None
        assert "width: 50.0%" in progress_fill.get("style", "")

    def test_uses_normal_styling_below_90_percent(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        progress_fill = soup.find(class_="progress-fill")
        style = progress_fill.get("style", "")
        assert "#ef4444" not in style

    def test_displays_last_updated_timestamp(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        time_element = soup.find("time")
        assert time_element is not None
        assert time_element.has_attr("datetime")
        assert USAGE_50_PCT["last_updated"] in time_element["datetime"]

    def test_shows_normal_folder_icon(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        svgs = soup.find_all("svg", class_="icon")
        assert len(svgs) > 0
        circles = soup.find_all("circle")
        assert len(circles) == 0


class TestUsageTemplateWithHighUsage:
    """Test template rendering with high usage (>= 90%)"""

    def test_displays_sad_folder_icon_at_95_percent(self, jinja_env):
        soup = render_template(jinja_env, USAGE_95_PCT)
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
        soup = render_template(jinja_env, USAGE_95_PCT)
        element = soup.find(class_=css_class)
        assert expected_style in element.get("style", "")

    def test_percentage_threshold_at_exactly_90(self, jinja_env):
        soup = render_template(jinja_env, USAGE_95_PCT)
        progress_fill = soup.find(class_="progress-fill")
        assert "#ef4444" in progress_fill.get("style", "")


class TestUsageTemplateWithErrors:
    """Test template rendering with error states"""

    def test_displays_error_message_when_prometheus_down(self, jinja_env):
        soup = render_template(jinja_env, USAGE_PROMETHEUS_ERROR)
        error_message = soup.find(class_="error-message")
        assert error_message is not None
        assert "Unable to reach Prometheus" in error_message.text

    def test_displays_error_icon_not_folder(self, jinja_env):
        soup = render_template(jinja_env, USAGE_PROMETHEUS_ERROR)
        svgs = soup.find_all("svg", class_="icon")
        assert len(svgs) > 0
        svg = svgs[0]
        assert 'stroke="#ef4444"' in str(svg) or svg.get("stroke") == "#ef4444"

    def test_error_state_has_no_progress_bar(self, jinja_env):
        soup = render_template(jinja_env, USAGE_PROMETHEUS_ERROR)
        progress_track = soup.find(class_="progress-track")
        assert progress_track is None

    def test_displays_no_data_error(self, jinja_env):
        soup = render_template(jinja_env, USAGE_NO_DATA)
        error_message = soup.find(class_="error-message")
        assert error_message is not None
        assert "No storage data found" in error_message.text

    def test_error_message_has_red_styling(self, jinja_env):
        template = jinja_env.get_template("usage.html")
        html_content = template.render(
            storage_data=USAGE_PROMETHEUS_ERROR,
            compute_data=COMPUTE_DATA_PLACEHOLDER,
        )
        assert ".error-message" in html_content
        assert "color: #ef4444" in html_content or "color:#ef4444" in html_content


class TestUsageTemplateEdgeCases:
    """Test edge cases in template rendering"""

    def test_handles_0_percent_usage(self, jinja_env):
        soup = render_template(jinja_env, USAGE_0_PCT)
        progress_label = soup.find(class_="progress-label")
        assert "0.0%" in progress_label.text
        progress_fill = soup.find(class_="progress-fill")
        assert "width: 0.0%" in progress_fill.get("style", "")
        metric_remaining = soup.find(class_="metric-remaining")
        assert "10.0 GiB remaining" in metric_remaining.text

    def test_handles_100_percent_usage(self, jinja_env):
        soup = render_template(jinja_env, USAGE_100_PCT)
        progress_label = soup.find(class_="progress-label")
        assert "100.0%" in progress_label.text
        progress_fill = soup.find(class_="progress-fill")
        assert "#ef4444" in progress_fill.get("style", "")
        metric_remaining = soup.find(class_="metric-remaining")
        assert "0.0 GiB remaining" in metric_remaining.text

    def test_handles_very_large_quota_terabytes(self, jinja_env):
        soup = render_template(jinja_env, USAGE_TERABYTES)
        metric_usage = soup.find(class_="metric-usage")
        assert "512.0 GiB used" in metric_usage.text
        assert "1024.0 GiB quota" in metric_usage.text


class TestUsageTemplateFooter:
    """Test footer and informational text"""

    def test_displays_footer_note(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        footer_note = soup.find(class_="footer-note")
        assert footer_note is not None
        assert "JupyterHub Admin" in footer_note.text
        assert "quota" in footer_note.text.lower()

    def test_displays_page_title(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        h1 = soup.find("h1")
        assert h1 is not None
        assert "Usage" in h1.text

    def test_displays_subtitle(self, jinja_env):
        soup = render_template(jinja_env, USAGE_50_PCT)
        subtitle = soup.find(class_="subtitle")
        assert subtitle is not None
        assert "view your current resource usage and quota" in subtitle.text.lower()
