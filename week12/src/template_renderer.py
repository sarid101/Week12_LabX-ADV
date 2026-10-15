# agentic-comm-automator/src/template_renderer.py
import string
from utils import setup_logging

logger = setup_logging(__name__)


class TemplateRenderer:
    """
    A simple template renderer using Python's str.format syntax:
      {report_date}, {sales_figure:.2f}, {attachments_meta[0][filename]}
    """
    def __init__(self):
        logger.debug("TemplateRenderer initialized.")

    def render(self, template_string, context):
        """
        Renders a template string using a dictionary context.
        A missing key raises ValueError with a clear message.
        """
        if template_string is None:
            return ""
        try:
            return string.Formatter().vformat(template_string, [], context)
        except KeyError as e:
            logger.error(f"Missing key in template context: {e}. Template: '{template_string}'")
            raise ValueError(f"Missing context key: {e}")
        except (IndexError, AttributeError, TypeError) as e:
            logger.error(f"Bad placeholder in template '{template_string}': {e}")
            raise ValueError(f"Bad placeholder in template: {e}")
