# AllCode — Week 12 Agentic Communication Workflows
รวมซอร์สโค้ดทั้งหมดของโปรเจกต์ (สาริษฐ์ บุตรช่วง 663380365-3)

## `main.py`

```python
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
```

## `create_sample_files.py`

```python
# agentic-comm-automator/create_sample_files.py
# สร้างไฟล์แนบตัวอย่าง data/reports/sales_report.pdf และ data/reports/summary_data.xlsx
import os
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(BASE_DIR, "data", "reports")

SALES = [("Alice", 1425.75), ("Bob", 130.75), ("Charlie", 500.00), ("David", 90.00), ("Eve", 15.50)]


def create_pdf(path):
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    c.setFillColor(HexColor("#1F4E79"))
    c.rect(0, h - 90, w, 90, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(50, h - 55, "Daily Sales Report")
    c.setFont("Helvetica", 11)
    c.drawString(50, h - 75, f"Generated {datetime.date.today():%Y-%m-%d}")

    y = h - 140
    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "Customer")
    c.drawRightString(400, y, "Total Amount ($)")
    c.setFont("Helvetica", 12)
    for name, amount in SALES:
        y -= 22
        c.drawString(60, y, name)
        c.drawRightString(400, y, f"{amount:,.2f}")
    y -= 28
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "Total")
    c.drawRightString(400, y, f"{sum(a for _, a in SALES):,.2f}")
    c.save()
    print(f"Created {path}")


def create_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Customer", "Total_Amount"])
    for row in SALES:
        ws.append(row)
    ws.append(["Total", f"=SUM(B2:B{len(SALES) + 1})"])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 16
    wb.save(path)
    print(f"Created {path}")


if __name__ == "__main__":
    os.makedirs(REPORTS, exist_ok=True)
    create_pdf(os.path.join(REPORTS, "sales_report.pdf"))
    create_xlsx(os.path.join(REPORTS, "summary_data.xlsx"))
```

## `src/__init__.py`

```python
# agentic-comm-automator/src/__init__.py
# This file indicates that the 'src' directory is a Python package.
```

## `src/utils.py`

```python
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
```

## `src/template_renderer.py`

```python
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
```

## `src/config_parser.py`

```python
# agentic-comm-automator/src/config_parser.py
import json
import os
from utils import setup_logging, expand_env_vars

logger = setup_logging(__name__)


class ConfigParser:
    """
    Parses and validates the communication automation configuration from a JSON file.
    ${ENV_VAR} placeholders are replaced with values from .env after validation.
    """
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = {}

    def load_config(self):
        """Loads the configuration from the specified JSON file."""
        if not os.path.exists(self.config_path):
            logger.critical(f"Configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            logger.critical(f"Invalid JSON format in config file: {e}")
            raise ValueError(f"Invalid JSON format in config file: {e}")

        self._validate_config()
        self.config = expand_env_vars(self.config)  # ${SENDER_EMAIL} -> value from .env
        logger.info(f"Configuration loaded successfully from {self.config_path}")
        return self.config

    def _validate_config(self):
        """Validates required fields and task structures."""
        if "tasks" not in self.config:
            raise ValueError("Missing required field in config: 'tasks'")
        if not isinstance(self.config["tasks"], list):
            raise ValueError("Config field 'tasks' must be a list.")

        for i, task in enumerate(self.config["tasks"]):
            if "type" not in task:
                raise ValueError(f"Task {i} is missing 'type' field.")
            if "name" not in task:
                raise ValueError(f"Task {i} (type: {task['type']}) is missing 'name' field.")
            params = task.get("parameters")

            if task["type"] == "send_email":
                # 'to' lives inside parameters.recipients
                recipients = (params or {}).get("recipients", {})
                if not params or "to" not in recipients or not all(k in params for k in ["subject_template", "body_template"]):
                    raise ValueError(f"Task {i} (send_email) requires 'recipients.to', 'subject_template', 'body_template' in parameters.")
                for key in ["to", "cc", "bcc"]:
                    if key in recipients and not isinstance(recipients[key], list):
                        raise ValueError(f"Task {i} (send_email) 'recipients.{key}' must be a list.")
                if "attachments" in params and not isinstance(params["attachments"], list):
                    raise ValueError(f"Task {i} (send_email) 'attachments' parameter must be a list.")

            elif task["type"] == "send_sms":
                if not params or not all(k in params for k in ["phone_numbers", "message_template"]):
                    raise ValueError(f"Task {i} (send_sms) requires 'phone_numbers', 'message_template' in parameters.")
                if not isinstance(params["phone_numbers"], list):
                    raise ValueError(f"Task {i} (send_sms) 'phone_numbers' parameter must be a list.")

            elif task["type"] == "process_inbox":
                if not params or "search_criteria" not in params:
                    raise ValueError(f"Task {i} (process_inbox) requires 'search_criteria' in parameters.")
                if "rules" in params and not isinstance(params["rules"], list):
                    raise ValueError(f"Task {i} (process_inbox) 'rules' parameter must be a list.")

        logger.info("Configuration validated.")
```

