import os


def get_template_path():
    """Get the path to the templates directory."""
    return os.path.join(os.path.dirname(__file__), "templates")
