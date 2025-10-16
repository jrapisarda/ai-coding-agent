import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import os
from typing import List, Dict, Any

class SendGridClient:
    def __init__(self):
        self.sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
    
    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        content: str,
        from_email: str,
        from_name: str = "Chopan AI"
    ) -> Dict[str, Any]:
        """Send email using SendGrid"""
        try:
            from_email_obj = Email(from_email, from_name)
            to_emails_obj = [To(email) for email in to_emails]
            content_obj = Content("text/html", content)
            
            mail = Mail(
                from_email=from_email_obj,
                to_emails=to_emails_obj,
                subject=subject,
                plain_text_content=content_obj
            )
            
            response = self.sg.send(mail)
            
            return {
                "success": True,
                "message_id": response.headers.get("X-Message-Id"),
                "status_code": response.status_code
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_bulk_email(
        self,
        recipients: List[Dict[str, str]],
        subject: str,
        content: str,
        from_email: str,
        from_name: str = "Chopan AI"
    ) -> Dict[str, Any]:
        """Send bulk email using SendGrid"""
        try:
            # Prepare personalization data
            personalizations = []
            for recipient in recipients:
                personalization = {
                    "to": [{"email": recipient["email"]}],
                    "subject": subject
                }
                personalizations.append(personalization)
            
            data = {
                "personalizations": personalizations,
                "from": {"email": from_email, "name": from_name},
                "content": [{"type": "text/html", "value": content}]
            }
            
            response = self.sg.client.mail.send.post(request_body=data)
            
            return {
                "success": True,
                "message_id": response.headers.get("X-Message-Id"),
                "status_code": response.status_code,
                "recipients_count": len(recipients)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "recipients_count": len(recipients)
            }