## `src/email_tasks.py`

```python
# agentic-comm-automator/src/email_tasks.py
import os
import smtplib
import imaplib
import email
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import decode_header
from email.utils import parseaddr, formatdate, make_msgid

from utils import setup_logging, ensure_directory_exists

logger = setup_logging(__name__)


class EmailTasks:
    """
    Handles sending (SMTP) and receiving (IMAP) emails.
    Building and parsing messages are separate methods so they can be reused by DemoEmailTasks.
    """
    def __init__(self, smtp_server, smtp_port, imap_server, sender_email, sender_password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.sender_email = sender_email
        self.sender_password = sender_password
        self._smtp = None
        self._imap = None
        logger.info("EmailTasks initialized.")

    # ------------------------------------------------------------------ building / parsing
    def build_message(self, recipients, subject, body, attachments=None, is_html=False):
        """Builds a MIME message. Returns (message, list_of_all_recipient_addresses)."""
        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid()

        to_list = recipients.get('to', [])
        cc_list = recipients.get('cc', [])
        bcc_list = recipients.get('bcc', [])  # BCC is not written to the headers
        msg['To'] = ", ".join(to_list)
        if cc_list:
            msg['Cc'] = ", ".join(cc_list)

        msg.attach(MIMEText(body, 'html' if is_html else 'plain', 'utf-8'))

        for attachment_path in attachments or []:
            if not os.path.exists(attachment_path):
                logger.warning(f"Attachment file not found: {attachment_path}. Skipping.")
                continue
            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)
                logger.info(f"Attached file: {os.path.basename(attachment_path)}")
            except Exception as e:
                logger.error(f"Error attaching file {attachment_path}: {e}")

        # remove duplicates (e.g. sender in both To and Cc) but keep order
        all_recipients = list(dict.fromkeys(to_list + cc_list + bcc_list))
        return msg, all_recipients

    def parse_message(self, uid, raw_email, download_attachments_dir=None):
        """Parses raw RFC822 bytes into a dict; optionally saves attachments."""
        msg = email.message_from_bytes(raw_email)
        sender_header = self._decode_header_part(msg['From'])
        sender_address = parseaddr(sender_header)[1] or sender_header
        subject = self._decode_header_part(msg['Subject'])

        text_body, html_body, attachments_meta = "", "", []
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            filename = part.get_filename()
            if filename:
                filename = self._decode_header_part(filename)

            if "attachment" in disposition or filename:
                filepath = None
                if filename and download_attachments_dir:
                    ensure_directory_exists(download_attachments_dir)
                    filepath = os.path.join(download_attachments_dir, os.path.basename(filename))
                    try:
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        logger.info(f"Downloaded attachment: {filepath}")
                    except Exception as e:
                        logger.error(f"Error downloading attachment {filename}: {e}")
                        filepath = None
                attachments_meta.append({'filename': filename, 'filepath': filepath})
            elif content_type in ("text/plain", "text/html"):
                try:
                    text = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                except Exception as e:
                    logger.warning(f"Could not decode {content_type} part of email {uid}: {e}")
                    continue
                if content_type == "text/plain":
                    text_body += text
                else:
                    html_body += text

        return {
            "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
            "sender": sender_address,
            "subject": subject,
            "text_body": text_body,
            "html_body": html_body,
            "has_attachments": bool(attachments_meta),
            "attachments_meta": attachments_meta,
        }

    # ------------------------------------------------------------------ SMTP
    def _connect_smtp(self):
        if self._smtp:
            return True
        try:
            self._smtp = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
            self._smtp.starttls()
            self._smtp.login(self.sender_email, self.sender_password)
            logger.info("Connected and logged into SMTP server.")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed. Check email and APP PASSWORD. Error: {e}")
        except Exception as e:
            logger.error(f"SMTP connect/login failed: {e}")
        self._smtp = None
        return False

    def _disconnect_smtp(self):
        if self._smtp:
            try:
                self._smtp.quit()
            except Exception as e:
                logger.warning(f"Error during SMTP disconnection: {e}")
            finally:
                self._smtp = None

    def send_email(self, recipients, subject, body, attachments=None, is_html=False):
        """
        Sends an email. `recipients` = {'to': [...], 'cc': [...], 'bcc': [...]}.
        Returns True on success.
        """
        msg, all_recipients = self.build_message(recipients, subject, body, attachments, is_html)
        if not all_recipients:
            logger.error("No recipients specified for email.")
            return False
        if not self._connect_smtp():
            return False
        try:
            self._smtp.send_message(msg, from_addr=self.sender_email, to_addrs=all_recipients)
            logger.info(f"Email sent to {len(all_recipients)} recipient(s). Subject: '{subject}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
        finally:
            self._disconnect_smtp()

    # ------------------------------------------------------------------ IMAP
    def _connect_imap(self, mailbox='INBOX'):
        if self._imap:
            return True
        try:
            self._imap = imaplib.IMAP4_SSL(self.imap_server)
            self._imap.login(self.sender_email, self.sender_password)
            self._imap.select(mailbox)
            logger.info("Connected and logged into IMAP server.")
            return True
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP authentication failed. Check email and APP PASSWORD (and that IMAP is enabled). Error: {e}")
        except Exception as e:
            logger.error(f"IMAP connect/login failed: {e}")
        self._imap = None
        return False

    def close(self):
        """Closes the IMAP connection (kept open between search and fetch)."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception as e:
                logger.warning(f"Error during IMAP disconnection: {e}")
            finally:
                self._imap = None

    def search_emails(self, mailbox='INBOX', criteria='UNSEEN', from_sender=None, subject_contains=None,
                      since_today=False):
        """
        Searches emails and returns a list of UIDs (bytes), or None if the mailbox could not be reached.
        Uses UID SEARCH so the ids stay valid for the following UID FETCH / STORE.
        """
        if not self._connect_imap(mailbox):
            return None
        try:
            self._imap.select(mailbox)
            query = [criteria]
            if from_sender:
                query += ['FROM', f'"{from_sender}"']
            if subject_contains:
                query += ['SUBJECT', f'"{subject_contains}"']
            if since_today:
                query += ['SINCE', datetime.date.today().strftime("%d-%b-%Y")]
            status, data = self._imap.uid('search', None, *query)
            if status != 'OK':
                logger.error(f"IMAP search failed. Status: {status}")
                return None
            uids = data[0].split()
            logger.info(f"Found {len(uids)} email(s) matching {' '.join(query)} in '{mailbox}'.")
            return uids
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return None

    def fetch_email_content(self, uid, mark_as_read=True, download_attachments_dir=None):
        """Fetches one email by UID, optionally marks it as read and downloads attachments."""
        if not self._connect_imap():
            return None
        try:
            status, msg_data = self._imap.uid('fetch', uid, '(BODY.PEEK[])')
            if status != 'OK' or not msg_data or msg_data[0] is None:
                logger.error(f"Failed to fetch email UID {uid}. Status: {status}")
                return None
            info = self.parse_message(uid, msg_data[0][1], download_attachments_dir)
            if mark_as_read:
                self._imap.uid('store', uid, '+FLAGS', '(\\Seen)')
                logger.info(f"Marked email UID {info['uid']} as read.")
            return info
        except Exception as e:
            logger.error(f"Error fetching/parsing email UID {uid}: {e}")
            return None

    @staticmethod
    def _decode_header_part(header_value):
        """Decodes encoded headers such as '=?UTF-8?B?...?='."""
        if header_value is None:
            return ""
        decoded = ""
        for part, charset in decode_header(header_value):
            if isinstance(part, bytes):
                try:
                    decoded += part.decode(charset or 'utf-8')
                except (LookupError, UnicodeDecodeError):
                    decoded += part.decode('latin-1', errors='replace')
            else:
                decoded += part
        return decoded.strip()
```

