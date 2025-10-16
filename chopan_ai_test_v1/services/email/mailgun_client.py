import requests
import os
from typing import List, Dict, Any

class MailgunClient:
    def __init__(self):
        self.api_key = os.getenv("MAILGUN_API_KEY")
        self.domain = os.getenv("MAILGUN_DOMAIN")
        self.base_url = f"https://api.mailgun.net/v3/{self.domain}"
    
    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        content: str,
        from_email: str,
        from_name: str = "Chopan AI"
    ) -> Dict[str, Any]:
        """Send email using Mailgun"""
        try:
            data = {
                "from": f"{from_name} <{from_email}>",
                "to": to_emails,
                "subject": subject,
                "html": content
            }
            
            response = requests.post(
                f"{self.base_url}/messages",
                auth=("api", self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message_id": response.json().get("id"),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
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
        """Send bulk email using Mailgun"""
        try:
            # Mailgun batch sending
            recipient_vars = {}
            for i, recipient in enumerate(recipients):
                recipient_vars[recipient["email"]] = {"id": i}
            
            data = {
                "from": f"{from_name} <{from_email}>",
                "to": [r["email"] for r in recipients],
                "subject": subject,
                "html": content,
                "recipient-variables": recipient_vars
            }
            
            response = requests.post(
                f"{self.base_url}/messages",
                auth=("api", self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message_id": response.json().get("id"),
                    "status_code": response.status_code,
                    "recipients_count": len(recipients)
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                    "recipients_count": len(recipients)
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "recipients_count": len(recipients)
            }