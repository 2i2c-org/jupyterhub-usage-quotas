"""Tests for Jinja2 template rendering"""

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from jupyterhub_usage_quotas import get_template_path


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

    def test_displays_correct_usage_percentage(self, jinja_env, usage_data_50_percent):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        progress_label = soup.find(class_="progress-label")
        assert progress_label is not None
        assert "50.0%" in progress_label.text

    def test_displays_usage_and_quota_in_gib(self, jinja_env, usage_data_50_percent):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        metric_usage = soup.find(class_="metric-usage")
        assert metric_usage is not None
        assert "5.0 GiB used" in metric_usage.text
        assert "10.0 GiB quota" in metric_usage.text

    def test_displays_remaining_storage(self, jinja_env, usage_data_50_percent):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        metric_remaining = soup.find(class_="metric-remaining")
        assert metric_remaining is not None
        assert "5.0 GiB remaining" in metric_remaining.text

    def test_progress_bar_width_matches_percentage(
        self, jinja_env, usage_data_50_percent
    ):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        progress_fill = soup.find(class_="progress-fill")
        assert progress_fill is not None
        assert "width: 50.0%" in progress_fill.get("style", "")

    def test_uses_normal_styling_below_90_percent(
        self, jinja_env, usage_data_50_percent
    ):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        progress_fill = soup.find(class_="progress-fill")
        style = progress_fill.get("style", "")
        assert "#ef4444" not in style

    def test_displays_last_updated_timestamp(self, jinja_env, usage_data_50_percent):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        time_element = soup.find("time")
        assert time_element is not None
        assert time_element.has_attr("datetime")
        assert usage_data_50_percent["last_updated"] in time_element["datetime"]

    def test_shows_normal_folder_icon(self, jinja_env, usage_data_50_percent):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        svgs = soup.find_all("svg", class_="icon")
        assert len(svgs) > 0
        circles = soup.find_all("circle")
        assert len(circles) == 0


class TestUsageTemplateWithHighUsage:
    """Test template rendering with high usage (>= 90%)"""

    def test_displays_sad_folder_icon_at_95_percent(
        self, jinja_env, usage_data_95_percent
    ):
        soup = render_template(jinja_env, storage_data=usage_data_95_percent)
        circles = soup.find_all("circle")
        assert len(circles) == 2

    def test_progress_bar_is_red_at_high_usage(self, jinja_env, usage_data_95_percent):
        soup = render_template(jinja_env, storage_data=usage_data_95_percent)
        progress_fill = soup.find(class_="progress-fill")
        assert "background: #ef4444" in progress_fill.get("style", "")

    def test_remaining_storage_is_red_at_high_usage(
        self, jinja_env, usage_data_95_percent
    ):
        soup = render_template(jinja_env, storage_data=usage_data_95_percent)
        metric_remaining = soup.find(class_="metric-remaining")
        style = metric_remaining.get("style", "")
        assert "color: #ef4444" in style

    def test_percentage_threshold_at_exactly_90(self, jinja_env, usage_data_90_percent):
        soup = render_template(jinja_env, usage_data_90_percent)
        progress_fill = soup.find(class_="progress-fill")
        style = progress_fill.get("style", "")
        assert "#ef4444" in style

    def test_progress_label_is_red_at_high_usage(
        self, jinja_env, usage_data_95_percent
    ):
        soup = render_template(jinja_env, storage_data=usage_data_95_percent)
        progress_label = soup.find(class_="progress-label")
        style = progress_label.get("style", "")
        assert "color: #ef4444" in style


class TestUsageTemplateWithErrors:
    """Test template rendering with error states"""

    def test_displays_error_message_when_prometheus_down(
        self, jinja_env, usage_data_prometheus_error
    ):
        soup = render_template(jinja_env, usage_data_prometheus_error)
        error_message = soup.find(class_="error-message")
        assert error_message is not None
        assert "Unable to reach Prometheus" in error_message.text

    def test_displays_error_icon_not_folder(
        self, jinja_env, usage_data_prometheus_error
    ):
        soup = render_template(jinja_env, usage_data_prometheus_error)
        svgs = soup.find_all("svg", class_="icon")
        assert len(svgs) > 0
        svg = svgs[0]
        assert 'stroke="#ef4444"' in str(svg) or svg.get("stroke") == "#ef4444"

    def test_error_state_has_no_progress_bar(
        self, jinja_env, usage_data_prometheus_error
    ):
        soup = render_template(jinja_env, usage_data_prometheus_error)
        progress_track = soup.find(class_="progress-track")
        assert progress_track is None

    def test_displays_no_data_error(self, jinja_env, usage_data_no_quota):
        soup = render_template(jinja_env, usage_data_no_quota)
        error_message = soup.find(class_="error-message")
        assert error_message is not None
        assert "No storage data found" in error_message.text

    def test_error_message_has_red_styling(
        self, jinja_env, usage_data_prometheus_error, compute_data_placeholder
    ):
        template = jinja_env.get_template("usage.html")
        html_content = template.render(
            storage_data=usage_data_prometheus_error,
            compute_data=compute_data_placeholder,
        )
        assert ".error-message" in html_content
        assert "color: #ef4444" in html_content or "color:#ef4444" in html_content


class TestUsageTemplateEdgeCases:
    """Test edge cases in template rendering"""

    def test_handles_0_percent_usage(self, jinja_env, usage_data_0_percent):
        soup = render_template(jinja_env, usage_data_0_percent)
        progress_label = soup.find(class_="progress-label")
        assert "0.0%" in progress_label.text
        progress_fill = soup.find(class_="progress-fill")
        assert "width: 0.0%" in progress_fill.get("style", "")
        metric_remaining = soup.find(class_="metric-remaining")
        assert "10.0 GiB remaining" in metric_remaining.text

    def test_handles_100_percent_usage(self, jinja_env, usage_data_100_percent):
        soup = render_template(jinja_env, usage_data_100_percent)
        progress_label = soup.find(class_="progress-label")
        assert "100.0%" in progress_label.text
        progress_fill = soup.find(class_="progress-fill")
        assert "#ef4444" in progress_fill.get("style", "")
        metric_remaining = soup.find(class_="metric-remaining")
        assert "0.0 GiB remaining" in metric_remaining.text

    def test_handles_very_large_quota_terabytes(self, jinja_env, usage_data_terabytes):
        soup = render_template(jinja_env, usage_data_terabytes)
        metric_usage = soup.find(class_="metric-usage")
        assert "512.0 GiB used" in metric_usage.text
        assert "1024.0 GiB quota" in metric_usage.text


class TestUsageTemplateFooter:
    """Test footer and informational text"""

    def test_displays_footer_note(self, jinja_env, usage_data_50_percent):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        footer_note = soup.find(class_="footer-note")
        assert footer_note is not None
        assert "JupyterHub Admin" in footer_note.text
        assert "quota" in footer_note.text.lower()

    def test_displays_page_title(self, jinja_env, usage_data_50_percent):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        h1 = soup.find("h1")
        assert h1 is not None
        assert "Usage" in h1.text

    def test_displays_subtitle(self, jinja_env, usage_data_50_percent):
        soup = render_template(jinja_env, storage_data=usage_data_50_percent)
        subtitle = soup.find(class_="subtitle")
        assert subtitle is not None
        assert "view your current resource usage and quota" in subtitle.text.lower()