## `src/demo_email_tasks.py`

```python
# agentic-comm-automator/src/demo_email_tasks.py
"""
DEMO MODE (python main.py --demo)

Runs the whole workflow without a real mail server so the pipeline can be tested
without a Gmail App Password. Every "sent" email is:
  * saved as an .eml file in data/demo_outbox/ (open it with Outlook / Thunderbird / any mail app)
  * delivered to an in-memory inbox when it is addressed to the sender, so that
    process_inbox can find, parse and apply rules to it exactly like with IMAP.
"""
import os
import re

from email_tasks import EmailTasks
from utils import setup_logging, ensure_directory_exists

logger = setup_logging(__name__)


class DemoEmailTasks(EmailTasks):
    def __init__(self, sender_email, outbox_dir):
        super().__init__("demo-smtp", 0, "demo-imap", sender_email, "")
        self.outbox_dir = outbox_dir
        ensure_directory_exists(outbox_dir)
        self.inbox = []        # list of {"uid": bytes, "raw": bytes, "seen": bool}
        self._counter = 0
        logger.info(f"DEMO MODE: emails will be saved to '{outbox_dir}' instead of being sent.")

    def send_email(self, recipients, subject, body, attachments=None, is_html=False):
        msg, all_recipients = self.build_message(recipients, subject, body, attachments, is_html)
        if not all_recipients:
            logger.error("No recipients specified for email.")
            return False
        self._counter += 1
        safe = re.sub(r'[^A-Za-z0-9]+', '_', subject or "sms").strip('_')[:50] or "sms"
        path = os.path.join(self.outbox_dir, f"{self._counter:02d}_{safe}.eml")
        raw = msg.as_bytes()
        with open(path, "wb") as f:
            f.write(raw)
        if self.sender_email in all_recipients:   # mail to self -> lands in our demo inbox
            self.inbox.append({"uid": str(len(self.inbox) + 1).encode(), "raw": raw, "seen": False})
        logger.info(f"[DEMO] Email saved: {os.path.basename(path)} (to {len(all_recipients)} recipient(s))")
        return True

    def search_emails(self, mailbox='INBOX', criteria='UNSEEN', from_sender=None, subject_contains=None,
                      since_today=False):
        uids = []
        for item in self.inbox:
            info = self.parse_message(item["uid"], item["raw"])
            if criteria.upper() == 'UNSEEN' and item["seen"]:
                continue
            if from_sender and from_sender.lower() not in info["sender"].lower():
                continue
            if subject_contains and subject_contains.lower() not in info["subject"].lower():
                continue
            uids.append(item["uid"])
        logger.info(f"[DEMO] Found {len(uids)} email(s) in demo inbox.")
        return uids

    def fetch_email_content(self, uid, mark_as_read=True, download_attachments_dir=None):
        item = next((i for i in self.inbox if i["uid"] == uid), None)
        if item is None:
            return None
        info = self.parse_message(uid, item["raw"], download_attachments_dir)
        if mark_as_read:
            item["seen"] = True
            logger.info(f"[DEMO] Marked email UID {info['uid']} as read.")
        return info

    def close(self):
        pass
```

