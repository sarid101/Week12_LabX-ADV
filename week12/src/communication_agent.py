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
