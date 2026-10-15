# agentic-comm-automator/main.py
"""
python main.py          -> LIVE mode: sends real email via Gmail (needs .env)
python main.py --demo   -> DEMO mode: no mail server, emails are saved to data/demo_outbox/*.eml
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, 'src'))

from utils import setup_logging, ensure_directory_exists  # noqa: E402  (loads .env)

# In demo mode, fill any missing .env values with harmless placeholders before the config is read
DEMO = "--demo" in sys.argv or os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
if DEMO:
    for key, value in {"SENDER_EMAIL": "agent.demo@example.com",
                       "TEST_RECIPIENT_EMAIL": "team.demo@example.com",
                       "TEST_SMS_PHONE_NUMBER": "0812345678@sms-gateway.example.com",
                       "TEST_SMS_CARRIER": ""}.items():
        os.environ.setdefault(key, value)

from config_parser import ConfigParser                  # noqa: E402
from communication_agent import CommunicationAgent      # noqa: E402

logger = setup_logging(__name__)


def check_required_files(config):
    """Checks that static attachment paths (no {template}) exist before starting."""
    missing = []
    for task in config['tasks']:
        if task['type'] == 'send_email':
            for att in task.get('parameters', {}).get('attachments', []):
                if '{' in att:          # rendered later from the agent context
                    continue
                if not os.path.exists(os.path.join(BASE_DIR, att)):
                    missing.append(att)
    return missing


def main():
    config_file_path = os.path.join(BASE_DIR, 'configs', 'comm_pipeline_config.json')
    try:
        for d in ['data/reports', 'data/incoming_attachments', 'reports']:
            ensure_directory_exists(os.path.join(BASE_DIR, d))

        logger.info(f"Loading configuration from: {config_file_path}")
        config = ConfigParser(config_file_path).load_config()

        missing = check_required_files(config)
        if missing:
            logger.critical(f"Missing attachment files: {', '.join(missing)}. Run 'python create_sample_files.py' first.")
            sys.exit(1)

        agent = CommunicationAgent(config, BASE_DIR, demo=DEMO)
        report = agent.run()
        logger.info(f"Communication automation process completed. Audit report: {report}")

    except FileNotFoundError as e:
        logger.critical(f"File system error: {e}")
    except ValueError as e:
        logger.critical(f"Configuration or environment variable error: {e}")
        logger.info("Copy .env.example to .env and fill in your Gmail address and App Password.")
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