## `src/sms_tasks.py`

```python
# agentic-comm-automator/src/sms_tasks.py
from utils import setup_logging
from email_tasks import EmailTasks  # Reuse EmailTasks for sending the actual email

logger = setup_logging(__name__)


class SMSTasks:
    """
    Sends SMS via email-to-SMS gateways (number@gateway).
    A phone entry can be a plain number + carrier_name, or a full address such as
    '0812345678@your-gateway.com' (or any email address you want to use as an "SMS inbox").
    """
    def __init__(self, email_tasks_instance):
        if not isinstance(email_tasks_instance, EmailTasks):
            raise TypeError("SMSTasks requires an instance of EmailTasks.")
        self.email_tasks = email_tasks_instance

        # Common US carrier email-to-SMS gateways (some carriers have shut theirs down)
        self.carrier_gateways = {
            "att": "@txt.att.net",
            "verizon": "@vtext.com",
            "tmobile": "@tmomail.net",
            "sprint": "@messaging.sprintpcs.com",
            "boost": "@sms.boostmobile.com",
            "cricket": "@mms.cricketwireless.net",
            "us_cellular": "@email.uscc.net",
        }
        logger.info("SMSTasks initialized.")

    def _gateway_address(self, phone_number, carrier_name):
        phone_number = phone_number.strip()
        if '@' in phone_number:                       # already a full gateway / email address
            return phone_number
        if carrier_name and carrier_name.lower() in self.carrier_gateways:
            return f"{phone_number}{self.carrier_gateways[carrier_name.lower()]}"
        return None

    def send_sms(self, phone_numbers, message, carrier_name=None):
        """
        Sends `message` to every number. Returns True only if all of them were sent.
        """
        sent, attempted = 0, 0
        for phone_number in phone_numbers:
            attempted += 1
            address = self._gateway_address(phone_number, carrier_name)
            if not address:
                logger.warning(f"No gateway for '{phone_number}' (carrier '{carrier_name}'). "
                               "Use a full address like number@gateway or set a supported carrier.")
                continue
            # SMS gateways show the subject in front of the text, so keep it short
            if self.email_tasks.send_email({'to': [address]}, "SMS Alert", message[:300]):
                sent += 1
        logger.info(f"SMS: {sent}/{attempted} message(s) sent.")
        return attempted > 0 and sent == attempted
```

