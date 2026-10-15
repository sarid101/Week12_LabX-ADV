# agentic-comm-automator/src/utils.py
import logging
import os
import re
import datetime

from dotenv import load_dotenv

# Load environment variables from the .env file in the project root (not the current folder)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ${UPPER_CASE_NAME} = environment variable. Lower-case ${...} is left alone, so a template
# like "${sales_figure:.2f}" still means "$" + {sales_figure:.2f}.
ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def setup_logging(name, level=logging.INFO):
    """Sets up a logger for specific modules."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:  # Prevent adding multiple handlers if called multiple times
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.propagate = False
    return logger


def get_env_variable(var_name, default=None):
    """Retrieves an environment variable, raising an error if not found (and no default given)."""
    value = os.getenv(var_name)
    if value is None or value.strip() == "":
        if default is not None:
            return default
        raise ValueError(f"Environment variable '{var_name}' not set. Please check your .env file or environment settings.")
    return value.strip()


def expand_env_vars(value):
    """
    Recursively replaces ${ENV_VAR} placeholders in strings / lists / dicts of the config
    with values from the environment (.env). Unknown variables raise a clear error.
    """
    if isinstance(value, str):
        def _sub(match):
            var = match.group(1)
            env_value = os.getenv(var)
            if env_value is None:
                raise ValueError(f"Config uses ${{{var}}} but '{var}' is not set in .env")
            return env_value.strip()
        return ENV_PATTERN.sub(_sub, value)
    if isinstance(value, list):
        return [expand_env_vars(v) for v in value]
    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    return value


def mask_email(address):
    """'someone@gmail.com' -> 'so*****@gmail.com' (for logs / audit reports that may be committed)."""
    if not isinstance(address, str) or "@" not in address:
        return address
    name, domain = address.split("@", 1)
    return f"{name[:2]}{'*' * max(len(name) - 2, 1)}@{domain}"


def ensure_directory_exists(path):
    """Ensures that a directory exists, creating it if necessary."""
    if not path:
        return
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        logging.error(f"Error creating directory {path}: {e}")
        raise


def log_audit_entry(audit_log_list, status, message, task_type="N/A", details=None):
    """Adds an entry to the audit log list."""
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "task_type": task_type,
        "message": message,
        "details": details if details else {}
    }
    audit_log_list.append(log_entry)
    if status == "ERROR" or status == "CRITICAL":
        logging.error(f"AUDIT LOG - {status}: {message} | Task: {task_type}")
    else:
        logging.info(f"AUDIT LOG - {status}: {message} | Task: {task_type}")