## `src/communication_agent.py`

```python
# agentic-comm-automator/src/communication_agent.py
import os
import re
import json
import time
import datetime

from utils import setup_logging, log_audit_entry, ensure_directory_exists, get_env_variable, mask_email
from email_tasks import EmailTasks
from sms_tasks import SMSTasks
from template_renderer import TemplateRenderer

logger = setup_logging(__name__)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _mask(obj):
    """Masks every email address inside strings/lists/dicts (audit reports may end up on GitHub)."""
    if isinstance(obj, str):
        return EMAIL_RE.sub(lambda m: mask_email(m.group(0)), obj)
    if isinstance(obj, list):
        return [_mask(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _mask(v) for k, v in obj.items()}
    return obj


class CommunicationAgent:
    """
    Orchestrates communication tasks (email, SMS, inbox processing) from a JSON config,
    keeping a shared context dictionary for template values and task outputs.
    """
    def __init__(self, config, base_dir, demo=False):
        self.config = config
        self.base_dir = base_dir
        self.demo = demo
        self.audit_log = []
        self.context = {}  # Stores dynamic values for templating and task chaining
        self.start_time = datetime.datetime.now()
        self.template_renderer = TemplateRenderer()

        sender_email = get_env_variable("SENDER_EMAIL", "agent.demo@example.com" if demo else None)
        if demo:
            from demo_email_tasks import DemoEmailTasks
            self.email_tasks = DemoEmailTasks(sender_email, os.path.join(base_dir, "data", "demo_outbox"))
        else:
            self.email_tasks = EmailTasks(
                get_env_variable("SMTP_SERVER", "smtp.gmail.com"),
                int(get_env_variable("SMTP_PORT", "587")),
                get_env_variable("IMAP_SERVER", "imap.gmail.com"),
                sender_email,
                get_env_variable("SENDER_APP_PASSWORD").replace(" ", ""),  # Google shows it with spaces
            )
        self.sms_tasks = SMSTasks(self.email_tasks)
        logger.info(f"CommunicationAgent initialized ({'DEMO' if demo else 'LIVE'} mode).")

    # ------------------------------------------------------------------ helpers
    def _audit(self, status, message, task_type="N/A", details=None):
        log_audit_entry(self.audit_log, status, _mask(message), task_type, _mask(details) if details else None)

    def _update_context(self, key, value):
        self.context[key] = value
        logger.debug(f"Context updated: '{key}'")

    def _render(self, template_string, extra=None):
        context = {**self.context, **(extra or {})}
        return self.template_renderer.render(template_string, context)

    # ------------------------------------------------------------------ task handlers
    def _task_send_email(self, params):
        recipients = {k: [self._render(r) for r in v if r] for k, v in params.get('recipients', {}).items()}
        subject = self._render(params.get("subject_template"))
        body = self._render(params.get("body_template"))

        attachments = []
        for att in params.get("attachments", []):
            path = os.path.join(self.base_dir, self._render(att))
            if os.path.exists(path):           # conditional attachment: only attach files that exist
                attachments.append(path)
            else:
                self._audit("WARNING", f"Attachment not found, skipped: {att}", "send_email")

        ok = self.email_tasks.send_email(recipients, subject, body, attachments, params.get("is_html", False))
        output = {"recipients": recipients, "subject": subject,
                  "attachments": [os.path.basename(a) for a in attachments]}
        return ok, output

    def _task_send_sms(self, params):
        numbers = [self._render(p) for p in params.get("phone_numbers", []) if p]
        message = self._render(params.get("message_template"))
        ok = self.sms_tasks.send_sms(numbers, message, params.get("carrier_name") or None)
        return ok, {"phone_numbers": numbers, "message": message}

    def _rule_matches(self, conditions, info):
        if "from_sender_is" in conditions and self._render(conditions["from_sender_is"]).lower() != info["sender"].lower():
            return False
        if "subject_contains" in conditions and self._render(conditions["subject_contains"]).lower() not in info["subject"].lower():
            return False
        body = info["text_body"] or info["html_body"]
        if "body_contains" in conditions and self._render(conditions["body_contains"]).lower() not in body.lower():
            return False
        if "has_attachments" in conditions and conditions["has_attachments"] != info["has_attachments"]:
            return False
        return True

    def _apply_actions(self, actions, info):
        done = []
        if actions.get("send_sms_alert"):
            message = self._render(actions.get("alert_message_template",
                                               "Urgent email received: {subject} from {sender}"), info)
            numbers = [self._render(p) for p in actions.get("alert_phone_numbers", []) if p]
            ok = self.sms_tasks.send_sms(numbers, message, actions.get("alert_carrier") or None)
            done.append(f"send_sms_alert:{'OK' if ok else 'FAILED'}")
            self._audit("SUCCESS" if ok else "ERROR", f"SMS alert for '{info['subject']}': {message}", "rule_action")

        if "reply_with_template" in actions:
            body = self._render(actions["reply_with_template"], info)
            subject = self._render(actions.get("reply_subject_template", "Re: {subject}"), info)
            ok = self.email_tasks.send_email({'to': [info['sender']]}, subject, body)
            done.append(f"auto_reply:{'OK' if ok else 'FAILED'}")
            self._audit("SUCCESS" if ok else "ERROR", f"Auto-reply sent: '{subject}'", "rule_action")
        return done

    def _task_process_inbox(self, params):
        mailbox = params.get("mailbox", "INBOX")
        criteria = params.get("search_criteria", {})
        rules = params.get("rules", [])
        download_dir = os.path.join(self.base_dir, params.get("download_attachments_base_dir", "data/incoming_attachments"))
        exclude_prefix = criteria.get("exclude_subject_prefix", "Re:")  # don't process our own auto-replies
        retries = int(params.get("max_retries", 3))
        wait = 0 if self.demo else int(params.get("wait_seconds", 10))

        sender = self._render(criteria["from_sender"]) if criteria.get("from_sender") else None
        subject = self._render(criteria["subject_contains"]) if criteria.get("subject_contains") else None

        # an email we just sent to ourselves can take a few seconds to arrive -> poll a few times
        uids = []
        for attempt in range(1, retries + 1):
            uids = self.email_tasks.search_emails(mailbox, criteria.get("status", "UNSEEN"), sender, subject,
                                                  criteria.get("since_today", False))
            if uids is None:   # could not log in / search -> the task really failed
                self.email_tasks.close()
                self._audit("ERROR", "Could not access the mailbox (check IMAP settings / App Password).", "process_inbox")
                return False, {"processed_emails": [], "count": 0}
            if uids or attempt == retries:
                break
            logger.info(f"No matching email yet (attempt {attempt}/{retries}). Waiting {wait}s...")
            time.sleep(wait)

        processed = []
        try:
            for uid in uids:
                info = self.email_tasks.fetch_email_content(uid, mark_as_read=True, download_attachments_dir=download_dir)
                if not info:
                    self._audit("ERROR", f"Failed to fetch email UID {uid!r}", "process_inbox")
                    continue
                if exclude_prefix and info["subject"].lower().startswith(exclude_prefix.lower()):
                    logger.info(f"Skipping reply email '{info['subject']}'.")
                    continue

                self._audit("INFO", f"Processing email '{info['subject']}' from {info['sender']} "
                                    f"({len(info['attachments_meta'])} attachment(s) downloaded)", "process_inbox")
                actions_done = []
                for idx, rule in enumerate(rules, 1):
                    if self._rule_matches(rule.get("if", {}), info):
                        logger.info(f"Rule {idx} matched for '{info['subject']}'.")
                        actions_done += self._apply_actions(rule.get("then", {}), info)
                    else:
                        logger.info(f"Rule {idx} did not match for '{info['subject']}'.")
                processed.append({"uid": info["uid"], "sender": info["sender"], "subject": info["subject"],
                                  "attachments": [a["filename"] for a in info["attachments_meta"]],
                                  "actions": actions_done})
        finally:
            self.email_tasks.close()

        if not processed:
            self._audit("WARNING", "No emails matched the search criteria.", "process_inbox")
        return True, {"processed_emails": processed, "count": len(processed)}

    # ------------------------------------------------------------------ main loop
    def _process_task(self, task):
        task_type = task.get("type")
        task_name = task.get("name", task_type)
        params = task.get("parameters", {})
        handlers = {"send_email": self._task_send_email,
                    "send_sms": self._task_send_sms,
                    "process_inbox": self._task_process_inbox}

        logger.info(f"Executing task: '{task_name}' (Type: {task_type})")
        self._audit("INFO", f"Starting task '{task_name}'", task_type)

        handler = handlers.get(task_type)
        if handler is None:
            self._audit("WARNING", f"Unsupported task type: {task_type}", task_type, task)
            return
        try:
            success, output = handler(params)
            if success and task.get("output_context_key"):
                self._update_context(task["output_context_key"], output)
            self._audit("SUCCESS" if success else "ERROR",
                        f"Task '{task_name}' {'completed successfully' if success else 'failed'}.", task_type, output)
        except Exception as e:
            self._audit("ERROR", f"An error occurred during task '{task_name}': {e}", task_type, {"error": str(e)})
            logger.error(f"Error during task '{task_name}': {e}", exc_info=True)

    def _generate_audit_report(self, output_dir):
        ensure_directory_exists(output_dir)
        path = os.path.join(output_dir, f"audit_report_comm_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        self._audit("INFO", f"Audit report generated at reports/{os.path.basename(path)}", "audit_report")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.audit_log, f, indent=4, ensure_ascii=False)
            logger.info(f"Audit report saved to: {path}")
        except Exception as e:
            logger.error(f"Failed to save audit report: {e}")
        return path

    def run(self):
        logger.info("Starting Communication Agent run...")
        self._audit("INFO", f"Communication Agent started ({'DEMO' if self.demo else 'LIVE'} mode).", "agent_run")

        # Simulated data from a previous agent run (e.g. the Data Agent)
        self._update_context("report_name", "DailySalesSummary")
        self._update_context("report_date", datetime.date.today().strftime("%Y-%m-%d"))
        self._update_context("sales_figure", 12345.67)
        self._update_context("total_customers", 500)
        self._update_context("attachment_path_1", "data/reports/sales_report.pdf")
        self._update_context("attachment_path_2", "data/reports/summary_data.xlsx")

        for task in self.config.get("tasks", []):
            self._process_task(task)

        duration = (datetime.datetime.now() - self.start_time).total_seconds()
        self._audit("INFO", f"Communication Agent finished in {duration:.2f} seconds.", "agent_run_summary")
        return self._generate_audit_report(os.path.join(self.base_dir, 'reports'))
```

## `configs/comm_pipeline_config.json`

```json
{
    "tasks": [
        {
            "name": "Send Daily Sales Report Email",
            "type": "send_email",
            "parameters": {
                "recipients": {
                    "to": ["${TEST_RECIPIENT_EMAIL}"],
                    "cc": ["${SENDER_EMAIL}"]
                },
                "subject_template": "Daily Sales Report - {report_date}",
                "body_template": "Dear Team,\n\nPlease find the latest sales report for {report_date} attached. Total sales: ${sales_figure:,.2f}. Total active customers: {total_customers}.\n\nBest regards,\nAutomated Agent",
                "attachments": [
                    "{attachment_path_1}",
                    "{attachment_path_2}"
                ],
                "is_html": false
            },
            "output_context_key": "daily_report_email"
        },
        {
            "name": "Send Sales Alert SMS",
            "type": "send_sms",
            "parameters": {
                "phone_numbers": ["${TEST_SMS_PHONE_NUMBER}"],
                "message_template": "Sales for {report_date} are ${sales_figure:,.2f}. Total customers: {total_customers}. Review!",
                "carrier_name": "${TEST_SMS_CARRIER}"
            },
            "output_context_key": "sales_sms"
        },
        {
            "name": "Simulate Incoming Request Email (to self)",
            "type": "send_email",
            "parameters": {
                "recipients": {
                    "to": ["${SENDER_EMAIL}"]
                },
                "subject_template": "Data Request for {report_date} - Urgent",
                "body_template": "Hello Agent,\n\nWe need the latest data for {report_date}. Please process urgently. This email includes attachments.\n\nThank you,\nClient Team\n\n\nThis is an urgent request for new data processing.",
                "attachments": [
                    "data/reports/sales_report.pdf"
                ],
                "is_html": false
            },
            "output_context_key": "simulated_email_sent"
        },
        {
            "name": "Process Incoming Data Requests",
            "type": "process_inbox",
            "parameters": {
                "mailbox": "INBOX",
                "search_criteria": {
                    "status": "UNSEEN",
                    "from_sender": "${SENDER_EMAIL}",
                    "subject_contains": "Data Request",
                    "exclude_subject_prefix": "Re:"
                },
                "wait_seconds": 10,
                "max_retries": 3,
                "download_attachments_base_dir": "data/incoming_attachments",
                "rules": [
                    {
                        "if": {
                            "subject_contains": "Urgent",
                            "has_attachments": true
                        },
                        "then": {
                            "send_sms_alert": true,
                            "alert_phone_numbers": ["${TEST_SMS_PHONE_NUMBER}"],
                            "alert_carrier": "${TEST_SMS_CARRIER}",
                            "alert_message_template": "URGENT: New Data Request email received from {sender} - Subject: {subject}. Saved: {attachments_meta[0][filename]}"
                        }
                    },
                    {
                        "if": {
                            "body_contains": "new data processing"
                        },
                        "then": {
                            "reply_with_template": "Agent received your request for '{subject}'. We are now processing the new data. You will receive an update shortly.",
                            "reply_subject_template": "Re: {subject} - Received & Processing"
                        }
                    }
                ]
            },
            "output_context_key": "processed_inbox_results"
        }
    ]
}
```

## `.env.example`

```ini
# Copy this file to .env and fill in your own values.  NEVER commit .env to GitHub.
SENDER_EMAIL=your_gmail_address@gmail.com
SENDER_APP_PASSWORD=your16charapppassword
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
IMAP_SERVER=imap.gmail.com

# Recipient for the daily report email (another address you can check)
TEST_RECIPIENT_EMAIL=another_email@example.com

# "SMS" target. Thai carriers have no email-to-SMS gateway, so put an email address you can
# check on your phone (e.g. your own Gmail). US users can put a number and set a carrier.
TEST_SMS_PHONE_NUMBER=your_gmail_address@gmail.com
TEST_SMS_CARRIER=
```

## `requirements.txt`

```text
python-dotenv>=1.0
# only needed for create_sample_files.py
reportlab>=4.0
openpyxl>=3.1
```
